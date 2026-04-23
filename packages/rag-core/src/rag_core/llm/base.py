"""LLMClient 协议.

实现:
- LiteLLMClient (rag_core.llm.litellm_backend, 走 litellm.acompletion)
- StubLLMClient (rag_core.llm.stub_backend, 测试用)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLMClient(Protocol):
    name: str

    async def complete(
        self,
        *,
        messages: list[dict],
        model: str,
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> LLMResponse: ...
