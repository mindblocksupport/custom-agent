"""Chat 请求 / 响应 schema (OpenAI 兼容)。"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """单条消息——OpenAI / Anthropic 兼容形态。"""

    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


class ChatRequest(BaseModel):
    """`POST /v1/chat/completions` 请求体。"""

    messages: list[ChatMessage]
    model: str | None = None
    stream: bool = True
    temperature: float | None = None
    max_tokens: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
