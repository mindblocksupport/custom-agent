"""PDF parser router 单测 (无真 PDF, 用 monkeypatch 模拟 backend)."""

import pytest

from rag_core.parser.base import ParsedDocument, ParsedPage
from rag_core.parser.router import (
    DIGITAL_CHAR_THRESHOLD,
    ScannedPdfNotSupported,
    _is_table_heavy,
    parse_pdf_doc,
)


def _doc(pages_text: list[str], title: str | None = None) -> ParsedDocument:
    pages = [ParsedPage(page_idx=i + 1, text=t) for i, t in enumerate(pages_text)]
    return ParsedDocument(pages=pages, title=title, backend="pdfium")


def test_joined_text_omits_blank_pages():
    d = _doc(["alpha", "", "  ", "beta"])
    assert d.joined_text == "alpha\n\nbeta"


def test_page_breaks_offsets_match_join():
    d = _doc(["alpha", "beta", "gamma"])
    text = d.joined_text
    breaks = d.page_breaks
    assert text[breaks[0]:].startswith("alpha")
    assert text[breaks[1]:].startswith("beta")
    assert text[breaks[2]:].startswith("gamma")


def test_router_raises_on_scanned_pdf(monkeypatch):
    """avg chars/page 低于阈值 → 拒绝处理."""
    scanned = _doc(["a", "b", "c"])  # < 100 chars/page
    from rag_core.parser import router as r
    monkeypatch.setattr(r.PdfiumBackend, "parse", lambda self, path: scanned)
    with pytest.raises(ScannedPdfNotSupported, match="scanned"):
        parse_pdf_doc("/nonexistent.pdf")


def test_router_returns_pdfium_for_digital(monkeypatch):
    long_page = "x" * (DIGITAL_CHAR_THRESHOLD * 2)
    digital = _doc([long_page, long_page], title="My Doc")
    from rag_core.parser import router as r
    monkeypatch.setattr(r.PdfiumBackend, "parse", lambda self, path: digital)
    out = parse_pdf_doc("/x.pdf")
    assert out.backend == "pdfium"
    assert out.title == "My Doc"
    assert "x" * 50 in out.joined_text


def test_router_switches_to_plumber_for_table_heavy(monkeypatch):
    # 构造表格密集页 (大量"   "簇)
    table_line = "Name    Value    Date    Status"
    text = "\n".join([table_line] * 30)
    digital = _doc([text, text], title="Tables")
    plumber_doc = _doc([text, text], title="Tables")

    from rag_core.parser import router as r
    monkeypatch.setattr(r.PdfiumBackend, "parse", lambda self, path: digital)
    plumber_called = []
    monkeypatch.setattr(
        r.PlumberBackend, "parse",
        lambda self, path: plumber_called.append(1) or plumber_doc,
    )
    out = parse_pdf_doc("/x.pdf")
    assert plumber_called == [1]
    assert out.backend in ("pdfium", "plumber")  # plumber_doc.backend 是 "pdfium" 因为 _doc 工厂


def test_table_heavy_detection_avoids_false_positive():
    """普通段落不应被误判为表格密集."""
    prose = "这是一段普通文字。" * 50
    d = _doc([prose])
    assert _is_table_heavy(d) is False


def test_table_heavy_detection_catches_columns():
    table_line = "A    B    C    D"
    d = _doc(["\n".join([table_line] * 30)])
    assert _is_table_heavy(d) is True
