"""Reranker 抽象 (cross-encoder).

输入: query + 候选 hit 列表 (RRF 融合后, 默认 20)
输出: 按相关度重排后的 hit 列表 (score 替换为 cross-encoder 分数, 范围因模型而异)

实现:
- BgeReranker: BAAI/bge-reranker-v2-m3 (生产)
- HashReranker: 确定性 stub (CI / 单测)
"""

from __future__ import annotations

from typing import Protocol

from rag_core.types import SearchHit


class Reranker(Protocol):
    name: str

    def rerank(
        self,
        *,
        query: str,
        hits: list[SearchHit],
        top_k: int,
    ) -> list[SearchHit]: ...
