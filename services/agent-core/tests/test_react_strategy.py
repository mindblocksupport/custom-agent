"""ReActStrategy 集成测试 (mock LLM)"""

from collections.abc import AsyncIterator
from typing import Any

import pytest

from agent_core import AgentConfig, ReActStrategy, Tool, ToolRegistry


# ============================================================
# Fake LLM streams
# ============================================================
async def _llm_no_tool(*args, **kwargs) -> AsyncIterator[dict[str, Any]]:
    """直接给最终答案 (无 tool call) → 1 步完成。"""
    for d in ["Hello ", "world"]:
        yield {"type": "text", "delta": d}


async def _llm_one_tool_then_text(*args, **kwargs) -> AsyncIterator[dict[str, Any]]:
    """第 1 次给 tool call,第 2 次给 text。需要外部计数器。"""
    if not _llm_one_tool_then_text.called:
        _llm_one_tool_then_text.called = True
        yield {
            "type": "tool_call",
            "data": {"id": "c1", "function": {"name": "ping", "arguments": '{"text":"hi"}'}},
        }
    else:
        for d in ["got ", "result"]:
            yield {"type": "text", "delta": d}
_llm_one_tool_then_text.called = False  # type: ignore[attr-defined]


async def _llm_loop_same_tool(*args, **kwargs) -> AsyncIterator[dict[str, Any]]:
    """每次都返回同一个 tool call → 应触发死循环 guard。"""
    yield {
        "type": "tool_call",
        "data": {"id": "c", "function": {"name": "ping", "arguments": "{}"}},
    }


# ============================================================
# Fixtures
# ============================================================
async def _ping(**kwargs) -> str:
    return "pong"


@pytest.fixture
def registry() -> ToolRegistry:
    r = ToolRegistry()
    r.register(
        Tool(
            name="ping",
            description="ping",
            parameters={"type": "object", "properties": {}, "required": []},
            execute=_ping,
        )
    )
    return r


# ============================================================
# Tests
# ============================================================
@pytest.mark.asyncio
async def test_react_no_tool_one_step(monkeypatch, registry):
    monkeypatch.setattr("agent_core.runtime.planner.llm_complete_stream", _llm_no_tool)
    s = ReActStrategy()
    events = [
        ev
        async for ev in s.run(
            messages=[{"role": "user", "content": "hi"}],
            model="fake",
            registry=registry,
            config=AgentConfig(),
        )
    ]
    types = [e.type for e in events]
    assert types[0] == "start"
    assert types[-1] == "done"
    # 中间应该有 token events
    assert "token" in types
    # done 数据
    done = events[-1]
    assert done.data.steps == 1


@pytest.mark.asyncio
async def test_react_with_tool(monkeypatch, registry):
    _llm_one_tool_then_text.called = False  # type: ignore[attr-defined]
    monkeypatch.setattr(
        "agent_core.runtime.planner.llm_complete_stream", _llm_one_tool_then_text
    )
    s = ReActStrategy()
    events = [
        ev
        async for ev in s.run(
            messages=[{"role": "user", "content": "hi"}],
            model="fake",
            registry=registry,
            config=AgentConfig(),
        )
    ]
    types = [e.type for e in events]
    assert "tool_call" in types
    assert "tool_result" in types
    assert types[-1] == "done"
    assert events[-1].data.steps == 2


@pytest.mark.asyncio
async def test_react_loop_guard(monkeypatch, registry):
    monkeypatch.setattr(
        "agent_core.runtime.planner.llm_complete_stream", _llm_loop_same_tool
    )
    s = ReActStrategy()
    events = [
        ev
        async for ev in s.run(
            messages=[{"role": "user", "content": "hi"}],
            model="fake",
            registry=registry,
            config=AgentConfig(max_loop_repeats=3, max_steps=10),
        )
    ]
    # 死循环 guard 应该在第 3 次同 action 时触发
    assert events[-1].type == "error"
    assert "Loop detected" in events[-1].text
