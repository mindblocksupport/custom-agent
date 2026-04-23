"""Qwen3-Embedding 自托管 wrapper.

Day 9: sentence-transformers 本地加载 (CPU/MPS/CUDA 自适应)
Day 14+: vLLM 服务化, 通过 HTTP 调用

模型权重首次使用时从 HuggingFace 自动下载 (~1.2GB for 0.6B)。
要求: pip install rag-core[embed]
"""

from __future__ import annotations

import os
from typing import Any


class Qwen3Embedding:
    """sentence-transformers 加载 Qwen3-Embedding-0.6B (默认) 或 4B."""

    def __init__(
        self,
        model_id: str = "Qwen/Qwen3-Embedding-0.6B",
        device: str | None = None,
        cache_dir: str | None = None,
    ) -> None:
        self.model_id = model_id
        self.name = self._derive_name(model_id)
        self._device = device or os.environ.get("RAG_EMBED_DEVICE")
        self._cache_dir = cache_dir or os.environ.get("RAG_EMBED_CACHE")
        self._model: Any = None    # lazy load (避免 import 时下载权重)
        self.dimension = 1024 if "0.6B" in model_id else 2560

    @staticmethod
    def _derive_name(model_id: str) -> str:
        # 把 'Qwen/Qwen3-Embedding-0.6B' 转成 'qwen3-0.6b-v1'
        tail = model_id.split("/")[-1].lower()
        return tail.replace("qwen3-embedding-", "qwen3-") + "-v1"

    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise RuntimeError(
                "sentence-transformers not installed. "
                "Run: uv pip install 'rag-core[embed]'"
            ) from e
        self._model = SentenceTransformer(
            self.model_id,
            device=self._device,
            cache_folder=self._cache_dir,
        )
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load()
        # sentence-transformers 默认已 normalize
        vecs = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return vecs.tolist()
