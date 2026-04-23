"""Agent Core · L5 运行时核心

公开 API:
    from agent_core import run_agent, AgentConfig, ToolRegistry, Tool, ReActStrategy

设计原则:
- 全部依赖通过参数注入 (无全局变量)
- 类型化事件输出 (schemas.StreamEvent)
- 推理策略可换 (ReActStrategy / 未来 PlanExecute / Reflexion)
- planner / executor / critic 解耦,后续可单独换实现
"""

from agent_core.runtime import (
    AgentConfig,
    AgentState,
    AgentStrategy,
    Critic,
    CriticVerdict,
    Executor,
    NoOpCritic,
    Planner,
    ReActStrategy,
    ToolExecResult,
    run_agent,
)
from agent_core.tools.protocol import Tool
from agent_core.tools.registry import ToolRegistry

__all__ = [
    "AgentConfig",
    "AgentState",
    "AgentStrategy",
    "Critic",
    "CriticVerdict",
    "Executor",
    "NoOpCritic",
    "Planner",
    "ReActStrategy",
    "Tool",
    "ToolExecResult",
    "ToolRegistry",
    "run_agent",
]
