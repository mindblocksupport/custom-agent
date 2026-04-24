"""Tool 协议 (L4)

设计原则:
- 工具定义与注册中心解耦——任何符合 Tool 协议的对象都可以注册
- 后续 MCP server 适配只需把 MCP tool 包装成 Tool 实例,无需改 registry
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Tool:
    """工具定义 —— 不可变,适合放入注册中心。

    Args:
        name: 工具名 (snake_case),LLM 通过此名调用
        description: 给 LLM 看的"何时用 / 何时不用"。质量决定调用准确率
        parameters: JSON Schema (OpenAI / Anthropic / MCP 通用格式)
        execute: 异步可调用,接收 kwargs,返回任意可序列化结果
        requires_acl: True 表示工具需要 ACL principal token (Day 2/P0 #3).
                      Executor 在调用前自动注入 `_principal_token` arg,
                      LLM 永远看不到. 触达租户数据的工具应设 True
                      (search_kb, future crm_lookup, files_read 等).
    """

    name: str
    description: str
    parameters: dict[str, Any]
    execute: Callable[..., Awaitable[Any]]
    requires_acl: bool = False
