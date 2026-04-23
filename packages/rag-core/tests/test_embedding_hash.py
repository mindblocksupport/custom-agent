"""HashEmbedding 确定性测试 (CI 不需要 GPU)."""

import math

from rag_core.embedding.hash_backend import HashEmbedding


def test_dimension():
    emb = HashEmbedding()
    [v] = emb.encode(["hello"])
    assert len(v) == emb.dimension == 1024


def test_deterministic():
    emb = HashEmbedding()
    [v1] = emb.encode(["same input"])
    [v2] = emb.encode(["same input"])
    assert v1 == v2


def test_different_inputs_differ():
    emb = HashEmbedding()
    [v1] = emb.encode(["A"])
    [v2] = emb.encode(["B"])
    # 任意维度上有差异
    assert any(abs(a - b) > 1e-6 for a, b in zip(v1, v2))


def test_normalized():
    emb = HashEmbedding()
    [v] = emb.encode(["normalize me"])
    norm = math.sqrt(sum(x * x for x in v))
    assert abs(norm - 1.0) < 1e-6


def test_batch():
    emb = HashEmbedding()
    out = emb.encode(["a", "b", "c"])
    assert len(out) == 3 and all(len(v) == 1024 for v in out)
