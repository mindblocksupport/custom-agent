"""Embedding 抽象 (允许 hash-backend 在 CI 跑、Qwen3 在生产跑)."""

from __future__ import annotations

from typing import Protocol


class EmbeddingProvider(Protocol):
    """Day 9 baseline 接口.

    生产实现: Qwen3Embedding (sentence-transformers)
    测试实现: HashEmbedding (无 ML 依赖, 确定性)
    """

    name: str          # 模型版本字符串 (写入 rag_chunks.embedding_model_version)
    dimension: int     # 1024 for 0.6B, 2560 for 4B

    def encode(self, texts: list[str]) -> list[list[float]]: ...
