"""Agent 流式事件 schema (类型化 discriminated union)。

前端按 `type` 字段区分；JSON 形态稳定，是对外 SDK 的契约。
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field


# ===== Start =====
class StartData(BaseModel):
    model: str
    max_steps: int


class StartEvent(BaseModel):
    type: Literal["start"] = "start"
    data: StartData


# ===== Token (流式文本) =====
class TokenEvent(BaseModel):
    type: Literal["token"] = "token"
    text: str


# ===== Tool Call =====
class ToolCallData(BaseModel):
    id: str | None = None
    name: str
    arguments: str  # JSON string (LLM 原样输出)


class ToolCallEvent(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    data: ToolCallData


# ===== Tool Result =====
class ToolResultData(BaseModel):
    id: str | None = None
    name: str
    result: str | None = None
    error: str | None = None


class ToolResultEvent(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    data: ToolResultData


# ===== Done =====
class DoneData(BaseModel):
    steps: int
    cost_usd: float
    input_tokens: int = 0
    output_tokens: int = 0


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"
    data: DoneData


# ===== Retrieval (L37 §8.4 + Day 11) =====
class CitationData(BaseModel):
    """RAG 命中的单条引用 (与 rag_core.types.Citation 字段一致)."""

    doc_id: str
    chunk_id: str
    source_uri: str
    title: str | None = None
    page: int | None = None
    char_offset_start: int | None = None
    char_offset_end: int | None = None
    score: float
    snippet: str


class RetrievalStartData(BaseModel):
    tool_call_id: str | None = None
    query: str
    k: int


class RetrievalStartEvent(BaseModel):
    type: Literal["retrieval.start"] = "retrieval.start"
    data: RetrievalStartData


class RetrievalDoneData(BaseModel):
    tool_call_id: str | None = None
    citations: list[CitationData] = Field(default_factory=list)
    refused: bool = False
    refusal_reason: str | None = None
    n_dense: int = 0
    n_bm25: int = 0
    n_rerank_in: int = 0
    elapsed_ms: int | None = None


class RetrievalDoneEvent(BaseModel):
    type: Literal["retrieval.done"] = "retrieval.done"
    data: RetrievalDoneData


# ===== Error =====
class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    text: str


# Discriminated union ——前端按 type 字段路由
StreamEvent = Annotated[
    StartEvent
    | TokenEvent
    | ToolCallEvent
    | ToolResultEvent
    | RetrievalStartEvent
    | RetrievalDoneEvent
    | DoneEvent
    | ErrorEvent,
    Field(discriminator="type"),
]
