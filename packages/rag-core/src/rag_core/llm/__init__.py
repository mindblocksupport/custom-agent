"""LLM 抽象 (Day 12).

rag-core 不强依赖 litellm — 走 Protocol + 可选 backend.
"""

from rag_core.llm.base import LLMClient, LLMResponse
from rag_core.llm.stub_backend import StubLLMClient

__all__ = ["LLMClient", "LLMResponse", "StubLLMClient"]
