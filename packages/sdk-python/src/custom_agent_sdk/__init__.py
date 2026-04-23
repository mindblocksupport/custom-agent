"""Custom Agent Platform · Python SDK

Quick start:
    import asyncio
    from custom_agent_sdk import Client

    async def main():
        async with Client(api_key="...") as client:
            async for event in client.chat.completions.stream(
                messages=[{"role": "user", "content": "hi"}],
                model="deepseek/deepseek-chat",
            ):
                if event.type == "token":
                    print(event.text, end="")

    asyncio.run(main())
"""

from custom_agent_sdk.client import Client
from custom_agent_sdk.exceptions import (
    AgentError,
    AuthError,
    RateLimitError,
    ServerError,
    StreamError,
    TimeoutError,
)
from custom_agent_sdk.types import (
    ChatChoice,
    ChatResponse,
    DoneData,
    DoneEvent,
    ErrorEvent,
    Message,
    StartData,
    StartEvent,
    StreamEvent,
    TokenEvent,
    ToolCallData,
    ToolCallEvent,
    ToolResultData,
    ToolResultEvent,
)

__version__ = "0.1.0"

__all__ = [
    # Client
    "Client",
    # Exceptions
    "AgentError",
    "AuthError",
    "RateLimitError",
    "ServerError",
    "StreamError",
    "TimeoutError",
    # Types - chat
    "Message",
    "ChatChoice",
    "ChatResponse",
    # Types - events
    "StreamEvent",
    "StartEvent",
    "StartData",
    "TokenEvent",
    "ToolCallEvent",
    "ToolCallData",
    "ToolResultEvent",
    "ToolResultData",
    "DoneEvent",
    "DoneData",
    "ErrorEvent",
]
