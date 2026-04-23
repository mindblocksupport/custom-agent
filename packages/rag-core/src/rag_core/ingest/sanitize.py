"""Prompt-injection 检测 + 内容净化 (L37 §8.3, Day 11).

检测可疑模式 → 标 is_quarantined=True (检索时过滤);
净化用于嵌入 prompt 时, 防止 chunk 内容逃出 <retrieved_context> 包装.
"""

from __future__ import annotations

import re

# 显式 jailbreak / system-prompt-inject 指令
_INJECTION_PATTERNS = [
    re.compile(r"(?i)ignore (the )?(previous|above|prior) (instructions?|prompt)"),
    re.compile(r"(?i)disregard (the )?(previous|above|prior) (instructions?|prompt)"),
    re.compile(r"(?i)\byou are now\b.*\b(dan|jailbroken|unrestricted)\b"),
    re.compile(r"(?i)\bsystem prompt\b\s*[:=]"),
    re.compile(r"<\s*system\s*>", re.IGNORECASE),
    re.compile(r"<\s*\|\s*(im_start|system|im_end)\s*\|\s*>", re.IGNORECASE),
    re.compile(r"\[INST\]|\[/INST\]"),
    # 长 base64 (>200 字符, 防隐藏负载)
    re.compile(r"[A-Za-z0-9+/=]{200,}"),
]

# 我们自己的包装 tag — chunk 内容不能含 (匹配整个开/闭 tag, 含可能的属性)
_OWN_WRAPPER_TAG_RE = re.compile(r"</?\s*retrieved_context\b[^>]*>", re.IGNORECASE)


def detect_injection(content: str) -> tuple[bool, str | None]:
    """返回 (是否疑似 injection, 命中的 reason)."""
    if not content:
        return False, None
    for pat in _INJECTION_PATTERNS:
        m = pat.search(content)
        if m:
            return True, f"pattern:{pat.pattern[:40]}"
    if _OWN_WRAPPER_TAG_RE.search(content):
        return True, "own_wrapper_tag_in_content"
    return False, None


def escape_for_wrapper(content: str) -> str:
    """转义 chunk 内容里的 <retrieved_context> tag, 防止 LLM 看到的 wrapper 被破坏.

    把 < / > 替换成全角字符是简单有效的不可见净化 (LLM 仍能读懂语义,
    但 tokenizer 上等价于不同 token, 无法关闭我们的真 wrapper).
    """
    if not content:
        return content
    return _OWN_WRAPPER_TAG_RE.sub(lambda m: m.group(0).replace("<", "＜").replace(">", "＞"), content)
