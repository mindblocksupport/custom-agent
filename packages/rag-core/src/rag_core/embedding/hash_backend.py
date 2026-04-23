"""HashEmbedding: 确定性、无依赖 embedding (CI / 单测 / 冷启动)。

不要在生产用; 它只对完全相同的字符串返回相同向量 (语义无关)。
但能让 ingest pipeline / pgvector store 跑通, 验证管路。
"""

from __future__ import annotations

import hashlib
import math


class HashEmbedding:
    name = "hash-1024-v1"
    dimension = 1024

    def __init__(self, dimension: int = 1024) -> None:
        self.dimension = dimension

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        # 用 sha256 derive 多个种子, 填满 dimension
        seeds_needed = (self.dimension * 4) // 32 + 1  # 每 sha256 出 32 字节, 每 4 字节做一个 float
        buf = b""
        seed = text.encode("utf-8")
        for i in range(seeds_needed):
            seed = hashlib.sha256(seed + i.to_bytes(2, "big")).digest()
            buf += seed
        # 取前 dimension*4 字节, 拆成 float (映射到 [-1, 1])
        vec: list[float] = []
        for i in range(self.dimension):
            chunk = buf[i * 4 : i * 4 + 4]
            # 映射到 [-1, 1]
            ival = int.from_bytes(chunk, "big", signed=False)
            vec.append((ival / 0xFFFFFFFF) * 2.0 - 1.0)
        # L2 归一化 (cosine 相似度需要)
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]
