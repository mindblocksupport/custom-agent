"""ModelRouter (L37 §1 Q4 + Day 13).

按 query 复杂度路由到不同模型, 省 50%+ LLM 成本:
- 简单 FAQ / 短问 → DeepSeek-Chat ($0.14/1M 输入)
- 长上下文 / 多跳推理 / 显式分析词 → Sonnet 4.6 ($3/1M 输入)
- tool-heavy 流程 → DeepSeek (函数调用稳定性 + 便宜)

输入信号:
- last user query 字符长度
- 是否含分析/推理词 ("为什么/分析/对比/推导/为何/原因")
- messages 历史长度 (对话越长越倾向便宜)
- tools 数量 (有工具时一律走 DeepSeek; 工具循环费 token)
- 显式 model 参数 (caller 指定时 router 不接管)

返回 (model, reason) 二元组, reason 写进 trace metadata.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

REASONING_KEYWORDS_RE = re.compile(
    r"(为什么|为何|分析|对比|比较|推导|原因|区别|权衡|trade.?off|why\b|analyze|compare)",
    re.IGNORECASE,
)
LONG_QUERY_THRESHOLD = 200            # 字符


@dataclass
class RouteDecision:
    model: str
    reason: str

    def __str__(self) -> str:
        return f"{self.model} ({self.reason})"


class ModelRouter:
    """轻量启发式路由. Day 14+ 接 DPO / bandit 学习."""

    def __init__(
        self,
        *,
        cheap_model: str | None = None,
        reasoning_model: str | None = None,
        force_model: str | None = None,
    ) -> None:
        self.cheap = cheap_model or os.environ.get(
            "ROUTER_CHEAP_MODEL", "deepseek/deepseek-chat",
        )
        self.reasoning = reasoning_model or os.environ.get(
            "ROUTER_REASONING_MODEL", "anthropic/claude-sonnet-4-6",
        )
        # force_model 用于 caller 显式指定时 (router 不接管)
        self.force = force_model

    def route(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        explicit_model: str | None = None,
    ) -> RouteDecision:
        # 1. caller 显式指定 → 直接用
        if explicit_model:
            return RouteDecision(explicit_model, "explicit")
        if self.force:
            return RouteDecision(self.force, "force")

        # 2. 提取最后一条 user query
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                content = m.get("content") or ""
                last_user = content if isinstance(content, str) else str(content)
                break

        # 3. 推理词触发 → reasoning model
        if REASONING_KEYWORDS_RE.search(last_user):
            return RouteDecision(self.reasoning, "reasoning_keyword")

        # 4. 长 query (>200 char) → reasoning
        if len(last_user) > LONG_QUERY_THRESHOLD:
            return RouteDecision(self.reasoning, "long_query")

        # 5. 默认 (短 FAQ + 工具循环) → cheap
        if tools:
            return RouteDecision(self.cheap, "tool_calling")
        return RouteDecision(self.cheap, "default_short")
