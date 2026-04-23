"""RAG 核心类型 (L37 §8.4 引用结构对齐)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class Doc(BaseModel):
    """文档主表映射 (rag_docs)."""

    id: UUID | None = None
    tenant_id: UUID
    source_uri: str
    source_type: str = "file"
    title: str | None = None
    checksum: str                                # sha256
    current_version: int = 1
    status: str = "published"
    acl: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class Chunk(BaseModel):
    """chunk 映射 (rag_chunks)."""

    id: UUID | None = None
    doc_id: UUID
    tenant_id: UUID
    parent_id: UUID | None = None
    chunk_seq: int
    doc_version: int = 1
    content: str
    content_hash: str                            # sha256(content)
    embedding: list[float] | None = None
    embedding_model_version: str = "qwen3-0.6b-v1"
    metadata: dict = Field(default_factory=dict)
    page: int | None = None
    char_offset_start: int | None = None
    char_offset_end: int | None = None
    is_quarantined: bool = False
    bm25_tokens: str | None = None              # jieba 预切分, 落 bm25_tokens 列


class Citation(BaseModel):
    """检索返回的引用 (L37 §8.4).

    前端显示 + 审计都依赖这个结构。
    """

    doc_id: UUID
    chunk_id: UUID
    source_uri: str
    title: str | None = None
    page: int | None = None
    char_offset_start: int | None = None
    char_offset_end: int | None = None
    score: float
    snippet: str                                  # 首 200 字符


class SearchHit(BaseModel):
    """dense_search / hybrid_search 单条结果."""

    chunk: Chunk
    score: float
    source_uri: str | None = None
    title: str | None = None
    parent_content: str | None = None             # Day 12: parent-child enrichment

    def to_citation(self) -> Citation:
        assert self.chunk.id is not None, "chunk must be persisted before citation"
        assert self.chunk.doc_id is not None
        # 父块存在时, snippet 用父块 (上下文更全), 否则用子块自身
        snippet_src = self.parent_content if self.parent_content else self.chunk.content
        snippet = snippet_src[:400]
        return Citation(
            doc_id=self.chunk.doc_id,
            chunk_id=self.chunk.id,
            source_uri=self.source_uri or "",
            title=self.title,
            page=self.chunk.page,
            char_offset_start=self.chunk.char_offset_start,
            char_offset_end=self.chunk.char_offset_end,
            score=self.score,
            snippet=snippet,
        )


class IngestReport(BaseModel):
    """CLI / MCP 返回的 ingest 统计."""

    doc_id: UUID
    tenant_id: UUID
    source_uri: str
    chunks_created: int
    chunks_reused: int                            # content_hash 未变, 省 embed
    version: int
    ingested_at: datetime = Field(default_factory=datetime.now)
