"""Multi-Query Retrieval: 一个 query 改写 N 条变体, 各路召回 → RRF 融合.

对模糊/歧义 query 有效 (比如"部署", 可能是 k8s/docker/bare-metal).
成本: 1 次 LLM 改写 + N 次检索.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from rag_core.llm.base import LLMClient
from rag_core.retrieval.hybrid import HybridRetriever, HybridSearchResult
from rag_core.retrieval.rrf import rrf_fuse
from rag_core.types import SearchHit

DEFAULT_MODEL = "deepseek/deepseek-chat"

_MULTIQUERY_PROMPT = """Rewrite the following search query into {n} DIFFERENT alternative phrasings
that someone might use to search for the same information.
Output one rewrite per line, no numbering, no preamble.

Original query: {query}

Rewrites:"""


@dataclass
class MultiQueryRetriever:
    """用 LLM 生成 N 条变体 query, 并行召回后用 RRF 融合."""

    base: HybridRetriever
    llm: LLMClient
    model: str = DEFAULT_MODEL
    num_variants: int = 3
    rrf_k: int = 60

    async def search(
        self,
        *,
        query: str,
        tenant_id: UUID,
        principals: list[str],
        k: int = 5,
        filters: dict | None = None,
    ) -> HybridSearchResult:
        resp = await self.llm.complete(
            messages=[{"role": "user", "content": _MULTIQUERY_PROMPT.format(
                query=query, n=self.num_variants)}],
            model=self.model, max_tokens=256, temperature=0.0,
        )
        variants = [line.strip() for line in resp.text.splitlines() if line.strip()]
        variants = variants[: self.num_variants]
        # 原 query 也纳入 (永远包含原始意图)
        all_queries = [query] + variants

        # 并行 (Day 12 简化: 串行; Day 13 asyncio.gather + to_thread)
        all_hits: list[list[SearchHit]] = []
        aggregated: HybridSearchResult | None = None
        for q in all_queries:
            res = self.base.search(
                query=q, tenant_id=tenant_id, principals=principals,
                k=self.base.candidate_pool, filters=filters,
            )
            all_hits.append(res.hits)
            if aggregated is None:
                aggregated = res

        fused = rrf_fuse(all_hits, k=self.rrf_k, top_n=k)
        assert aggregated is not None
        return HybridSearchResult(
            hits=fused,
            refused=aggregated.refused and not fused,
            refusal_reason=aggregated.refusal_reason if not fused else None,
            n_dense=aggregated.n_dense,
            n_bm25=aggregated.n_bm25,
            n_rerank_in=aggregated.n_rerank_in,
        )
