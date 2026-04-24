"""Agent 主入口 · 选择策略 + 编排

新版 (v0.2 重构):
- loop.py 极简,仅做 strategy 选择 + dispatch
- 实际推理逻辑在 strategies/ 下,planner/executor/critic 子模块各司其职
- 后续接 LangGraph: 把 strategy 实现替成 LangGraph compile().astream(),其余不变
"""

from collections.abc import AsyncIterator, Callable
from typing import Any

from schemas import StreamEvent

from agent_core.runtime.config import AgentConfig
from agent_core.runtime.strategies import AgentStrategy, ReActStrategy
from agent_core.tools.registry import ToolRegistry

# 默认策略 - 80% 业务场景够用 (见 docs/05 §3.3)
_DEFAULT_STRATEGY: AgentStrategy = ReActStrategy()


async def run_agent(
    messages: list[dict[str, Any]],
    model: str,
    *,
    registry: ToolRegistry,
    config: AgentConfig | None = None,
    strategy: AgentStrategy | None = None,
    metadata: dict[str, Any] | None = None,
    token_provider: Callable[[], str] | None = None,
) -> AsyncIterator[StreamEvent]:
    """跑 Agent。

    Args:
        messages: OpenAI 兼容消息历史
        model: LiteLLM 模型 ID (如 "deepseek/deepseek-chat")
        registry: 工具注册中心
        config: 运行时配置 (None=默认)
        strategy: 推理策略 (None=ReAct);可换 PlanExecute/Reflexion/...
        metadata: 观测/计费/审计 透传 (trace_id/session_id/user_id/tags),
                  下传到 gateway → LiteLLM → Langfuse callback。
        token_provider: () -> JWT, 给 requires_acl=True 的工具注入. Day 2 P0 #3.
                        api-server 用 Principal 现签现给.

    Yields:
        类型化 StreamEvent (start/token/tool_call/tool_result/done/error)
    """
    cfg = config or AgentConfig()
    strat = strategy or _DEFAULT_STRATEGY

    async for event in strat.run(
        messages=messages,
        model=model,
        registry=registry,
        config=cfg,
        metadata=metadata,
        token_provider=token_provider,
    ):
        yield event
