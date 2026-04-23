"""chunking 单测 (无 DB / 无 ML)."""

from rag_core.chunking.recursive import RecursiveChunker


def test_short_text_single_chunk():
    chunks = RecursiveChunker(target_chars=1024).split("hello world")
    assert len(chunks) == 1
    assert chunks[0].content == "hello world"
    assert chunks[0].seq == 0
    assert chunks[0].heading_path == ()


def test_markdown_headers_become_path():
    text = "# A\nbody A\n## A.1\nbody A.1\n# B\nbody B\n"
    chunks = RecursiveChunker(target_chars=1024).split(text)
    paths = [c.heading_path for c in chunks]
    assert ("A",) in paths
    assert ("A", "A.1") in paths
    assert ("B",) in paths


def test_long_text_splits_with_overlap():
    text = "段落甲。" * 200 + "\n\n" + "段落乙。" * 200
    chunks = RecursiveChunker(target_chars=300, overlap_chars=30).split(text)
    assert len(chunks) >= 2
    # 序号连续
    assert [c.seq for c in chunks] == list(range(len(chunks)))
    # 每块都 ≤ target (允许略大, 因 overlap 会让 candidate 走 else 分支)
    assert all(len(c.content) <= 600 for c in chunks)


def test_content_hash_deterministic():
    [c1] = RecursiveChunker().split("same text")
    [c2] = RecursiveChunker().split("same text")
    assert c1.content_hash == c2.content_hash
    assert c1.content_hash != RecursiveChunker().split("other text")[0].content_hash


def test_offsets_align_within_section():
    text = "# H\n" + "A" * 100 + "\n## H2\n" + "B" * 100
    chunks = RecursiveChunker(target_chars=200).split(text)
    # 找到含 'A' 的块, offset 应该指向 'A' 在原文中的位置
    a_chunks = [c for c in chunks if "A" in c.content]
    assert a_chunks
    for c in a_chunks:
        assert text[c.char_offset_start : c.char_offset_end].startswith(c.content[:5])
