"""Critic · 评审 (Reflexion / Self-Refine 用)

MVP 仅 Protocol + NoOpCritic 占位。
后续 ReflexionStrategy 会用真实 Critic 做"自我反思"。
"""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class CriticVerdict:
    approved: bool
    feedback: str | None = None  # 不通过时的修改建议
    confidence: float | None = None


class Critic(Protocol):
    """评审 Agent 输出的协议。"""

    async def review(
        self,
        history: list[dict[str, Any]],
        last_response: str,
    ) -> CriticVerdict: ...


class NoOpCritic:
    """默认 critic - 总是通过。ReAct 不需要 critic 时用这个。"""

    async def review(
        self,
        history: list[dict[str, Any]],
        last_response: str,
    ) -> CriticVerdict:
        return CriticVerdict(approved=True)
