#!/usr/bin/env python3
"""把 Markdown 转 OPML (XMind 老版本兜底).

Usage:
    python scripts/md_to_opml.py docs/rag-knowledge-map.md docs/rag-knowledge-map.opml
"""

import sys
from pathlib import Path
from xml.sax.saxutils import escape

# reuse the markdown parser + inline 剥离
sys.path.insert(0, str(Path(__file__).parent))
from md_to_xmind import Node, parse_markdown, strip_md_inline


def to_opml_outline(node: Node, depth: int = 0) -> str:
    indent = "  " * depth
    text = escape(strip_md_inline(node.title).strip())
    note = (
        escape("\n\n".join(strip_md_inline(n) for n in node.notes).strip())
        if node.notes else ""
    )
    attrs = f'text="{text}"'
    if note:
        attrs += f' _note="{note}"'
    if not node.children:
        return f"{indent}<outline {attrs}/>\n"
    inner = "".join(to_opml_outline(c, depth + 1) for c in node.children)
    return f"{indent}<outline {attrs}>\n{inner}{indent}</outline>\n"


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.md> <output.opml>", file=sys.stderr)
        sys.exit(1)
    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    md = in_path.read_text(encoding="utf-8")
    root = parse_markdown(md)
    body = to_opml_outline(root)
    opml = f"""<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head>
    <title>{escape(root.title)}</title>
  </head>
  <body>
{body}  </body>
</opml>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(opml, encoding="utf-8")
    print(f"✓ 写入 {out_path}  ({out_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
