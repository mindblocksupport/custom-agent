"""Guardrails 单元测试"""

import pytest

from agent_core import AgentConfig
from agent_core.guardrails import GuardrailViolation, RuntimeGuard


def test_budget_within_limit():
    g = RuntimeGuard(AgentConfig(max_cost_usd=1.0))
    g.add_cost(0.5)
    g.check_budget()  # ok


def test_budget_exceeded():
    g = RuntimeGuard(AgentConfig(max_cost_usd=1.0))
    g.add_cost(1.5)
    with pytest.raises(GuardrailViolation, match="Max cost"):
        g.check_budget()


def test_loop_detection():
    g = RuntimeGuard(AgentConfig(max_loop_repeats=3))
    action = {"name": "ping", "arguments": '{"x": 1}'}
    g.check_loop(action)
    g.check_loop(action)
    with pytest.raises(GuardrailViolation, match="Loop detected"):
        g.check_loop(action)


def test_loop_different_args_ok():
    g = RuntimeGuard(AgentConfig(max_loop_repeats=3))
    g.check_loop({"name": "ping", "arguments": '{"x": 1}'})
    g.check_loop({"name": "ping", "arguments": '{"x": 2}'})
    g.check_loop({"name": "ping", "arguments": '{"x": 3}'})  # ok


def test_consecutive_tool_errors():
    g = RuntimeGuard(AgentConfig(max_consecutive_tool_errors=3))
    g.record_tool_error()
    g.record_tool_error()
    with pytest.raises(GuardrailViolation, match="Too many consecutive"):
        g.record_tool_error()


def test_reset_clears_counter():
    g = RuntimeGuard(AgentConfig(max_consecutive_tool_errors=3))
    g.record_tool_error()
    g.record_tool_error()
    g.reset_tool_errors()
    g.record_tool_error()  # 0 -> 1, no raise
