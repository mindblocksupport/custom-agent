"""InMemoryStore: 不依赖 PG 的 store 实现 (eval / 单测专用).

实现 dense_search + bm25_search 接口, 行为与 PgVectorStore 兼容,
让 eval pipeline 能在 CI / 没 docker 的开发机上跑。

注: 不实现 upsert_doc / upsert_chunks 的语义 (那是数据库职责),
只暴露一个 ingest_chunks(chunks, doc_meta) 方法, 接收已切好已 embed 的 chunks。
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from rag_core.tokenize.jieba_tokenizer import tokenize_for_bm25
from rag_core.types import Chunk, SearchHit


@dataclass
class _DocMeta:
    title: str | None
    source_uri: str
    acl: list[str]
    status: str = "published"
    deleted: bool = False


@dataclass
class InMemoryStore:
    chunks: list[Chunk] = field(default_factory=list)
    doc_meta: dict[UUID, _DocMeta] = field(default_factory=dict)
    # BM25 倒排 (query 时用) — 简化版: token → set(chunk_idx)
    _doc_token_freq: list[Counter] = field(default_factory=list)
    _avg_doc_len: float = 0.0

    def add_doc(
        self, *, title: str | None, source_uri: str, acl: list[str]
    ) -> UUID:
        doc_id = uuid4()
        self.doc_meta[doc_id] = _DocMeta(
            title=title, source_uri=source_uri, acl=acl
        )
        return doc_id

    def add_chunks(self, chunks: list[Chunk]) -> None:
        for c in chunks:
            if c.id is None:
                c = c.model_copy(update={"id": uuid4()})
            self.chunks.append(c)
            tokens_str = c.bm25_tokens or tokenize_for_bm25(c.content)
            self._doc_token_freq.append(Counter(tokens_str.split()))
        if self._doc_token_freq:
            self._avg_doc_len = sum(
                sum(c.values()) for c in self._doc_token_freq
            ) / len(self._doc_token_freq)

    def fetch_parents(self, chunk_ids: list[UUID]) -> dict[UUID, str]:
        """child chunk_id → parent content. 缺父返回空."""
        # build child_id → parent_id
        id_to_chunk = {c.id: c for c in self.chunks if c.id is not None}
        out: dict[UUID, str] = {}
        for cid in chunk_ids:
            child = id_to_chunk.get(cid)
            if child and child.parent_id and child.parent_id in id_to_chunk:
                out[cid] = id_to_chunk[child.parent_id].content
        return out

    # ---------- ACL filter ----------
    def _visible(self, chunk: Chunk, principals: list[str], tenant_id: UUID) -> bool:
        if chunk.tenant_id != tenant_id:
            return False
        if chunk.is_quarantined:
            return False
        meta = self.doc_meta.get(chunk.doc_id)
        if not meta or meta.deleted or meta.status != "published":
            return False
        return any(p in meta.acl for p in principals)

    # ---------- dense ----------
    def dense_search(
        self, *, tenant_id: UUID, query_embedding: list[float],
        principals: list[str], k: int = 5, filters: dict | None = None,
    ) -> list[SearchHit]:
        results: list[tuple[float, Chunk]] = []
        for c in self.chunks:
            if not self._visible(c, principals, tenant_id):
                continue
            if c.embedding is None:
                continue                            # 父块没 embed, 不参与 dense 召回
            score = sum(a * b for a, b in zip(query_embedding, c.embedding))
            results.append((score, c))
        results.sort(key=lambda x: x[0], reverse=True)
        return [
            SearchHit(
                chunk=c, score=float(s),
                source_uri=self.doc_meta[c.doc_id].source_uri,
                title=self.doc_meta[c.doc_id].title,
            )
            for s, c in results[:k]
        ]

    # ---------- BM25 (Okapi BM25) ----------
    def bm25_search(
        self, *, tenant_id: UUID, query_tokens: str,
        principals: list[str], k: int = 5, filters: dict | None = None,
    ) -> list[SearchHit]:
        if not query_tokens.strip():
            return []
        q_terms = [t for t in query_tokens.split() if t]
        if not q_terms:
            return []
        N = len(self.chunks)
        if N == 0:
            return []

        # idf (per term, smoothed)
        df = Counter()
        for tf in self._doc_token_freq:
            for term in q_terms:
                if term in tf:
                    df[term] += 1
        idf = {
            term: math.log(1 + (N - df[term] + 0.5) / (df[term] + 0.5))
            for term in q_terms
        }

        k1, b = 1.5, 0.75
        results: list[tuple[float, Chunk]] = []
        for i, c in enumerate(self.chunks):
            if not self._visible(c, principals, tenant_id):
                continue
            tf = self._doc_token_freq[i]
            doc_len = sum(tf.values()) or 1
            score = 0.0
            for term in q_terms:
                if term not in tf:
                    continue
                f = tf[term]
                num = f * (k1 + 1)
                den = f + k1 * (1 - b + b * doc_len / max(self._avg_doc_len, 1))
                score += idf[term] * num / den
            if score > 0:
                results.append((score, c))
        results.sort(key=lambda x: x[0], reverse=True)
        return [
            SearchHit(
                chunk=c, score=float(s),
                source_uri=self.doc_meta[c.doc_id].source_uri,
                title=self.doc_meta[c.doc_id].title,
            )
            for s, c in results[:k]
        ]
