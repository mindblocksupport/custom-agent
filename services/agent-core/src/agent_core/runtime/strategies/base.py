"""AgentStrategy 协议"""

from collections.abc import AsyncIterator
from typing import Any, Protocol

from schemas import StreamEvent

from agent_core.runtime.config import AgentConfig
from agent_core.tools.registry import ToolRegistry


class AgentStrategy(Protocol):
    """所有 agent 推理策略的协议。

    实现者保证:
    - yield 第一个事件是 StartEvent
    - yield 最后一个事件是 DoneEvent 或 ErrorEvent (二选一)
    - 中间穿插 TokenEvent / ToolCallEvent / ToolResultEvent
    - 触发任何 Guardrail 时立即 yield ErrorEvent 并 return
    - 不抛异常 (异常包装为 ErrorEvent)
    - metadata 透传给 gateway → LiteLLM → 观测后端
    """

    async def run(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        registry: ToolRegistry,
        config: AgentConfig,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamEvent]: ...
