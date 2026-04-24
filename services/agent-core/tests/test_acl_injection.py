"""Day 2 P0 #3: Executor token 注入 + ToolRegistry schema 剥字段."""

import json

import pytest

from agent_core.runtime.executor import Executor
from agent_core.tools.protocol import Tool
from agent_core.tools.registry import _SYSTEM_ARG_KEYS, ToolRegistry


@pytest.fixture
def captured():
    """工具记录每次被调用的 kwargs."""
    return []


def _make_tool(name: str, requires_acl: bool, captured: list, schema: dict | None = None):
    async def _exec(**kwargs):
        captured.append({"name": name, "kwargs": dict(kwargs)})
        return f"ok:{name}"
    return Tool(
        name=name,
        description="test",
        parameters=schema or {"type": "object", "properties": {}},
        execute=_exec,
        requires_acl=requires_acl,
    )


def test_schema_stripsprincipal_token():
    schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "principal_token": {"type": "string"},
        },
        "required": ["query", "principal_token"],
    }
    tool = _make_tool("search_kb", True, [], schema)
    reg = ToolRegistry([tool])
    [s] = reg.get_schemas()
    props = s["function"]["parameters"]["properties"]
    req = s["function"]["parameters"]["required"]
    assert "query" in props
    assert "principal_token" not in props
    assert "principal_token" not in req
    assert "query" in req


@pytest.mark.asyncio
async def test_executor_injects_token_for_requires_acl(captured):
    tool = _make_tool("search_kb", requires_acl=True, captured=captured)
    reg = ToolRegistry([tool])
    ex = Executor(reg, token_provider=lambda: "TOKEN-123")
    tool_calls = [{
        "id": "c1",
        "function": {"name": "search_kb", "arguments": '{"query":"hi"}'},
    }]
    events = [e async for e in ex.stream(tool_calls)]
    assert events  # tool_call + tool_result
    assert captured[0]["kwargs"] == {"query": "hi", "principal_token": "TOKEN-123"}


@pytest.mark.asyncio
async def test_executor_skips_injection_for_non_acl_tool(captured):
    tool = _make_tool("get_time", requires_acl=False, captured=captured)
    reg = ToolRegistry([tool])
    ex = Executor(reg, token_provider=lambda: "TOKEN-123")
    tool_calls = [{
        "id": "c1",
        "function": {"name": "get_time", "arguments": '{"tz":"UTC"}'},
    }]
    [_ for _ in [e async for e in ex.stream(tool_calls)]]
    assert "principal_token" not in captured[0]["kwargs"]
    assert captured[0]["kwargs"] == {"tz": "UTC"}


@pytest.mark.asyncio
async def test_executor_no_token_provider_no_injection(captured):
    tool = _make_tool("search_kb", requires_acl=True, captured=captured)
    reg = ToolRegistry([tool])
    ex = Executor(reg, token_provider=None)  # 没注入器
    tool_calls = [{
        "id": "c1",
        "function": {"name": "search_kb", "arguments": "{}"},
    }]
    [_ for _ in [e async for e in ex.stream(tool_calls)]]
    assert "principal_token" not in captured[0]["kwargs"]


@pytest.mark.asyncio
async def test_executor_overrides_llm_supplied_token(captured):
    """LLM 学会塞 principal_token 也会被覆盖, 不能伪造身份."""
    tool = _make_tool("search_kb", requires_acl=True, captured=captured)
    reg = ToolRegistry([tool])
    ex = Executor(reg, token_provider=lambda: "TRUSTED-TOKEN")
    # LLM 试图传一个伪造 token
    tool_calls = [{
        "id": "c1",
        "function": {"name": "search_kb",
                      "arguments": '{"query":"x","principal_token":"FAKE"}'},
    }]
    [_ for _ in [e async for e in ex.stream(tool_calls)]]
    assert captured[0]["kwargs"]["principal_token"] == "TRUSTED-TOKEN"


@pytest.mark.asyncio
async def test_executor_emits_original_args_in_tool_call_event(captured):
    """前端/LLM 看到的 ToolCallEvent.arguments 不能含 token."""
    tool = _make_tool("search_kb", requires_acl=True, captured=captured)
    reg = ToolRegistry([tool])
    ex = Executor(reg, token_provider=lambda: "SECRET")
    tool_calls = [{
        "id": "c1",
        "function": {"name": "search_kb", "arguments": '{"query":"hi"}'},
    }]
    events = [e async for e in ex.stream(tool_calls)]
    tc_events = [e for e in events if e.type == "tool_call"]
    assert tc_events
    # ToolCallEvent.data.arguments 是原版, 不含 principal_token
    assert "principal_token" not in tc_events[0].data.arguments
    assert "SECRET" not in tc_events[0].data.arguments


def test_system_arg_keys_includesprincipal_token():
    """sanity: 防漏字段."""
    assert "principal_token" in _SYSTEM_ARG_KEYS
