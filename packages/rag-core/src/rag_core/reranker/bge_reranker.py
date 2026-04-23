"""bge-reranker-v2-m3 wrapper (生产路径).

模型: BAAI/bge-reranker-v2-m3 (cross-encoder, 中英双语)
首次使用从 HuggingFace 下载 (~2GB)。
要求: pip install rag-core[embed]   (sentence-transformers + torch)
"""

from __future__ import annotations

import os
from typing import Any

from rag_core.types import SearchHit


class BgeReranker:
    """sentence-transformers CrossEncoder 加载 bge-reranker-v2-m3."""

    def __init__(
        self,
        model_id: str = "BAAI/bge-reranker-v2-m3",
        device: str | None = None,
        cache_dir: str | None = None,
    ) -> None:
        self.model_id = model_id
        self.name = model_id.split("/")[-1].lower()
        self._device = device or os.environ.get("RAG_RERANK_DEVICE")
        self._cache_dir = cache_dir or os.environ.get("RAG_RERANK_CACHE")
        self._model: Any = None  # lazy

    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as e:
            raise RuntimeError(
                "sentence-transformers not installed. "
                "Run: uv pip install 'rag-core[embed]'"
            ) from e
        self._model = CrossEncoder(
            self.model_id, device=self._device, cache_folder=self._cache_dir,
        )
        return self._model

    def rerank(
        self,
        *,
        query: str,
        hits: list[SearchHit],
        top_k: int,
    ) -> list[SearchHit]:
        if not hits:
            return []
        model = self._load()
        pairs = [(query, h.chunk.content) for h in hits]
        # bge-reranker 输出 logits; activation_fct=None 时是 raw score
        # 用 sigmoid 归一化到 (0, 1) 方便阈值判断
        scores = model.predict(pairs, activation_fct=None)
        import math

        rescored = []
        for hit, raw in zip(hits, scores):
            sig = 1.0 / (1.0 + math.exp(-float(raw)))
            rescored.append(
                SearchHit(
                    chunk=hit.chunk,
                    score=sig,
                    source_uri=hit.source_uri,
                    title=hit.title,
                )
            )
        rescored.sort(key=lambda h: h.score, reverse=True)
        return rescored[:top_k]
