"""PDF 解析路由 (Day 3 P0 #2 Stage 1).

策略 (调研报告 §2):
1. 先用 pypdfium2 抽前 N 页, 算 avg char/页
2. >= 阈值 = 数字 PDF → pypdfium2 全文 (默认), 表格密集再 fallback plumber
3. <  阈值 = 扫描件 → 抛 ScannedPdfNotSupported, 提示走 Stage 2 (PaddleOCR-VL)

入口: parse_pdf(path) → (text, title)
后续 Stage 2 加 PaddleOCRBackend, router 自动接.
"""

from __future__ import annotations

import logging
from pathlib import Path

from rag_core.parser.base import ParsedDocument
from rag_core.parser.pdfium_backend import PdfiumBackend
from rag_core.parser.plumber_backend import PlumberBackend

logger = logging.getLogger(__name__)

DIGITAL_CHAR_THRESHOLD = 100             # avg chars/page < 100 视为扫描件
DETECT_SAMPLE_PAGES = 3
TABLE_DENSITY_THRESHOLD = 2              # 数字 PDF 平均每页 ≥ 2 表 → 切 plumber


class ScannedPdfNotSupported(NotImplementedError):
    """检测到扫描件 PDF; Stage 2 (PaddleOCR-VL) 才支持."""


def _avg_chars_per_page(doc: ParsedDocument, sample: int = DETECT_SAMPLE_PAGES) -> float:
    pages = doc.pages[:sample] if doc.pages else []
    if not pages:
        return 0.0
    return sum(len(p.text) for p in pages) / len(pages)


def parse_pdf(path: Path) -> tuple[str, str | None]:
    """主入口: 数字 PDF → (joined_text, title). 扫描件抛 ScannedPdfNotSupported."""
    doc = parse_pdf_doc(path)
    return doc.joined_text, doc.title


def parse_pdf_doc(path: Path) -> ParsedDocument:
    """完整版: 返回 ParsedDocument (含 page_breaks 用于 page 反查)."""
    pdfium = PdfiumBackend()
    pdfium_doc = pdfium.parse(path)

    if not pdfium_doc.pages:
        raise ValueError(f"empty PDF: {path}")

    avg = _avg_chars_per_page(pdfium_doc)
    if avg < DIGITAL_CHAR_THRESHOLD:
        raise ScannedPdfNotSupported(
            f"PDF appears to be scanned (avg {avg:.0f} chars/page in first "
            f"{DETECT_SAMPLE_PAGES} pages, threshold {DIGITAL_CHAR_THRESHOLD}). "
            f"Stage 2 PaddleOCR-VL backend not yet wired."
        )

    # 表格密集 → plumber 重抽 (慢, 但表格保真)
    # 数字 PDF + 简单文本 → 直接用 pdfium 结果
    # 检测启发式: 看文本里有多少疑似表格行 (含多个连续空格 / 制表符)
    if _is_table_heavy(pdfium_doc):
        try:
            logger.info("PDF table-dense, switching to plumber backend: %s", path)
            return PlumberBackend().parse(path)
        except Exception as e:
            logger.warning("plumber backend failed (%s); falling back to pdfium", e)
    return pdfium_doc


def _is_table_heavy(doc: ParsedDocument) -> bool:
    """启发式: 文本里 >20% 行含 ≥3 个'空白簇' 视为表格密集."""
    suspicious_lines = 0
    total_lines = 0
    for p in doc.pages[:DETECT_SAMPLE_PAGES]:
        for line in p.text.splitlines():
            line = line.strip()
            if not line:
                continue
            total_lines += 1
            # 数 "  " (>=2 空格) 簇
            cluster_count = 0
            in_cluster = False
            spaces = 0
            for ch in line:
                if ch in (" ", "\t"):
                    spaces += 1
                    if spaces >= 2 and not in_cluster:
                        cluster_count += 1
                        in_cluster = True
                else:
                    spaces = 0
                    in_cluster = False
            if cluster_count >= 3:
                suspicious_lines += 1
    if total_lines == 0:
        return False
    return suspicious_lines / total_lines > 0.20
