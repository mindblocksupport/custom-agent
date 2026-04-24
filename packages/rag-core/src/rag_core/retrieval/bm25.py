"""BM25 检索器 (Postgres ts_rank + jieba 预切分)."""

from __future__ import annotations

from uuid import UUID

from rag_core.storage.pgvector_store import PgVectorStore
from rag_core.tokenize.jieba_tokenizer import expand_query_with_synonyms
from rag_core.types import SearchHit


class BM25Retriever:
    def __init__(self, store: PgVectorStore, *, expand_synonyms: bool = True) -> None:
        self.store = store
        self.expand_synonyms = expand_synonyms

    def search(
        self,
        *,
        query: str,
        tenant_id: UUID,
        principals: list[str],
        k: int = 5,
        filters: dict | None = None,
        collection: str | None = None,
    ) -> list[SearchHit]:
        if not query.strip():
            return []
        from rag_core.tokenize.jieba_tokenizer import tokenize_for_bm25
        tokens = (
            expand_query_with_synonyms(query)
            if self.expand_synonyms
            else tokenize_for_bm25(query)
        )
        if not tokens:
            return []
        return self.store.bm25_search(
            tenant_id=tenant_id,
            query_tokens=tokens,
            principals=principals,
            k=k,
            filters=filters,
            collection=collection,
        )
