"""pypdfium2 backend (Apache 2.0).

数字 PDF 的默认 backend. 比 PaddleOCR 快 100-500 倍, 大部分企业语料够用.
扫描件文本量低 → router 会切到 PaddleOCR (Stage 2).

要求: pip install rag-core[pdf]
"""

from __future__ import annotations

from pathlib import Path

from rag_core.parser.base import ParsedDocument, ParsedPage


class PdfiumBackend:
    name = "pdfium"

    def parse(self, path: Path) -> ParsedDocument:
        try:
            import pypdfium2 as pdfium
        except ImportError as e:
            raise RuntimeError(
                "pypdfium2 not installed. Run: uv pip install 'rag-core[pdf]'"
            ) from e

        pages: list[ParsedPage] = []
        title: str | None = None
        pdf = pdfium.PdfDocument(str(path))
        try:
            meta = self._extract_title(pdf)
            if meta:
                title = meta
            for i in range(len(pdf)):
                page = pdf[i]
                try:
                    text_page = page.get_textpage()
                    try:
                        text = text_page.get_text_range() or ""
                    finally:
                        text_page.close()
                finally:
                    page.close()
                pages.append(ParsedPage(page_idx=i + 1, text=text))
        finally:
            pdf.close()

        # 标题兜底: 第一页第一行 (清掉超长项)
        if not title and pages:
            for line in pages[0].text.splitlines():
                line = line.strip()
                if 3 <= len(line) <= 120:
                    title = line
                    break

        return ParsedDocument(pages=pages, title=title, backend=self.name)

    @staticmethod
    def _extract_title(pdf) -> str | None:
        """从 PDF metadata 拿 Title (经常是空的)."""
        try:
            meta = pdf.get_metadata_dict() or {}
            t = meta.get("Title") or meta.get("title")
            return t.strip() if isinstance(t, str) and t.strip() else None
        except Exception:
            return None
