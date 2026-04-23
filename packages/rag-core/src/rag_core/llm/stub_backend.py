"""StubLLMClient: 确定性 stub for tests.

按 prompt 关键字返回模板化文本. 不消耗 token, 不联网.
"""

from __future__ import annotations

from rag_core.llm.base import LLMResponse


class StubLLMClient:
    name = "stub"

    def __init__(self, *, default_text: str = "(stub answer)") -> None:
        self.default_text = default_text
        self.calls: list[dict] = []          # 测试用, 记录所有 prompt

    async def complete(
        self, *, messages: list[dict], model: str, max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> LLMResponse:
        self.calls.append({"model": model, "messages": messages})
        last_user = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        # 简单启发式: contextual 任务 → 返回 "本片段属于 doc, 讲 X"
        if "summarize this chunk's context" in last_user.lower() or "context for" in last_user.lower():
            text = "本片段属于该文档, 讲述相关主题."
        elif "hypothetical" in last_user.lower() or "假设" in last_user:
            text = "假设答案: " + last_user[:80]
        elif "rewrite" in last_user.lower() or "variants" in last_user.lower() or "改写" in last_user:
            # multi-query stub: 输出 3 行变体
            text = "变体一\n变体二\n变体三"
        else:
            text = self.default_text
        return LLMResponse(
            text=text, model=model,
            input_tokens=len(last_user) // 4,
            output_tokens=len(text) // 4,
        )
