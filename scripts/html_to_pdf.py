#!/usr/bin/env python3
"""HTML → PDF (用 WeasyPrint, 支持中文 + 自动分页 + 目录).

Usage:
    python3 scripts/html_to_pdf.py docs/rag-knowledge-map.html docs/rag-knowledge-map.pdf
"""

import re
import sys
from pathlib import Path

from weasyprint import HTML


def prepare_html_for_pdf(html: str) -> str:
    """修改 HTML 使其适合 PDF 输出 (去 JS, 改布局, 加打印样式)."""

    # 1. 去掉 Mermaid JS (PDF 不支持动态渲染, 保留 pre 代码块作为文本)
    html = re.sub(
        r'<script\s+src="https://cdn\.jsdelivr\.net/npm/mermaid[^"]*"></script>',
        "",
        html,
    )
    # 去掉 mermaid.initialize 和其他 JS
    html = re.sub(r"<script>[\s\S]*?</script>", "", html)

    # 2. 去掉发音按钮 (PDF 不能点)
    html = re.sub(r'<button class="speak-btn"[^>]*>🔊</button>', "", html)

    # 3. 去掉 progress bar
    html = re.sub(
        r'<div class="progress">.*?</div>', "", html, flags=re.DOTALL
    )

    # 4. 注入 PDF 专用打印样式
    pdf_css = """
<style>
@page {
    size: A4;
    margin: 2cm 1.8cm 2cm 1.8cm;
    @top-center {
        content: "RAG 知识地图 v4";
        font-size: 9px;
        color: #666;
    }
    @bottom-center {
        content: "第 " counter(page) " 页";
        font-size: 9px;
        color: #666;
    }
}

/* 强制亮色主题 (PDF 不支持 prefers-color-scheme) */
:root {
    --bg: #ffffff !important;
    --bg-alt: #f8f9fa !important;
    --text: #1a1a2e !important;
    --text-muted: #666 !important;
    --border: #e0e0e0 !important;
    --accent: #0969da !important;
    --code-bg: #f6f8fa !important;
    --link: #0969da !important;
    --table-stripe: #f6f8fa !important;
    --caption-bg: #fffbeb !important;
    --caption-fg: #92400e !important;
}

/* 单栏布局 (去掉左侧 TOC sidebar 的 grid) */
.layout {
    display: block !important;
    grid-template-columns: none !important;
}

/* TOC 区域在 PDF 中作为第一页显示, 不 sticky */
nav.toc {
    position: static !important;
    height: auto !important;
    max-height: none !important;
    border-right: none !important;
    border-bottom: 2px solid var(--border) !important;
    padding: 20px !important;
    page-break-after: always;
    background: white !important;
}

main {
    padding: 0 !important;
    max-width: 100% !important;
}

/* h2 每个新章节前分页 */
h2 {
    page-break-before: always;
    page-break-after: avoid;
}
h2:first-of-type {
    page-break-before: avoid;
}
h3, h4, h5 {
    page-break-after: avoid;
}

/* 避免列表/段落被切断 */
li, p {
    orphans: 3;
    widows: 3;
}

/* 表格不跨页 (尽量) */
table {
    page-break-inside: avoid;
}

/* Mermaid 图块在 PDF 中显示为灰色提示框 */
pre.mermaid {
    background: #f0f0f0 !important;
    border: 1px dashed #ccc !important;
    padding: 12px !important;
    font-size: 10px !important;
    color: #666 !important;
    white-space: pre-wrap !important;
    page-break-inside: avoid;
}
pre.mermaid::before {
    content: "📊 [Mermaid 图表 — 请在 HTML ��本中查看交互式渲染]";
    display: block;
    font-weight: bold;
    margin-bottom: 8px;
    color: #333;
    font-size: 11px;
}

figure.mermaid-figure {
    page-break-inside: avoid;
    margin: 16px 0;
}

.mermaid-caption {
    font-size: 11px !important;
    padding: 8px 12px !important;
}

/* 发音标注: 只显示音标, 去掉下划线 */
.pron {
    border-bottom: none !important;
}
.pron .ipa {
    font-size: 9px !important;
    color: #888 !important;
}

/* 代码块 */
code {
    font-size: 12px !important;
}
pre {
    page-break-inside: avoid;
    font-size: 11px !important;
}

/* 链接显示 URL */
a[href^="http"]::after {
    content: none;  /* PDF 中不显示 URL, 太长 */
}

/* 隐藏 hover 伪元素 */
h2:hover::before, h3:hover::before, h4:hover::before {
    content: none !important;
}

body {
    font-size: 13px !important;
    line-height: 1.6 !important;
}
</style>
"""
    html = html.replace("</head>", pdf_css + "\n</head>")

    return html


def main() -> None:
    if len(sys.argv) != 3:
        print(
            f"Usage: {sys.argv[0]} <input.html> <output.pdf>",
            file=sys.stderr,
        )
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    print(f"读取 HTML: {in_path} ({in_path.stat().st_size:,} bytes)")

    html = in_path.read_text(encoding="utf-8")
    html = prepare_html_for_pdf(html)

    print("生成 PDF 中 (WeasyPrint, 可能需要 1-2 分钟)...")

    doc = HTML(string=html, base_url=str(in_path.parent))
    doc.write_pdf(str(out_path))

    size = out_path.stat().st_size
    print(f"✓ 写入 {out_path}  ({size:,} bytes / {size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
