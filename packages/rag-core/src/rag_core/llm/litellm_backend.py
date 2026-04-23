"""LiteLLMClient: 通过 LiteLLM 调任意模型 (Haiku/Sonnet/DeepSeek/...).

要求: pip install rag-core[llm]   (litellm)
默认 model: claude-haiku-4-5-20251001 (Anthropic Haiku, 便宜适合 contextual chunking)
"""

from __future__ import annotations

from rag_core.llm.base import LLMResponse


class LiteLLMClient:
    name = "litellm"

    async def complete(
        self,
        *,
        messages: list[dict],
        model: str,
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> LLMResponse:
        try:
            import litellm
        except ImportError as e:
            raise RuntimeError(
                "litellm not installed. Run: uv pip install 'rag-core[llm]'"
            ) from e
        resp = await litellm.acompletion(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=False,
        )
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        return LLMResponse(
            text=text,
            model=model,
            input_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        )
