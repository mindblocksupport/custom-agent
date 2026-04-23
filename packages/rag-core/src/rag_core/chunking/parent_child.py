"""父子分级切分 (L37 §1 Q1, Day 12).

策略:
1. 一次切大块 (parents): target=1500 char ≈ 750 token, 一个小节大小
2. 在每个 parent 内部再切小块 (children): target=500 char ≈ 250 token, 检索打分用
3. children 的 parent_id = 对应 parent 的 ChunkSpan.seq

检索阶段: 命中 child → 取 parent content 入 prompt (用细粒度找, 用粗粒度读).
"""

from __future__ import annotations

from dataclasses import dataclass

from rag_core.chunking.recursive import ChunkSpan, RecursiveChunker


@dataclass(frozen=True)
class HierarchicalChunks:
    parents: list[ChunkSpan]
    children: list[ChunkSpan]
    # children[i].metadata["parent_seq"] = parents[j].seq 时, child 属于该 parent
    parent_of_child: dict[int, int]               # child.seq → parent.seq


class ParentChildChunker:
    def __init__(
        self,
        parent_target: int = 1500,
        parent_overlap: int = 0,
        child_target: int = 500,
        child_overlap: int = 50,
    ) -> None:
        self.parent = RecursiveChunker(parent_target, parent_overlap)
        self.child = RecursiveChunker(child_target, child_overlap)

    def split(self, text: str) -> HierarchicalChunks:
        parents = self.parent.split(text)
        children: list[ChunkSpan] = []
        parent_of_child: dict[int, int] = {}
        child_seq = 0
        for p in parents:
            sub = self.child.split(p.content)
            for s in sub:
                # 子块 offset 转回原文坐标
                child = ChunkSpan(
                    seq=child_seq,
                    content=s.content,
                    char_offset_start=p.char_offset_start + s.char_offset_start,
                    char_offset_end=p.char_offset_start + s.char_offset_end,
                    heading_path=p.heading_path,
                )
                children.append(child)
                parent_of_child[child_seq] = p.seq
                child_seq += 1
        return HierarchicalChunks(
            parents=parents,
            children=children,
            parent_of_child=parent_of_child,
        )
