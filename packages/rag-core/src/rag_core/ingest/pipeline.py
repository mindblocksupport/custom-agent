"""Ingest pipeline: file → parse → chunk → embed → store.

Day 9 解析器:
- .md / .txt → 直接读
- .pdf → 占位 (Day 11 PaddleOCR-VL 接入)
- 其他 → 当 plain text 读
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import UUID

from rag_core.chunking.parent_child import ParentChildChunker
from rag_core.chunking.recursive import RecursiveChunker
from rag_core.embedding.base import EmbeddingProvider
from rag_core.ingest.sanitize import detect_injection
from rag_core.storage.pgvector_store import PgVectorStore
from rag_core.tokenize.jieba_tokenizer import tokenize_for_bm25
from rag_core.types import Chunk, Doc, IngestReport


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_file(path: Path) -> tuple[str, str]:
    """返回 (text, title). PDF 走占位; .md/.txt 原样读."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        raise NotImplementedError("PDF 解析将在 Day 11 通过 PaddleOCR-VL 接入")
    text = path.read_text(encoding="utf-8", errors="replace")
    # 标题: 用第一行 # 标题 / 文件名兜底
    title = path.stem
    for line in text.splitlines():
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            break
    return text, title


class IngestPipeline:
    def __init__(
        self,
        store: PgVectorStore,
        embedder: EmbeddingProvider,
        chunker: RecursiveChunker | None = None,
        parent_child_chunker: ParentChildChunker | None = None,
    ) -> None:
        self.store = store
        self.embedder = embedder
        # 互斥: 设了 parent_child_chunker 走 hierarchical 路径
        self.chunker = chunker or RecursiveChunker()
        self.parent_child_chunker = parent_child_chunker

    def ingest_text(
        self,
        *,
        text: str,
        source_uri: str,
        tenant_id: UUID,
        acl: list[str],
        title: str | None = None,
        source_type: str = "file",
        metadata: dict | None = None,
    ) -> IngestReport:
        if not text.strip():
            raise ValueError("empty text")

        # 1. doc upsert (内容未变直接 noop)
        doc = Doc(
            tenant_id=tenant_id,
            source_uri=source_uri,
            source_type=source_type,
            title=title,
            checksum=_sha256(text.encode("utf-8")),
            acl=acl,
            metadata=metadata or {},
        )
        doc_id, version, changed = self.store.upsert_doc(doc)
        if not changed:
            return IngestReport(
                doc_id=doc_id, tenant_id=tenant_id, source_uri=source_uri,
                chunks_created=0, chunks_reused=0, version=version,
            )

        # 2. chunk
        if self.parent_child_chunker is not None:
            chunks = self._chunks_parent_child(doc_id, tenant_id, version, text)
        else:
            chunks = self._chunks_flat(doc_id, tenant_id, version, text)

        if not chunks:
            return IngestReport(
                doc_id=doc_id, tenant_id=tenant_id, source_uri=source_uri,
                chunks_created=0, chunks_reused=0, version=version,
            )
        created, reused = self.store.upsert_chunks(chunks)

        return IngestReport(
            doc_id=doc_id, tenant_id=tenant_id, source_uri=source_uri,
            chunks_created=created, chunks_reused=reused, version=version,
        )

    def _chunks_flat(self, doc_id, tenant_id, version, text):
        spans = self.chunker.split(text)
        if not spans:
            return []
        embeddings = self.embedder.encode([s.content for s in spans])
        out = []
        for span, emb in zip(spans, embeddings, strict=True):
            quarantined, reason = detect_injection(span.content)
            meta = {"heading_path": list(span.heading_path)}
            if quarantined:
                meta["quarantine_reason"] = reason
            out.append(
                Chunk(
                    doc_id=doc_id, tenant_id=tenant_id, chunk_seq=span.seq,
                    doc_version=version, content=span.content,
                    content_hash=span.content_hash, embedding=emb,
                    embedding_model_version=self.embedder.name, metadata=meta,
                    char_offset_start=span.char_offset_start,
                    char_offset_end=span.char_offset_end,
                    bm25_tokens=tokenize_for_bm25(span.content),
                    is_quarantined=quarantined,
                )
            )
        return out

    def _chunks_parent_child(self, doc_id, tenant_id, version, text):
        """父子两层 chunks. 父块不 embed (只做引用容器), 子块 embed.

        chunk_seq 编排:
            parents 用 [0, n_parents)
            children 用 [n_parents, n_parents + n_children)
        子块的 parent_id 指向父块的 (本次还没 id, 用 chunk_seq 临时引用 → upsert 后回填)
        """
        from uuid import uuid4
        h = self.parent_child_chunker.split(text)
        n_parents = len(h.parents)
        # 1) 给 parents 预分配 id (避免一次 round-trip 后再 update)
        parent_ids = [uuid4() for _ in h.parents]
        out: list[Chunk] = []
        # parents — 不 embed (embedding=None), 仅作引用容器
        for parent, pid in zip(h.parents, parent_ids):
            quarantined, reason = detect_injection(parent.content)
            meta = {
                "heading_path": list(parent.heading_path),
                "role": "parent",
            }
            if quarantined:
                meta["quarantine_reason"] = reason
            out.append(
                Chunk(
                    id=pid,
                    doc_id=doc_id, tenant_id=tenant_id, chunk_seq=parent.seq,
                    doc_version=version, content=parent.content,
                    content_hash=parent.content_hash,
                    embedding=None,
                    embedding_model_version=self.embedder.name, metadata=meta,
                    char_offset_start=parent.char_offset_start,
                    char_offset_end=parent.char_offset_end,
                    bm25_tokens=None,                  # 父不参与 BM25
                    is_quarantined=quarantined,
                )
            )
        # children — embed + parent_id 指向 parent
        child_texts = [c.content for c in h.children]
        child_embeddings = self.embedder.encode(child_texts) if child_texts else []
        for i, (child, emb) in enumerate(zip(h.children, child_embeddings, strict=True)):
            parent_seq = h.parent_of_child[child.seq]
            parent_id = parent_ids[parent_seq]
            quarantined, reason = detect_injection(child.content)
            meta = {
                "heading_path": list(child.heading_path),
                "role": "child",
            }
            if quarantined:
                meta["quarantine_reason"] = reason
            out.append(
                Chunk(
                    doc_id=doc_id, tenant_id=tenant_id,
                    chunk_seq=n_parents + child.seq,
                    parent_id=parent_id,
                    doc_version=version, content=child.content,
                    content_hash=child.content_hash, embedding=emb,
                    embedding_model_version=self.embedder.name, metadata=meta,
                    char_offset_start=child.char_offset_start,
                    char_offset_end=child.char_offset_end,
                    bm25_tokens=tokenize_for_bm25(child.content),
                    is_quarantined=quarantined,
                )
            )
        return out


def ingest_file(
    pipeline: IngestPipeline,
    path: Path,
    *,
    tenant_id: UUID,
    acl: list[str],
) -> IngestReport:
    text, title = parse_file(path)
    return pipeline.ingest_text(
        text=text,
        source_uri=str(path.resolve()),
        tenant_id=tenant_id,
        acl=acl,
        title=title,
        source_type="file",
    )
