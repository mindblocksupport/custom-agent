"""工具注册中心 (L4 §6)

实例化 (而非全局 dict),便于:
- 多 agent 不同工具集
- 多租户隔离
- 单元测试
"""

import json
from typing import Any

from agent_core.tools.protocol import Tool

# 系统注入的字段, 永不在 LLM 可见的 schema 中暴露 (防 prompt injection 偷传)
_SYSTEM_ARG_KEYS = frozenset({"principal_token"})


def _strip_system_args(schema: dict[str, Any]) -> dict[str, Any]:
    """从 JSON Schema 的 properties / required 里剥掉系统字段."""
    if not isinstance(schema, dict):
        return schema
    props = schema.get("properties")
    required = schema.get("required")
    out = dict(schema)
    if isinstance(props, dict):
        out["properties"] = {
            k: v for k, v in props.items() if k not in _SYSTEM_ARG_KEYS
        }
    if isinstance(required, list):
        out["required"] = [r for r in required if r not in _SYSTEM_ARG_KEYS]
    return out


class ToolRegistry:
    """工具注册中心 —— 一个 Agent 一份。"""

    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        if tools:
            for t in tools:
                self.register(t)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def get_schemas(self) -> list[dict[str, Any]]:
        """返回 OpenAI / Anthropic 兼容的 tool schemas (剥系统字段, Day 2 P0 #3)."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": _strip_system_args(t.parameters),
                },
            }
            for t in self._tools.values()
        ]

    async def execute(self, name: str, arguments: str | dict[str, Any]) -> Any:
        """执行工具。

        Args:
            name: 工具名
            arguments: JSON 字符串或 dict

        Raises:
            KeyError: 工具不存在
            ValueError: 参数 JSON 解析失败
        """
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}. Available: {list(self._tools.keys())}")

        if isinstance(arguments, str):
            try:
                args = json.loads(arguments) if arguments.strip() else {}
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON arguments for tool '{name}': {e}") from e
        else:
            args = arguments or {}

        return await self._tools[name].execute(**args)
