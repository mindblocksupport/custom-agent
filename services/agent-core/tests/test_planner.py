"""Planner 单元测试 (mock LLM stream)"""

from collections.abc import AsyncIterator
from typing import Any

import pytest

from agent_core.runtime.planner import Planner


async def _fake_llm_stream(*args, **kwargs) -> AsyncIterator[dict[str, Any]]:
    """Fake LLM 流: 几个 token + 一个 tool_call。"""
    for delta in ["Hello ", "world"]:
        yield {"type": "text", "delta": delta}
    yield {"type": "tool_call", "data": {"id": "c1", "function": {"name": "ping", "arguments": "{}"}}}
    yield {"type": "usage", "cost": 0.001}


@pytest.mark.asyncio
async def test_planner_collects_state(monkeypatch):
    monkeypatch.setattr("agent_core.runtime.planner.llm_complete_stream", _fake_llm_stream)
    p = Planner()
    events = [ev async for ev in p.stream([{"role": "user", "content": "hi"}], model="x")]
    # 流式只返 TokenEvent (2 个)
    assert len(events) == 2
    assert all(e.type == "token" for e in events)
    # 内部状态正确累积
    assert p.last_text == "Hello world"
    assert len(p.last_tool_calls) == 1
    assert p.last_tool_calls[0]["function"]["name"] == "ping"
    assert p.last_cost_usd == pytest.approx(0.001)


@pytest.mark.asyncio
async def test_planner_reset_between_calls(monkeypatch):
    monkeypatch.setattr("agent_core.runtime.planner.llm_complete_stream", _fake_llm_stream)
    p = Planner()
    _ = [ev async for ev in p.stream([{"role": "user", "content": "first"}], model="x")]
    assert p.last_text == "Hello world"
    _ = [ev async for ev in p.stream([{"role": "user", "content": "second"}], model="x")]
    # 第二次开始前应 reset
    assert p.last_text == "Hello world"  # accumulated again from same fake
    assert p.last_cost_usd == pytest.approx(0.001)  # not 0.002
