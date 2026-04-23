"""跨服务共享的 Pydantic schema。

不依赖任何业务逻辑——只描述数据结构。
"""

from schemas.chat import ChatMessage, ChatRequest
from schemas.events import (
    CitationData,
    DoneData,
    DoneEvent,
    ErrorEvent,
    RetrievalDoneData,
    RetrievalDoneEvent,
    RetrievalStartData,
    RetrievalStartEvent,
    StartData,
    StartEvent,
    StreamEvent,
    TokenEvent,
    ToolCallData,
    ToolCallEvent,
    ToolResultData,
    ToolResultEvent,
)

__all__ = [
    "ChatMessage",
    "ChatRequest",
    "CitationData",
    "StreamEvent",
    "StartEvent",
    "StartData",
    "TokenEvent",
    "ToolCallEvent",
    "ToolCallData",
    "ToolResultEvent",
    "ToolResultData",
    "RetrievalStartEvent",
    "RetrievalStartData",
    "RetrievalDoneEvent",
    "RetrievalDoneData",
    "DoneEvent",
    "DoneData",
    "ErrorEvent",
]
