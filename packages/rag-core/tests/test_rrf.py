"""RRF fusion 单测."""

from uuid import UUID

from rag_core.retrieval.rrf import rrf_fuse
from rag_core.types import Chunk, SearchHit

T = UUID("00000000-0000-0000-0000-000000000001")
D = UUID("00000000-0000-0000-0000-000000000002")


def _hit(cid: str, score: float = 0.5) -> SearchHit:
    chunk = Chunk(
        id=UUID(cid),
        doc_id=D,
        tenant_id=T,
        chunk_seq=0,
        doc_version=1,
        content="x",
        content_hash="0" * 64,
    )
    return SearchHit(chunk=chunk, score=score)


def test_rrf_single_ranking():
    a, b, c = _hit("00000000-0000-0000-0000-00000000aaaa"), \
              _hit("00000000-0000-0000-0000-00000000bbbb"), \
              _hit("00000000-0000-0000-0000-00000000cccc")
    fused = rrf_fuse([[a, b, c]], k=60)
    assert [h.chunk.id for h in fused] == [a.chunk.id, b.chunk.id, c.chunk.id]
    # k=60, ranks 1/2/3 → 1/61, 1/62, 1/63
    assert abs(fused[0].score - 1 / 61) < 1e-9
    assert abs(fused[1].score - 1 / 62) < 1e-9


def test_rrf_two_rankings_overlap_boost():
    """两路都排第一的 doc 应该胜过只有一路命中的 doc."""
    a = _hit("00000000-0000-0000-0000-0000000000aa")  # 两路都中
    b = _hit("00000000-0000-0000-0000-0000000000bb")  # 只 BM25 中
    c = _hit("00000000-0000-0000-0000-0000000000cc")  # 只 dense 中
    bm25 = [a, b]
    dense = [a, c]
    fused = rrf_fuse([bm25, dense], k=60)
    ids = [h.chunk.id for h in fused]
    assert ids[0] == a.chunk.id  # a 双路命中胜出


def test_rrf_top_n_limit():
    hits = [_hit(f"00000000-0000-0000-0000-00000000000{i}") for i in range(5)]
    fused = rrf_fuse([hits], k=60, top_n=3)
    assert len(fused) == 3


def test_rrf_empty():
    assert rrf_fuse([], k=60) == []
    assert rrf_fuse([[], []], k=60) == []
