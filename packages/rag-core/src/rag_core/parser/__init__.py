"""PDF / 文档解析 (Day 3 P0 #2 Stage 1).

License 严格回避 AGPL/GPL:
- pypdfium2 (Apache 2.0) → 数字 PDF 文本提取, 默认
- pdfplumber  (MIT)        → 表格密集页可选 fallback
- PaddleOCR-VL Stage 2 (Apache 2.0) → 扫描件, 留待 GPU 部署上线

主入口: parse_pdf(path) -> (text, title)
"""

from rag_core.parser.base import ParsedDocument, ParsedPage, PDFParser
from rag_core.parser.router import parse_pdf

__all__ = ["ParsedDocument", "ParsedPage", "PDFParser", "parse_pdf"]
