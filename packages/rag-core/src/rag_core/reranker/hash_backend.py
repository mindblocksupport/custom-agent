"""HashReranker: 确定性 stub for CI / 单测.

策略: 用 hash embedding 算 cosine, 当成"reranker score" (0-1)。
- 满足 Reranker 协议
- 不依赖任何 ML 包
- 注: 真实 reranker 用 cross-encoder; 这里只是确定性回退
"""

from __future__ import annotations

from rag_core.embedding.hash_backend import HashEmbedding
from rag_core.types import SearchHit


class HashReranker:
    name = "hash-reranker-v1"

    def __init__(self) -> None:
        self._emb = HashEmbedding()

    def rerank(
        self,
        *,
        query: str,
        hits: list[SearchHit],
        top_k: int,
    ) -> list[SearchHit]:
        if not hits:
            return []
        [qv] = self._emb.encode([query])
        chunk_vecs = self._emb.encode([h.chunk.content for h in hits])
        rescored = []
        for hit, vec in zip(hits, chunk_vecs):
            cos = sum(a * b for a, b in zip(qv, vec))
            # 把 cos∈[-1,1] 映射到 [0,1] 当 reranker score
            score = (cos + 1.0) / 2.0
            rescored.append(
                SearchHit(
                    chunk=hit.chunk,
                    score=score,
                    source_uri=hit.source_uri,
                    title=hit.title,
                )
            )
        rescored.sort(key=lambda h: h.score, reverse=True)
        return rescored[:top_k]
