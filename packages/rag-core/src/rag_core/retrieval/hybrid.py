"""HybridRetriever: BM25 + Dense + RRF + (可选) Rerank + 拒答阈值.

L37 §1 Q2 + §8.4: 三路混合是召回质量的"地基", rerank 是精排.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from rag_core.embedding.base import EmbeddingProvider
from rag_core.reranker.base import Reranker
from rag_core.retrieval.bm25 import BM25Retriever
from rag_core.retrieval.dense import DenseRetriever
from rag_core.retrieval.rrf import rrf_fuse
from rag_core.storage.pgvector_store import PgVectorStore
from rag_core.types import SearchHit


@dataclass
class HybridSearchResult:
    """检索返回结果, 含拒答标记."""

    hits: list[SearchHit]
    refused: bool = False                 # rerank top1 < threshold
    refusal_reason: str | None = None
    n_dense: int = 0
    n_bm25: int = 0
    n_rerank_in: int = 0


class HybridRetriever:
    def __init__(
        self,
        store: PgVectorStore,
        embedder: EmbeddingProvider,
        *,
        reranker: Reranker | None = None,
        rrf_k: int = 60,
        candidate_pool: int = 20,         # 召回池大小 (rerank 输入)
        refusal_threshold: float = 0.3,   # rerank top1 阈值
        enrich_parents: bool = True,      # Day 12: 命中子块时取父块进 prompt
    ) -> None:
        self.store = store
        self.dense = DenseRetriever(store, embedder)
        self.bm25 = BM25Retriever(store)
        self.reranker = reranker
        self.rrf_k = rrf_k
        self.candidate_pool = candidate_pool
        self.refusal_threshold = refusal_threshold
        self.enrich_parents = enrich_parents

    def _enrich_parents(self, hits: list[SearchHit]) -> list[SearchHit]:
        """命中子块 → 取父块 content 填进 SearchHit.parent_content."""
        if not self.enrich_parents or not hits:
            return hits
        ids = [h.chunk.id for h in hits if h.chunk.id is not None]
        try:
            parent_map = self.store.fetch_parents(ids)
        except AttributeError:
            return hits
        out = []
        for h in hits:
            pc = parent_map.get(h.chunk.id) if h.chunk.id else None
            out.append(h.model_copy(update={"parent_content": pc}) if pc else h)
        return out

    def search(
        self,
        *,
        query: str,
        tenant_id: UUID,
        principals: list[str],
        k: int = 5,
        filters: dict | None = None,
        collection: str | None = None,         # v1.5: workspace/skill 默认 KB
    ) -> HybridSearchResult:
        # 1. 三路并行召回 (Day 10 串行, Day 12 改 asyncio.gather)
        dense_hits = self.dense.search(
            query=query, tenant_id=tenant_id, principals=principals,
            k=self.candidate_pool, filters=filters, collection=collection,
        )
        bm25_hits = self.bm25.search(
            query=query, tenant_id=tenant_id, principals=principals,
            k=self.candidate_pool, filters=filters, collection=collection,
        )

        # 2. RRF 融合
        fused = rrf_fuse([dense_hits, bm25_hits], k=self.rrf_k, top_n=self.candidate_pool)

        if not fused:
            return HybridSearchResult(
                hits=[], refused=True, refusal_reason="no_candidates",
                n_dense=len(dense_hits), n_bm25=len(bm25_hits), n_rerank_in=0,
            )

        # 3. (可选) rerank
        if self.reranker is None:
            return HybridSearchResult(
                hits=self._enrich_parents(fused[:k]),
                n_dense=len(dense_hits), n_bm25=len(bm25_hits), n_rerank_in=len(fused),
            )

        reranked = self.reranker.rerank(query=query, hits=fused, top_k=k)

        # 4. 拒答阈值: rerank top1 score < threshold → 拒答
        if not reranked or reranked[0].score < self.refusal_threshold:
            return HybridSearchResult(
                hits=[], refused=True,
                refusal_reason=f"top1_score={reranked[0].score if reranked else 0:.3f} < {self.refusal_threshold}",
                n_dense=len(dense_hits), n_bm25=len(bm25_hits), n_rerank_in=len(fused),
            )

        return HybridSearchResult(
            hits=self._enrich_parents(reranked),
            n_dense=len(dense_hits), n_bm25=len(bm25_hits), n_rerank_in=len(fused),
        )
