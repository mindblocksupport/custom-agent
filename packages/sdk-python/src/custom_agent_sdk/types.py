"""SDK 类型 (Pydantic models)

⚠️ 这是 schemas 包的**精简副本**(不依赖 workspace)。
SDK 是对外发布的独立包,不能引入 monorepo 内部依赖。

如果服务端 schemas 演进,需要同步更新这里。
"""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


# ============================================================
# Chat Messages (OpenAI 兼容)
# ============================================================
class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None


class ChatChoice(BaseModel):
    index: int
    message: Message
    finish_reason: str | None = None


class ChatResponse(BaseModel):
    """非流式 chat completion 响应。"""

    model: str
    choices: list[ChatChoice]


# ============================================================
# Stream Events (typed discriminated union)
# ============================================================
class StartData(BaseModel):
    model: str
    max_steps: int


class StartEvent(BaseModel):
    type: Literal["start"] = "start"
    data: StartData


class TokenEvent(BaseModel):
    type: Literal["token"] = "token"
    text: str


class ToolCallData(BaseModel):
    id: str | None = None
    name: str
    arguments: str  # JSON string (LLM 原样输出)


class ToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    data: ToolCallData


class ToolResultData(BaseModel):
    id: str | None = None
    name: str
    result: str | None = None
    error: str | None = None


class ToolResultEvent(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    data: ToolResultData


class DoneData(BaseModel):
    steps: int
    cost_usd: float
    input_tokens: int = 0
    output_tokens: int = 0


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    data: DoneData


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    text: str


StreamEvent = Annotated[
    StartEvent | TokenEvent | ToolCallEvent | ToolResultEvent | DoneEvent | ErrorEvent,
    Field(discriminator="type"),
]
