"""Reciprocal Rank Fusion (Cormack et al., 2009).

公式: score(d) = Σ 1 / (k + rank_i(d))   k 默认 60

特点:
- 对各路打分尺度无关 (只看 rank, 不看 score) → 适合融合 BM25 + dense
- 缺席某路按"无穷远 rank"算, 默认贡献 0
- k 越小越偏向 top-rank 文档, k=60 是 RRF 论文推荐值
"""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from rag_core.types import SearchHit


def rrf_fuse(
    rankings: Iterable[list[SearchHit]],
    k: int = 60,
    top_n: int | None = None,
) -> list[SearchHit]:
    """融合多路检索结果, 返回按 RRF 分数降序的新 SearchHit 列表.

    每个 chunk_id 取第一次出现时的 SearchHit 作为代表,
    新 SearchHit.score 替换为 RRF 分数 (注: 与原 dense/bm25 score 不可比)。

    Args:
        rankings: 多个排序结果, e.g. [bm25_hits, dense_hits]
        k: RRF 平滑常数 (默认 60)
        top_n: 限制输出数量 (None = 全部)
    """
    rrf_scores: dict[UUID, float] = {}
    representatives: dict[UUID, SearchHit] = {}

    for ranking in rankings:
        for rank, hit in enumerate(ranking, start=1):
            assert hit.chunk.id is not None, "RRF requires persisted chunks (with id)"
            chunk_id = hit.chunk.id
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
            if chunk_id not in representatives:
                representatives[chunk_id] = hit

    fused = [
        SearchHit(
            chunk=representatives[cid].chunk,
            score=score,
            source_uri=representatives[cid].source_uri,
            title=representatives[cid].title,
        )
        for cid, score in rrf_scores.items()
    ]
    fused.sort(key=lambda h: h.score, reverse=True)
    return fused[:top_n] if top_n else fused
