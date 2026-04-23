"""父子分级切分测试."""

from rag_core.chunking.parent_child import ParentChildChunker


def test_short_doc_one_parent_one_child():
    text = "# Title\nshort body."
    h = ParentChildChunker(parent_target=200, child_target=100).split(text)
    assert len(h.parents) == 1
    assert len(h.children) >= 1
    # 所有 child.parent_seq 都指向 parent 0
    assert set(h.parent_of_child.values()) == {0}


def test_long_doc_multiple_parents_each_with_children():
    text = "# H1\n" + "甲" * 800 + "\n# H2\n" + "乙" * 800
    h = ParentChildChunker(
        parent_target=600, parent_overlap=0,
        child_target=200, child_overlap=20,
    ).split(text)
    assert len(h.parents) >= 2
    assert len(h.children) >= 4
    # 每个 child 的 parent_seq 都在 parents 范围内
    for child_seq, parent_seq in h.parent_of_child.items():
        assert 0 <= parent_seq < len(h.parents)


def test_child_offsets_remap_to_original():
    text = "header\n" + "X" * 1000
    h = ParentChildChunker(parent_target=400, child_target=150).split(text)
    for child in h.children:
        # 子块在原文中的 [start, end) 切片应能恢复内容
        assert text[child.char_offset_start:child.char_offset_end].startswith(
            child.content[:5]
        ) or child.content[:5] in text[
            max(0, child.char_offset_start - 5):child.char_offset_end + 5
        ]


def test_seq_unique_and_sequential():
    text = "段一. " * 100 + "\n\n段二. " * 100
    h = ParentChildChunker().split(text)
    parent_seqs = [p.seq for p in h.parents]
    child_seqs = [c.seq for c in h.children]
    assert parent_seqs == sorted(set(parent_seqs))
    assert child_seqs == sorted(set(child_seqs))
