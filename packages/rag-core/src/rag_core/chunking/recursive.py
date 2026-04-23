"""Recursive 切分 + Markdown header 边界 (Day 9 baseline).

策略:
1. 优先按 Markdown 标题切 (#, ##, ###) → 保持语义边界, 维护 heading_path
2. 标题块再按字符递归切 (target=1024 char ≈ 512 token, overlap=100 char ≈ 50 token)
3. 字符切按分隔符优先级递归: 段落 > 句号 > 空格

Day 12 替换为真 tokenizer 计数 + parent-child + Anthropic Contextual Chunking.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_MD_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# 段落分隔优先级 (越靠前越优先)
_SPLIT_SEPARATORS = ("\n\n", "\n", "。", "．", ". ", "? ", "! ", "; ", " ")


@dataclass(frozen=True)
class ChunkSpan:
    seq: int
    content: str
    char_offset_start: int
    char_offset_end: int
    heading_path: tuple[str, ...]

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class _Section:
    heading_path: tuple[str, ...]
    text: str
    offset: int


class RecursiveChunker:
    def __init__(self, target_chars: int = 1024, overlap_chars: int = 100) -> None:
        if target_chars <= 0 or overlap_chars < 0 or overlap_chars >= target_chars:
            raise ValueError(f"invalid sizes: target={target_chars} overlap={overlap_chars}")
        self.target = target_chars
        self.overlap = overlap_chars

    def split(self, text: str) -> list[ChunkSpan]:
        sections = self._split_by_markdown_headers(text)
        chunks: list[ChunkSpan] = []
        seq = 0
        for section in sections:
            for sub_text, sub_offset in self._split_section(section.text, section.offset):
                chunks.append(
                    ChunkSpan(
                        seq=seq,
                        content=sub_text,
                        char_offset_start=sub_offset,
                        char_offset_end=sub_offset + len(sub_text),
                        heading_path=section.heading_path,
                    )
                )
                seq += 1
        return chunks

    def _split_by_markdown_headers(self, text: str) -> list[_Section]:
        matches = list(_MD_HEADER_RE.finditer(text))
        if not matches:
            stripped = text.strip()
            if not stripped:
                return []
            offset = text.find(stripped)
            return [_Section(heading_path=(), text=stripped, offset=offset)]

        sections: list[_Section] = []
        path: list[str] = []

        # preamble
        if matches[0].start() > 0:
            preamble_raw = text[: matches[0].start()]
            preamble = preamble_raw.strip()
            if preamble:
                offset = text.find(preamble)
                sections.append(_Section(heading_path=(), text=preamble, offset=offset))

        for i, m in enumerate(matches):
            level = len(m.group(1))
            title = m.group(2).strip()
            path = path[: level - 1] + [title]
            body_start = m.end()
            body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            raw_body = text[body_start:body_end]
            stripped_left = raw_body.lstrip()
            body = stripped_left.rstrip()
            if body:
                leading = len(raw_body) - len(stripped_left)
                sections.append(
                    _Section(
                        heading_path=tuple(path),
                        text=body,
                        offset=body_start + leading,
                    )
                )
        return sections

    def _split_section(self, text: str, base_offset: int) -> list[tuple[str, int]]:
        """递归字符切. 短于 target 直接返回, 否则按分隔符递归; 都不行则硬切."""
        if len(text) <= self.target:
            return [(text, base_offset)]

        sep = next((s for s in _SPLIT_SEPARATORS if s in text), None)

        if sep is None:
            # 无分隔符: 硬切 (overlap 滑窗)
            step = max(1, self.target - self.overlap)
            return [
                (text[i : i + self.target], base_offset + i)
                for i in range(0, len(text), step)
            ]

        # 按 sep 拆 (跟踪 offset)
        pieces: list[tuple[str, int]] = []
        cursor = 0
        for piece in text.split(sep):
            pieces.append((piece, base_offset + cursor))
            cursor += len(piece) + len(sep)

        # 每段过大就递归
        refined: list[tuple[str, int]] = []
        for piece, off in pieces:
            if not piece:
                continue
            if len(piece) > self.target:
                refined.extend(self._split_section(piece, off))
            else:
                refined.append((piece, off))

        if not refined:
            return []

        # 贪心合并相邻短段, 带 overlap
        out: list[tuple[str, int]] = []
        cur_text, cur_off = refined[0]
        for piece, off in refined[1:]:
            proposed = cur_text + sep + piece
            if len(proposed) <= self.target:
                cur_text = proposed
            else:
                out.append((cur_text, cur_off))
                # overlap: 把上块尾部 overlap 字符塞到本块开头
                if self.overlap > 0 and len(cur_text) > self.overlap:
                    tail = cur_text[-self.overlap :]
                    cur_text = tail + sep + piece
                    cur_off = off - (len(tail) + len(sep))
                else:
                    cur_text, cur_off = piece, off
        out.append((cur_text, cur_off))
        return out


def chunk_text(text: str, target_chars: int = 1024, overlap_chars: int = 100) -> list[ChunkSpan]:
    return RecursiveChunker(target_chars, overlap_chars).split(text)
