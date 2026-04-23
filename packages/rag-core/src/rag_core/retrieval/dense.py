"""Dense 检索器 (Day 9). Day 10 加 BM25 + RRF, Day 12 加 query 改写."""

from __future__ import annotations

from uuid import UUID

from rag_core.embedding.base import EmbeddingProvider
from rag_core.storage.pgvector_store import PgVectorStore
from rag_core.types import SearchHit


class DenseRetriever:
    def __init__(self, store: PgVectorStore, embedder: EmbeddingProvider) -> None:
        self.store = store
        self.embedder = embedder

    def search(
        self,
        *,
        query: str,
        tenant_id: UUID,
        principals: list[str],
        k: int = 5,
        filters: dict | None = None,
    ) -> list[SearchHit]:
        if not query.strip():
            return []
        [vec] = self.embedder.encode([query])
        return self.store.dense_search(
            tenant_id=tenant_id,
            query_embedding=vec,
            principals=principals,
            k=k,
            filters=filters,
        )
