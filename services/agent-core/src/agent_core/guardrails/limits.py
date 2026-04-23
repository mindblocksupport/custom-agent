"""五道闸门集中实现 (L5 §5)

抽出来作为独立模块,方便后续:
- 加新闸门 (如领域风险评分、输出有害内容等)
- 替换为 NeMo Guardrails 框架 (docs/16 §8)
- 单测覆盖每条闸门
"""

import hashlib
import json
from typing import Any

from agent_core.runtime.config import AgentConfig


class GuardrailViolation(RuntimeError):
    """护栏触发 - 上层应停止 agent loop 并向用户报错。"""


class RuntimeGuard:
    """单次 agent 运行的护栏状态机。"""

    def __init__(self, config: AgentConfig) -> None:
        self.cfg = config
        self.cost_usd: float = 0.0
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.consecutive_tool_errors: int = 0
        self._action_hashes: list[str] = []

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    # ----- 1) 成本 -----
    def add_cost(self, delta: float) -> None:
        self.cost_usd += delta

    def add_tokens(self, input_delta: int = 0, output_delta: int = 0) -> None:
        self.input_tokens += input_delta
        self.output_tokens += output_delta

    def check_budget(self) -> None:
        if self.cost_usd >= self.cfg.max_cost_usd:
            raise GuardrailViolation(
                f"Max cost ${self.cfg.max_cost_usd} exceeded "
                f"(current ${self.cost_usd:.4f})"
            )
        if (
            self.cfg.max_total_tokens is not None
            and self.total_tokens >= self.cfg.max_total_tokens
        ):
            raise GuardrailViolation(
                f"Max tokens {self.cfg.max_total_tokens} exceeded "
                f"(current {self.total_tokens})"
            )

    # ----- 2) 死循环 -----
    @staticmethod
    def _hash_action(action: dict[str, Any]) -> str:
        key = json.dumps(
            {"name": action.get("name"), "args": action.get("arguments")},
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha1(key.encode()).hexdigest()[:12]

    def check_loop(self, action: dict[str, Any]) -> None:
        h = self._hash_action(action)
        self._action_hashes.append(h)
        if self._action_hashes.count(h) >= self.cfg.max_loop_repeats:
            name = action.get("name", "?")
            raise GuardrailViolation(
                f"Loop detected: '{name}' called with same args "
                f"{self.cfg.max_loop_repeats}+ times"
            )

    # ----- 3) 连续工具失败 -----
    def record_tool_error(self) -> None:
        self.consecutive_tool_errors += 1
        if self.consecutive_tool_errors >= self.cfg.max_consecutive_tool_errors:
            raise GuardrailViolation(
                f"Too many consecutive tool errors ({self.consecutive_tool_errors})"
            )

    def reset_tool_errors(self) -> None:
        self.consecutive_tool_errors = 0
