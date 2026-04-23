"""Planner · 一次 LLM 决策

职责:
- 调用 LLM (通过 gateway)
- 累积 streaming text 与 tool calls
- 累积 cost / tokens (FinOps)
- 流式 yield TokenEvent
- 调用结束后,strategy 通过 `last_*` 属性读结果

后续:
- 加 Plan-Execute (一次产出 DAG)
- 加 Reflexion 反思 prompt
"""

from collections.abc import AsyncIterator
from typing import Any

from gateway import llm_complete_stream
from schemas import StreamEvent, TokenEvent


class Planner:
    """单次规划 - 包装一次 LLM 调用。"""

    def __init__(self) -> None:
        self.last_text: str = ""
        self.last_tool_calls: list[dict[str, Any]] = []
        self.last_cost_usd: float = 0.0
        self.last_input_tokens: int = 0
        self.last_output_tokens: int = 0

    def reset(self) -> None:
        self.last_text = ""
        self.last_tool_calls = []
        self.last_cost_usd = 0.0
        self.last_input_tokens = 0
        self.last_output_tokens = 0

    async def stream(
        self,
        messages: list[dict[str, Any]],
        model: str,
        tools: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        **llm_kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        """跑一次 LLM 调用,流式 yield TokenEvent。

        Args:
            metadata: LiteLLM/Langfuse 透传(trace_id / session_id / user_id / tags 等)。

        迭代结束后,通过 `self.last_*` 读结果。
        """
        self.reset()
        async for chunk in llm_complete_stream(
            messages=messages,
            model=model,
            tools=tools,
            metadata=metadata,
            **llm_kwargs,
        ):
            ctype = chunk.get("type")
            if ctype == "text":
                self.last_text += chunk["delta"]
                yield TokenEvent(text=chunk["delta"])
            elif ctype == "tool_call":
                self.last_tool_calls.append(chunk["data"])
            elif ctype == "usage":
                self.last_cost_usd += float(chunk.get("cost", 0.0))
                self.last_input_tokens += int(chunk.get("input_tokens", 0))
                self.last_output_tokens += int(chunk.get("output_tokens", 0))
