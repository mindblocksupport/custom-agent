"""rag-core: RAG 核心库 (L37 plan v1.1)

子模块:
- chunking: 切分 (Day 9 recursive + markdown, Day 12 parent-child + contextual)
- embedding: 向量化 (Qwen3 自托管, hash-backend for tests)
- storage: 持久化 (pgvector)
- retrieval: 召回 (Day 9 dense, Day 10 BM25 + RRF)
- ingest: pipeline (file -> parse -> chunk -> embed -> store)
- cli: `rag ingest <path>` / `rag query "..."`
"""

from rag_core.types import Chunk, Citation, Doc, SearchHit

__all__ = ["Chunk", "Citation", "Doc", "SearchHit"]
