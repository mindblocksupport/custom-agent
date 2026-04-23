"""Executor · 工具执行

职责:
- 顺序 (后续可并行) 执行 tool_calls
- 流式 yield ToolCallEvent + ToolResultEvent
- 错误捕获 → 结构化反馈给 LLM
- strategy 通过 `last_results` 拿详细结果做 guard 判断

后续:
- asyncio.gather 并行
- 单工具超时 / 重试
- 工具调用前的 HITL 拦截
- 沙箱化执行 (E2B / gVisor)
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from schemas import StreamEvent, ToolCallData, ToolCallEvent, ToolResultData, ToolResultEvent

from agent_core.tools.registry import ToolRegistry

# 单个工具结果截断上限 (防 context 爆炸)
DEFAULT_RESULT_CHARS = 1000


@dataclass
class ToolExecResult:
    """单次工具执行的内部结果(给 strategy 看,不直接 yield)。"""

    tool_call_id: str | None
    name: str
    raw_result: Any | None
    error: str | None

    @property
    def succeeded(self) -> bool:
        return self.error is None


class Executor:
    """工具调度器 - 接 ToolRegistry。"""

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        result_max_chars: int = DEFAULT_RESULT_CHARS,
    ) -> None:
        self.registry = registry
        self.result_max_chars = result_max_chars
        self.last_results: list[ToolExecResult] = []

    def reset(self) -> None:
        self.last_results = []

    async def stream(
        self, tool_calls: list[dict[str, Any]]
    ) -> AsyncIterator[StreamEvent]:
        """流式 yield: 先发 ToolCallEvent (通知开始) → 执行 → 发 ToolResultEvent。

        迭代结束后,strategy 通过 `self.last_results` 拿原始结果。
        """
        self.reset()

        # 1) 通知工具调用开始 (一次性发完, 让前端立刻显示"正在执行")
        for tc in tool_calls:
            fn = tc.get("function", {})
            yield ToolCallEvent(
                data=ToolCallData(
                    id=tc.get("id"),
                    name=fn.get("name", ""),
                    arguments=fn.get("arguments", ""),
                )
            )

        # 2) 顺序执行 (后续可改 asyncio.gather 并行)
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            try:
                raw = await self.registry.execute(name, fn.get("arguments", ""))
                exec_result = ToolExecResult(
                    tool_call_id=tc.get("id"),
                    name=name,
                    raw_result=raw,
                    error=None,
                )
                yield ToolResultEvent(
                    data=ToolResultData(
                        id=exec_result.tool_call_id,
                        name=name,
                        result=str(raw)[: self.result_max_chars],
                    )
                )
            except Exception as e:
                err = f"Tool error ({name}): {e}"
                exec_result = ToolExecResult(
                    tool_call_id=tc.get("id"),
                    name=name,
                    raw_result=None,
                    error=err,
                )
                yield ToolResultEvent(
                    data=ToolResultData(id=tc.get("id"), name=name, error=err)
                )

            self.last_results.append(exec_result)
