"""SDK 单测 (用 httpx.MockTransport 替真实 HTTP)"""

import json

import httpx
import pytest

from custom_agent_sdk import (
    AgentError,
    AuthError,
    Client,
    DoneEvent,
    StartEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
)


# ============================================================
# Helpers
# ============================================================
def _make_mock_transport(handler):
    """httpx.MockTransport 包装。"""
    return httpx.MockTransport(handler)


def _client_with(handler) -> Client:
    transport = _make_mock_transport(handler)
    http = httpx.AsyncClient(
        base_url="http://test",
        headers={"Authorization": "Bearer test-key"},
        transport=transport,
    )
    return Client(api_key="test-key", base_url="http://test", http_client=http)


# ============================================================
# Non-stream
# ============================================================
@pytest.mark.asyncio
async def test_create_basic():
    def handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        assert body["stream"] is False
        assert body["messages"][0]["content"] == "hi"
        return httpx.Response(
            200,
            json={
                "model": "fake",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "hello back"},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    async with _client_with(handler) as c:
        resp = await c.chat.completions.create(
            messages=[{"role": "user", "content": "hi"}], model="fake"
        )
        assert resp.choices[0].message.content == "hello back"


# ============================================================
# Auth error
# ============================================================
@pytest.mark.asyncio
async def test_auth_error():
    def handler(req):
        return httpx.Response(401, json={"detail": "Invalid API key"})

    async with _client_with(handler) as c:
        with pytest.raises(AuthError) as exc:
            await c.chat.completions.create(
                messages=[{"role": "user", "content": "hi"}], model="fake"
            )
        assert exc.value.status == 401


# ============================================================
# Stream
# ============================================================
def _sse_response(events: list[tuple[str, dict | str]]) -> bytes:
    """构造 SSE 字节流。"""
    out = []
    for ev_name, data in events:
        out.append(f"event: {ev_name}")
        payload = data if isinstance(data, str) else json.dumps(data)
        out.append(f"data: {payload}")
        out.append("")  # blank line = separator
    return ("\n".join(out) + "\n").encode("utf-8")


@pytest.mark.asyncio
async def test_stream_basic():
    sse = _sse_response(
        [
            ("start", {"type": "start", "data": {"model": "fake", "max_steps": 15}}),
            ("token", {"type": "token", "text": "Hello "}),
            ("token", {"type": "token", "text": "world"}),
            ("done", {"type": "done", "data": {"steps": 1, "cost_usd": 0.001}}),
            ("done", "[DONE]"),
        ]
    )

    def handler(req):
        body = json.loads(req.content)
        assert body["stream"] is True
        return httpx.Response(
            200,
            content=sse,
            headers={"content-type": "text/event-stream"},
        )

    async with _client_with(handler) as c:
        events = []
        async for ev in c.chat.completions.stream(
            messages=[{"role": "user", "content": "hi"}], model="fake"
        ):
            events.append(ev)

    types = [e.type for e in events]
    assert types == ["start", "token", "token", "done"]
    assert isinstance(events[0], StartEvent)
    assert isinstance(events[1], TokenEvent)
    assert events[1].text == "Hello "
    assert isinstance(events[3], DoneEvent)
    assert events[3].data.steps == 1


@pytest.mark.asyncio
async def test_stream_with_tools():
    sse = _sse_response(
        [
            ("start", {"type": "start", "data": {"model": "fake", "max_steps": 15}}),
            (
                "tool_call",
                {
                    "type": "tool_call",
                    "data": {"id": "c1", "name": "calculator", "arguments": '{"x":1}'},
                },
            ),
            (
                "tool_result",
                {
                    "type": "tool_result",
                    "data": {"id": "c1", "name": "calculator", "result": "42"},
                },
            ),
            ("token", {"type": "token", "text": "Done."}),
            ("done", {"type": "done", "data": {"steps": 2, "cost_usd": 0.002}}),
        ]
    )

    def handler(req):
        return httpx.Response(200, content=sse, headers={"content-type": "text/event-stream"})

    async with _client_with(handler) as c:
        events = [
            ev async for ev in c.chat.completions.stream(
                messages=[{"role": "user", "content": "hi"}], model="fake"
            )
        ]

    tc = [e for e in events if isinstance(e, ToolCallEvent)][0]
    tr = [e for e in events if isinstance(e, ToolResultEvent)][0]
    assert tc.data.name == "calculator"
    assert tr.data.result == "42"


# ============================================================
# Convenience: ask()
# ============================================================
@pytest.mark.asyncio
async def test_ask():
    sse = _sse_response(
        [
            ("start", {"type": "start", "data": {"model": "fake", "max_steps": 15}}),
            ("token", {"type": "token", "text": "Paris"}),
            ("token", {"type": "token", "text": "."}),
            ("done", {"type": "done", "data": {"steps": 1, "cost_usd": 0.0}}),
        ]
    )

    def handler(req):
        return httpx.Response(200, content=sse, headers={"content-type": "text/event-stream"})

    async with _client_with(handler) as c:
        text = await c.ask("Capital of France?", model="fake")
        assert text == "Paris."


# ============================================================
# Validation: missing api_key
# ============================================================
def test_missing_api_key(monkeypatch):
    monkeypatch.delenv("CUSTOM_AGENT_API_KEY", raising=False)
    with pytest.raises(ValueError, match="api_key required"):
        Client()  # no api_key, no env var


def test_env_var_api_key(monkeypatch):
    monkeypatch.setenv("CUSTOM_AGENT_API_KEY", "env-key")
    c = Client()
    assert c.api_key == "env-key"


# ============================================================
# CRLF SSE handling (regression test for the chat.html bug)
# ============================================================
@pytest.mark.asyncio
async def test_stream_crlf_line_endings():
    body = b"event: token\r\ndata: {\"type\":\"token\",\"text\":\"ok\"}\r\n\r\n"

    def handler(req):
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    async with _client_with(handler) as c:
        events = [
            ev async for ev in c.chat.completions.stream(
                messages=[{"role": "user", "content": "x"}], model="fake"
            )
        ]
        assert len(events) == 1
        assert isinstance(events[0], TokenEvent)
        assert events[0].text == "ok"
