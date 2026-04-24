"""ReAct 策略 · 经典 think → act → observe 循环

对应文档 docs/05-agent-core.md §3.1。
"""

import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

from schemas import (
    DoneData,
    DoneEvent,
    ErrorEvent,
    StartData,
    StartEvent,
    StreamEvent,
)

from agent_core.guardrails.limits import GuardrailViolation, RuntimeGuard
from agent_core.runtime.config import AgentConfig
from agent_core.runtime.executor import Executor
from agent_core.runtime.planner import Planner
from agent_core.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class ReActStrategy:
    """ReAct 实现 = Planner + Executor 反复轮转。"""

    async def run(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        registry: ToolRegistry,
        config: AgentConfig,
        metadata: dict[str, Any] | None = None,
        token_provider: Callable[[], str] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        history = list(messages)
        guard = RuntimeGuard(config)
        planner = Planner()
        executor = Executor(registry, token_provider=token_provider)
        tools_schema = registry.get_schemas()

        yield StartEvent(data=StartData(model=model, max_steps=config.max_steps))

        for step in range(config.max_steps):
            # ===== 闸门 1-2: 成本 / token =====
            try:
                guard.check_budget()
            except GuardrailViolation as e:
                yield ErrorEvent(text=str(e))
                return

            # ===== Planner: 一次 LLM 调用 =====
            step_metadata = dict(metadata or {})
            step_metadata = {**step_metadata, "agent_step": step}
            try:
                async for ev in planner.stream(
                    history, model, tools_schema, metadata=step_metadata
                ):
                    yield ev
                # 累积 cost + tokens 到 guard
                guard.add_cost(planner.last_cost_usd)
                guard.add_tokens(planner.last_input_tokens, planner.last_output_tokens)
            except Exception as e:
                logger.exception("LLM call failed")
                yield ErrorEvent(text=f"LLM error: {e}")
                return

            # ===== 没工具调用 = 完成 =====
            if not planner.last_tool_calls:
                history.append({"role": "assistant", "content": planner.last_text})
                yield DoneEvent(
                    data=DoneData(
                        steps=step + 1,
                        cost_usd=round(guard.cost_usd, 6),
                        input_tokens=guard.input_tokens,
                        output_tokens=guard.output_tokens,
                    )
                )
                return

            # ===== 闸门 3: 死循环检测 =====
            try:
                for tc in planner.last_tool_calls:
                    guard.check_loop(tc.get("function", {}))
            except GuardrailViolation as e:
                yield ErrorEvent(text=str(e))
                return

            # ===== 写历史 (assistant turn + tool_calls) =====
            history.append(
                {
                    "role": "assistant",
                    "content": planner.last_text or None,
                    "tool_calls": planner.last_tool_calls,
                }
            )

            # ===== Executor: 执行工具 =====
            async for ev in executor.stream(planner.last_tool_calls):
                yield ev

            # 把执行结果回写到 history
            had_error = False
            for r in executor.last_results:
                if not r.succeeded:
                    had_error = True
                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": r.tool_call_id,
                        "content": r.error or str(r.raw_result),
                    }
                )

            # ===== 闸门 4: 连续工具失败 =====
            if had_error:
                try:
                    guard.record_tool_error()
                except GuardrailViolation as e:
                    yield ErrorEvent(text=str(e))
                    return
            else:
                guard.reset_tool_errors()

        # ===== 闸门 5: max_steps =====
        yield ErrorEvent(text=f"Max steps {config.max_steps} reached without completion")
