"""Executor 单元测试"""

import pytest

from agent_core import Tool, ToolRegistry
from agent_core.runtime.executor import Executor


async def _ok_tool(text: str) -> str:
    return f"echo:{text}"


async def _bad_tool(**_kwargs) -> str:
    raise RuntimeError("boom")


@pytest.fixture
def registry() -> ToolRegistry:
    r = ToolRegistry()
    r.register(
        Tool(
            name="ok",
            description="ok",
            parameters={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            execute=_ok_tool,
        )
    )
    r.register(
        Tool(
            name="bad",
            description="bad",
            parameters={"type": "object", "properties": {}},
            execute=_bad_tool,
        )
    )
    return r


@pytest.mark.asyncio
async def test_executor_success(registry):
    ex = Executor(registry)
    calls = [{"id": "c1", "function": {"name": "ok", "arguments": '{"text": "hi"}'}}]
    events = [ev async for ev in ex.stream(calls)]
    # 1 ToolCallEvent + 1 ToolResultEvent
    assert len(events) == 2
    assert events[0].type == "tool_call"
    assert events[1].type == "tool_result"
    assert events[1].data.result == "echo:hi"
    assert ex.last_results[0].succeeded


@pytest.mark.asyncio
async def test_executor_error_captured(registry):
    ex = Executor(registry)
    calls = [{"id": "c2", "function": {"name": "bad", "arguments": "{}"}}]
    events = [ev async for ev in ex.stream(calls)]
    assert events[1].type == "tool_result"
    assert events[1].data.error is not None
    assert "boom" in events[1].data.error
    assert not ex.last_results[0].succeeded


@pytest.mark.asyncio
async def test_executor_multiple_calls(registry):
    ex = Executor(registry)
    calls = [
        {"id": "c1", "function": {"name": "ok", "arguments": '{"text": "a"}'}},
        {"id": "c2", "function": {"name": "ok", "arguments": '{"text": "b"}'}},
    ]
    events = [ev async for ev in ex.stream(calls)]
    # 2 ToolCallEvent + 2 ToolResultEvent
    assert len(events) == 4
    assert sum(1 for e in events if e.type == "tool_call") == 2
    assert sum(1 for e in events if e.type == "tool_result") == 2
    assert len(ex.last_results) == 2
