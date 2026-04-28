"""Chat 请求 / 响应 schema (OpenAI 兼容)。"""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """单条消息——OpenAI / Anthropic 兼容形态。

    `content` 可以是:
    - str: 纯文本 (主路径, 跟以前一致)
    - list[dict]: multimodal content parts. OpenAI vision 兼容:
        [
          {"type": "text", "text": "What's this?"},
          {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
        ]
      LiteLLM gateway 直接透传给 vision-capable model.
    - None: tool 消息 (用 tool_call_id + 单独 result 字段)
    """

    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[dict[str, Any]] | None = None
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
    # Skill 模板变量替换 — skill.system_prompt 中的 {{ var }} 会被替换
    # 仅替换字面 {{ name }} (Mustache 子集), 缺失的变量保留原文.
    skill_vars: dict[str, str] = Field(default_factory=dict)
