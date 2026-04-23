"""Custom Agent Platform · Async Client

设计:
- 异步优先 (httpx.AsyncClient)
- async context manager 自动关闭连接
- 类型化事件 (Pydantic 解析)
- OpenAI 兼容 + 我们的扩展 (typed events / convenience methods)
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx
from pydantic import TypeAdapter, ValidationError

from custom_agent_sdk.exceptions import (
    AgentError,
    AuthError,
    RateLimitError,
    ServerError,
    StreamError,
    TimeoutError,
)
from custom_agent_sdk.types import ChatResponse, StreamEvent

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT = 120.0

_event_adapter: TypeAdapter[StreamEvent] = TypeAdapter(StreamEvent)


# ============================================================
# Public Client
# ============================================================
class Client:
    """Custom Agent Platform 异步客户端。

    用法:
        async with Client(api_key="...") as client:
            async for event in client.chat.completions.stream(messages=[...], model="..."):
                ...

    环境变量:
        CUSTOM_AGENT_API_KEY  - 默认 api_key
        CUSTOM_AGENT_BASE_URL - 默认 base_url
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        default_model: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        api_key = api_key or os.getenv("CUSTOM_AGENT_API_KEY")
        if not api_key:
            raise ValueError(
                "api_key required (pass api_key=... or set CUSTOM_AGENT_API_KEY env var)"
            )
        base_url = (base_url or os.getenv("CUSTOM_AGENT_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")

        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model
        self.timeout = timeout

        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=timeout,
        )
        # 子接口
        self.chat = _Chat(self)

    # ----- lifecycle -----
    async def close(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> Client:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    # ----- 高层便捷接口 -----
    async def ask(
        self,
        prompt: str,
        *,
        model: str | None = None,
        system: str | None = None,
    ) -> str:
        """最简一句话: 给个 prompt, 直接拿完整回答。

        合并所有 token,丢弃工具/进度细节。
        想要细节请用 `client.chat.completions.stream(...)`。
        """
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        text_parts: list[str] = []
        async for event in self.chat.completions.stream(messages=messages, model=model):
            if event.type == "token":
                text_parts.append(event.text)
            elif event.type == "error":
                raise AgentError(event.text)
        return "".join(text_parts)


# ============================================================
# Chat namespace
# ============================================================
class _Chat:
    def __init__(self, client: Client) -> None:
        self.completions = _ChatCompletions(client)


class _ChatCompletions:
    def __init__(self, client: Client) -> None:
        self._client = client

    # ---------- 非流式 ----------
    async def create(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChatResponse:
        """OpenAI Chat Completions 兼容 - 非流式。"""
        body = self._build_body(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            metadata=metadata,
            stream=False,
        )
        try:
            r = await self._client._http.post("/v1/chat/completions", json=body)
        except httpx.TimeoutException as e:
            raise TimeoutError(f"Request timed out after {self._client.timeout}s") from e
        except httpx.HTTPError as e:
            raise AgentError(f"HTTP error: {e}") from e

        _raise_for_status(r)
        return ChatResponse.model_validate(r.json())

    # ---------- 流式 ----------
    async def stream(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """OpenAI Chat Completions 兼容 - SSE 流式。

        Yields:
            类型化事件 (StartEvent / TokenEvent / ToolCallEvent / ...)
        """
        body = self._build_body(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            metadata=metadata,
            stream=True,
        )

        try:
            async with self._client._http.stream(
                "POST",
                "/v1/chat/completions",
                json=body,
            ) as response:
                if response.status_code >= 400:
                    body_text = await response.aread()
                    _raise_for_status_text(response.status_code, body_text.decode("utf-8", "replace"))

                async for event in _parse_sse(response):
                    yield event
        except httpx.TimeoutException as e:
            raise TimeoutError(f"Stream timed out after {self._client.timeout}s") from e

    # ---------- 内部 ----------
    def _build_body(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None,
        temperature: float | None,
        max_tokens: int | None,
        metadata: dict[str, Any] | None,
        stream: bool,
    ) -> dict[str, Any]:
        m = model or self._client.default_model
        body: dict[str, Any] = {"messages": messages, "stream": stream}
        if m is not None:
            body["model"] = m
        if temperature is not None:
            body["temperature"] = temperature
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        if metadata is not None:
            body["metadata"] = metadata
        return body


# ============================================================
# 内部工具
# ============================================================
def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code < 400:
        return
    _raise_for_status_text(r.status_code, r.text)


def _raise_for_status_text(status: int, body: str) -> None:
    msg = f"HTTP {status}: {body[:200]}"
    if status == 401:
        raise AuthError(msg, status=status, body=body)
    if status == 429:
        raise RateLimitError(msg, status=status, body=body)
    if 500 <= status < 600:
        raise ServerError(msg, status=status, body=body)
    raise AgentError(msg, status=status, body=body)


async def _parse_sse(response: httpx.Response) -> AsyncIterator[StreamEvent]:
    """SSE 解析 - 服务端按 \\n\\n 分隔事件,每事件多行 (event: / data: / id: ...)。

    我们只关心 `data:` 行的 JSON 内容。
    """
    buffer = ""
    async for chunk in response.aiter_text():
        buffer += chunk
        # SSE spec 允许 \r\n / \n / \r 作行终止
        buffer = buffer.replace("\r\n", "\n").replace("\r", "\n")
        events, _, buffer = _split_events(buffer)
        for ev in events:
            for parsed in _parse_one_event(ev):
                yield parsed

    # flush remainder
    if buffer.strip():
        for parsed in _parse_one_event(buffer):
            yield parsed


def _split_events(buffer: str) -> tuple[list[str], str, str]:
    """split on \\n\\n, return (complete_events, separator, remainder)。"""
    parts = buffer.split("\n\n")
    return parts[:-1], "\n\n", parts[-1]


def _parse_one_event(raw: str) -> list[StreamEvent]:
    if not raw.strip():
        return []
    data_lines: list[str] = []
    for line in raw.split("\n"):
        if line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if not data_lines:
        return []
    payload = "\n".join(data_lines)
    if payload == "[DONE]":
        return []
    try:
        obj = json.loads(payload)
    except json.JSONDecodeError as e:
        raise StreamError(f"Failed to parse SSE data: {payload[:100]}") from e
    try:
        return [_event_adapter.validate_python(obj)]
    except ValidationError as e:
        raise StreamError(f"SSE event validation failed: {e}") from e
