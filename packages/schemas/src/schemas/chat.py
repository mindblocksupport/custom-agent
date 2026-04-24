"""Chat 请求 / 响应 schema (OpenAI 兼容)。"""

from typing import Any, Literal
from uuid import UUID

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
    # Day 4 P0 #7: 关联 session, 服务器自动持久化每轮
    session_id: UUID | None = None
    # v1.5 沉淀层: 指定 workspace + skill (二选一)
    workspace_id: UUID | None = None
    skill_id: UUID | None = None
