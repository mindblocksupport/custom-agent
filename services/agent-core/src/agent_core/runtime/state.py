"""Agent 状态定义 (L5 §4)"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class AgentState:
    """单次 Agent 运行的完整状态。

    后续接入 LangGraph checkpointer 时,这个 dataclass 会被序列化持久化。
    """

    messages: list[dict] = field(default_factory=list)
    step: int = 0
    tokens_used: int = 0
    cost_usd: float = 0.0

    # 失控保护 (L5 §5 五道闸门)
    state_hash_history: list[str] = field(default_factory=list)
    consecutive_tool_errors: int = 0

    status: Literal["running", "done", "halted", "awaiting_human", "error"] = "running"
    error_message: str | None = None
