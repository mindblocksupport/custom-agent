"""HashReranker 测试 (无 ML 依赖)."""

from uuid import UUID

from rag_core.reranker.hash_backend import HashReranker
from rag_core.types import Chunk, SearchHit

T = UUID("00000000-0000-0000-0000-000000000001")
D = UUID("00000000-0000-0000-0000-000000000002")


def _hit(content: str, score: float = 0.5) -> SearchHit:
    return SearchHit(
        chunk=Chunk(
            id=UUID("00000000-0000-0000-0000-00000000beef"),
            doc_id=D,
            tenant_id=T,
            chunk_seq=0,
            doc_version=1,
            content=content,
            content_hash="0" * 64,
        ),
        score=score,
    )


def test_rerank_returns_top_k():
    rr = HashReranker()
    hits = [_hit(f"chunk {i}") for i in range(10)]
    out = rr.rerank(query="q", hits=hits, top_k=3)
    assert len(out) == 3


def test_rerank_scores_in_unit_interval():
    rr = HashReranker()
    hits = [_hit("a"), _hit("b")]
    out = rr.rerank(query="q", hits=hits, top_k=2)
    assert all(0.0 <= h.score <= 1.0 for h in out)


def test_rerank_empty():
    assert HashReranker().rerank(query="q", hits=[], top_k=5) == []


def test_rerank_deterministic():
    rr = HashReranker()
    hits = [_hit(f"c{i}") for i in range(5)]
    a = rr.rerank(query="same", hits=hits, top_k=5)
    b = rr.rerank(query="same", hits=hits, top_k=5)
    assert [h.chunk.content for h in a] == [h.chunk.content for h in b]
