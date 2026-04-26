#!/usr/bin/env python3
"""把 Markdown 大纲转成 XMind 原生 .xmind 文件 (XMind 2020+ 格式).

Usage:
    python scripts/md_to_xmind.py docs/rag-knowledge-map.md docs/rag-knowledge-map.xmind

Markdown 约定:
    # 一级 (root)
    ## 二级 (主分支)
    ### 三级
    #### 四级
    ##### 五级
    - 列表项 (叶节点; 缩进 = 子层)
    > 引用 / 段落 (作为节点的 notes)

XMind 文件结构 (zip):
    content.json    主结构
    metadata.json   创建者元数据
    manifest.json   文件清单
"""

from __future__ import annotations  # PEP 604 X | Y 语法兼容 Py 3.9-

import json
import re
import sys
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


# ----- markdown 内联格式剥离 (XMind 节点不渲染 **bold**, 会显示字面 ** ) -----
_INLINE_PATTERNS = [
    # LaTeX 公式 (XMind 不渲染 KaTeX, 显示字面 $$ \frac \sum 一坨乱码)
    (re.compile(r"\$\$(.+?)\$\$", re.DOTALL), r"[公式: \1]"),  # $$ block math $$
    (re.compile(r"(?<!\$)\$([^$\n]+?)\$(?!\$)"), r"[\1]"),    # $ inline $
    # 常见 LaTeX 控制序列 (兜底, 万一上面没匹配)
    (re.compile(r"\\text\{([^}]+)\}"), r"\1"),
    (re.compile(r"\\frac\{([^}]+)\}\{([^}]+)\}"), r"(\1)/(\2)"),
    (re.compile(r"\\sum"), r"Σ"),
    (re.compile(r"\\cdot"), r"·"),
    (re.compile(r"\\vec\{([^}]+)\}"), r"\1"),
    (re.compile(r"\\in\b"), r"∈"),
    # markdown inline
    (re.compile(r"\*\*\*(.+?)\*\*\*"), r"\1"),  # ***bold-italic***
    (re.compile(r"\*\*(.+?)\*\*"), r"\1"),       # **bold**
    (re.compile(r"__(.+?)__"), r"\1"),           # __bold__
    (re.compile(r"(?<!\*)\*([^*]+?)\*(?!\*)"), r"\1"),  # *italic*
    (re.compile(r"(?<!_)_([^_]+?)_(?!_)"), r"\1"),       # _italic_
    (re.compile(r"~~(.+?)~~"), r"\1"),           # ~~strike~~
    (re.compile(r"`([^`]+?)`"), r"\1"),          # `code`
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"),  # [text](url)
    (re.compile(r"!\[([^\]]*)\]\([^)]+\)"), r"\1"),  # ![alt](img)
]


def strip_md_inline(text: str) -> str:
    """剥掉 markdown inline 格式, 留纯文本. 多次循环防嵌套."""
    out = text
    for _ in range(3):
        before = out
        for pat, repl in _INLINE_PATTERNS:
            out = pat.sub(repl, out)
        if out == before:
            break
    return out


# ----- 顶级分支配色 (按 top-level 顺序循环, 仅 level 1+2 着色) -----
# 取一组对比强但不刺眼的色; 红橙给"问题/案例"暗示警示
_TOP_PALETTE: list[str] = [
    # v4 17 sections + 3 附录 + 末尾 = 21 颜色 (清晰色阶)
    "#F59E0B",  # 〇 速览 + 读者地图 - amber
    "#3B82F6",  # 一 RAG 基础原理 - blue
    "#06B6D4",  # 二 业务流程图解 - cyan
    "#0EA5E9",  # 三 5 层架构总览 - sky
    "#10B981",  # 四 L1 数据治理 + Write Path - emerald
    "#22C55E",  # 五 L2 索引质量 + Index Build - green
    "#84CC16",  # 六 L3 检索 + Read Path (重头戏) - lime
    "#A855F7",  # 七 L4 Router 路由决策流程 - purple
    "#EC4899",  # 八 L5 Agent 多步推理 - pink
    "#8B5CF6",  # 九 Generation 生成流程 - violet
    "#F97316",  # 十 横切关注点 - orange
    "#0891B2",  # 十一 周边技术栈 + 各组件读写流程 - cyan deep
    "#14B8A6",  # 十二 业务场景案例库 - teal
    "#EF4444",  # 十三 22 真实事故 - red (警示)
    "#6366F1",  # 十四 评估与运营 - indigo
    "#7C3AED",  # 十五 完整面试题库 - deep purple
    "#DC2626",  # 十六 Failure Mode 系统诊断 - dark red
    "#059669",  # 十七 学习路径 - deep emerald
    "#0284C7",  # 十八 RAG 源码实现+工程结构 - sky deeper (源码工程)
    "#7C3AED",  # 十九 Modular RAG 深度详解 - violet (范式)
    "#DB2777",  # 二十 Agent RAG 深度详解 - magenta (智能体)
    "#94A3B8",  # 附录 A - slate
    "#94A3B8",  # 附录 B - slate
    "#94A3B8",  # 附录 C - slate
    "#94A3B8",  # 末尾总结 - slate
]


def _topic_style(color: str, depth: int) -> dict:
    """生成 XMind topic style: 浅色背景 + 同色边框 + 同色文字."""
    if depth == 1:
        # 一级: 实色填充 + 白字
        return {
            "id": uuid.uuid4().hex,
            "type": "topic",
            "properties": {
                "svg:fill": color,
                "border-line-color": color,
                "border-line-width": "2pt",
                "fo:color": "#FFFFFF",
                "fo:font-weight": "700",
            },
        }
    # 二级: 浅色填充 + 同色边框 + 同色文字
    return {
        "id": uuid.uuid4().hex,
        "type": "topic",
        "properties": {
            "svg:fill": color + "1A",  # 10% alpha
            "border-line-color": color,
            "border-line-width": "1.5pt",
            "fo:color": color,
            "fo:font-weight": "600",
        },
    }


@dataclass
class Node:
    title: str
    notes: list[str] = field(default_factory=list)
    children: list["Node"] = field(default_factory=list)
    level: int = 0  # 0=root, 1=##, 2=###, ...
    color: str | None = None  # 顶级分支着色后, 沿树向下传

    def to_xmind(self, depth: int = 0) -> dict:
        clean_title = strip_md_inline(self.title).strip()
        out: dict = {
            "id": uuid.uuid4().hex,
            "class": "topic",
            "title": clean_title,
        }
        # 仅 depth 1 / 2 着色 (3+ 默认白底, 防视觉过重)
        if self.color and depth in (1, 2):
            out["style"] = _topic_style(self.color, depth)
        if self.notes:
            text = "\n\n".join(strip_md_inline(n) for n in self.notes).strip()
            if text:
                out["notes"] = {"plain": {"content": text}}
        if self.children:
            out["children"] = {
                "attached": [c.to_xmind(depth + 1) for c in self.children],
            }
        return out


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
LIST_RE = re.compile(r"^(\s*)[-*]\s+(.+)$")


def parse_markdown(md_text: str) -> Node:
    """解析策略 (优先可见, 减少折叠):
    - heading → 主树节点 (展开级)
    - 普通段落 → **可见子节点** (作为 leaf, 不折叠到 notes)
    - 列表 → 子节点 (按缩进嵌套)
    - 表格 → 整张表合并成 notes (放节点附注里, 减少节点爆炸)
    - blockquote (>) → notes (作者明确标"附注"语义)
    - code fence (```) → 跳过 (mind map 不适合大代码块)
    """
    lines = md_text.splitlines()

    root: Node | None = None
    # 栈: (level, node) 维护当前 heading 路径
    stack: list[tuple[int, Node]] = []
    # 普通段落 buffer, 累积到 blank line 或 heading/list 时变成可见子节点
    plain_buf: list[str] = []
    # 表格 / blockquote buffer, 累积到 blank line 或 heading/list 时变成 notes
    notes_buf: list[str] = []

    def flush_plain_as_child():
        """把累积的普通段落变成当前 heading 的可见子节点."""
        if not plain_buf or not stack:
            plain_buf.clear()
            return
        text = " ".join(s.strip() for s in plain_buf if s.strip()).strip()
        if text:
            leaf = Node(title=text, level=99)
            stack[-1][1].children.append(leaf)
        plain_buf.clear()

    def flush_notes_to_current():
        """把累积的表格/引用合并成一段, 挂到当前 heading 的 notes."""
        if not notes_buf or not stack:
            notes_buf.clear()
            return
        text = "\n".join(notes_buf).strip()
        if text:
            stack[-1][1].notes.append(text)
        notes_buf.clear()

    def flush_all():
        flush_plain_as_child()
        flush_notes_to_current()

    list_stack: list[tuple[int, Node]] = []  # (indent_chars, list_node)
    in_code_fence = False

    for raw in lines:
        # 处理 code fence (跳过整段)
        if raw.strip().startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue

        # heading
        m = HEADING_RE.match(raw)
        if m:
            flush_all()
            list_stack = []
            hashes, title = m.group(1), m.group(2).strip()
            level = len(hashes)
            node = Node(title=title, level=level)
            if level == 1:
                root = node
                stack = [(1, root)]
                continue
            if root is None:
                root = Node(title="(root)")
                stack = [(1, root)]
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent = stack[-1][1] if stack else root
            parent.children.append(node)
            stack.append((level, node))
            continue

        # list item
        m = LIST_RE.match(raw)
        if m:
            flush_all()
            indent_str, item_text = m.group(1), m.group(2).strip()
            indent = len(indent_str.expandtabs(2))
            leaf = Node(title=item_text, level=99)
            while list_stack and list_stack[-1][0] >= indent:
                list_stack.pop()
            if list_stack:
                list_stack[-1][1].children.append(leaf)
            elif stack:
                stack[-1][1].children.append(leaf)
            list_stack.append((indent, leaf))
            continue

        # blockquote → notes
        if raw.strip().startswith(">"):
            text = raw.strip().lstrip(">").strip()
            if text:
                notes_buf.append(text)
            continue

        # blank line → 段落分隔, flush
        if raw.strip() == "":
            flush_plain_as_child()
            # 表格内的空行不应该 flush notes; 但简化: 也 flush
            flush_notes_to_current()
            continue

        # 表格分隔行 |---|---| → 跳过
        if re.match(r"^\s*\|?\s*[:\- ]+\|", raw):
            continue

        # 表格内容行 → notes
        if "|" in raw and raw.strip().startswith("|"):
            cells = [c.strip() for c in raw.strip().strip("|").split("|")]
            notes_buf.append(" | ".join(cells))
            continue

        # 普通段落
        plain_buf.append(raw.strip())

    flush_all()

    if root is None:
        raise ValueError("No # heading found in markdown")
    return root


def paint_top_branches(root: Node) -> None:
    """给顶级分支按 _TOP_PALETTE 上色, 颜色沿树向下 cascade."""
    def cascade(node: Node, color: str) -> None:
        node.color = color
        for ch in node.children:
            cascade(ch, color)

    for i, branch in enumerate(root.children):
        color = _TOP_PALETTE[i % len(_TOP_PALETTE)]
        cascade(branch, color)


def build_xmind_content(root: Node) -> list[dict]:
    """生成 content.json 内容 (XMind 2020+ 多 sheet 数组格式)."""
    paint_top_branches(root)
    root_topic = root.to_xmind(depth=0)
    root_topic["structureClass"] = "org.xmind.ui.map.unbalanced"
    return [
        {
            "id": uuid.uuid4().hex,
            "class": "sheet",
            "title": "RAG 知识地图",
            "rootTopic": root_topic,
            "topicPositioning": "fixed",
            "topicOverlapping": "overlap",
            "theme": {
                "id": "theme-default",
            },
        },
    ]


def build_metadata() -> dict:
    return {
        "creator": {
            "name": "custom_agent rag-knowledge-map generator",
            "version": "1.0",
        },
    }


def build_manifest() -> dict:
    return {
        "file-entries": {
            "content.json": {},
            "metadata.json": {},
        },
    }


def write_xmind(path: Path, root: Node) -> None:
    content = build_xmind_content(root)
    metadata = build_metadata()
    manifest = build_manifest()

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.json", json.dumps(content, ensure_ascii=False, indent=2))
        z.writestr(
            "metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2),
        )
        z.writestr(
            "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2),
        )


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.md> <output.xmind>", file=sys.stderr)
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    md_text = in_path.read_text(encoding="utf-8")
    root = parse_markdown(md_text)

    # 简单计数, 给个直观感
    def count(n: Node) -> int:
        return 1 + sum(count(c) for c in n.children)

    n_nodes = count(root)
    write_xmind(out_path, root)

    print(f"✓ 写入 {out_path}")
    print(f"  - 节点数: {n_nodes}")
    print(f"  - 文件大小: {out_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
