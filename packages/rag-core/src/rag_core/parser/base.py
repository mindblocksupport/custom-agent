"""PDF parser 抽象类型.

ParsedPage 携带 page_idx (1-based) + text, 上层 chunking 可借此填 Chunk.page.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class ParsedPage:
    """单页解析结果."""

    page_idx: int                         # 1-based, 与 PDF 阅读器一致
    text: str
    tables_md: list[str] = field(default_factory=list)   # 可选: markdown 表格


@dataclass(frozen=True)
class ParsedDocument:
    """整 PDF 解析结果."""

    pages: list[ParsedPage]
    title: str | None = None
    backend: str = ""                     # 'pdfium' / 'plumber' / 'paddleocr'

    @property
    def joined_text(self) -> str:
        """全文 (页间用空行分隔)."""
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    @property
    def page_breaks(self) -> list[int]:
        """每页起始的全文 char offset (用于 offset → page_idx 反查)."""
        breaks: list[int] = []
        cursor = 0
        for p in self.pages:
            if not p.text.strip():
                continue
            breaks.append(cursor)
            cursor += len(p.text) + len("\n\n")  # 加上 join 分隔符
        return breaks


class PDFParser(Protocol):
    name: str

    def parse(self, path: Path) -> ParsedDocument: ...
