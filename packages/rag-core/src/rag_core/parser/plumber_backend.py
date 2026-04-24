"""pdfplumber backend (MIT).

适合表格密集 PDF: pdfplumber 的 extract_tables() 是数字 PDF 表格之王.
开销比 pdfium 大 (~3-5x), 默认不用; 仅在 router 检测到表格密集时切.

要求: pip install rag-core[pdf]
"""

from __future__ import annotations

from pathlib import Path

from rag_core.parser.base import ParsedDocument, ParsedPage


def _table_to_markdown(rows: list[list[str | None]]) -> str:
    """list[list[cell]] → markdown table. None cell → 空格."""
    if not rows:
        return ""
    norm = [[(c or "").strip() for c in r] for r in rows]
    width = max(len(r) for r in norm)
    norm = [r + [""] * (width - len(r)) for r in norm]
    header = "| " + " | ".join(norm[0]) + " |"
    sep = "| " + " | ".join("---" for _ in range(width)) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in norm[1:])
    return f"{header}\n{sep}\n{body}".rstrip()


class PlumberBackend:
    name = "plumber"

    def parse(self, path: Path) -> ParsedDocument:
        try:
            import pdfplumber
        except ImportError as e:
            raise RuntimeError(
                "pdfplumber not installed. Run: uv pip install 'rag-core[pdf]'"
            ) from e

        pages: list[ParsedPage] = []
        title: str | None = None
        with pdfplumber.open(str(path)) as pdf:
            meta = pdf.metadata or {}
            t = meta.get("Title") or meta.get("title")
            if isinstance(t, str) and t.strip():
                title = t.strip()
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                tables = page.extract_tables() or []
                tables_md = [_table_to_markdown(t) for t in tables if t]
                pages.append(ParsedPage(
                    page_idx=i + 1,
                    text=text,
                    tables_md=[m for m in tables_md if m],
                ))
        return ParsedDocument(pages=pages, title=title, backend=self.name)
