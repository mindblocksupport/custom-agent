"""LLM Gateway · L2

唯一的 LLM 出口。MVP 阶段 = LiteLLM 包装。
"""

from gateway.client import llm_complete_stream
from gateway.router import ModelRouter, RouteDecision

__all__ = ["ModelRouter", "RouteDecision", "llm_complete_stream"]
