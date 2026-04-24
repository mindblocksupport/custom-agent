"""v1.5: workspace.allowed_tools / skill.allowed_tools 真过滤测试."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from agent_core import ToolRegistry
from agent_core.tools.protocol import Tool

from api_server.db.skills import SkillRow
from api_server.db.workspaces import WorkspaceRow
from api_server.routes.chat import _build_effective_registry

T = UUID("00000000-0000-0000-0000-000000000001")


async def _noop(**_):
    return ""


def _tool(name: str) -> Tool:
    return Tool(
        name=name, description="x",
        parameters={"type": "object", "properties": {}},
        execute=_noop,
    )


def _registry(*names: str) -> ToolRegistry:
    r = ToolRegistry()
    for n in names:
        r.register(_tool(n))
    return r


def _ws(allowed: list[str] | None = None) -> WorkspaceRow:
    return WorkspaceRow(
        id=uuid4(), tenant_id=T, name="ws", description="",
        default_model="auto",
        allowed_models=[], allowed_tools=allowed or [],
        default_collection="default", allowed_collections=["default"],
        budget_daily_usd=None, budget_monthly_usd=None,
        features={}, created_by="dev",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _skill(allowed: list[str] | None = None) -> SkillRow:
    return SkillRow(
        id=uuid4(), workspace_id=uuid4(), name="sk", description="",
        version=1, system_prompt="",
        allowed_tools=allowed or [],
        default_collections=[], starter_examples=[],
        visibility="workspace", budget_per_call_usd=None, tags=[],
        created_by="dev",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_no_workspace_no_skill_passthrough():
    base = _registry("a", "b", "c")
    eff, applied = _build_effective_registry(base, None, None)
    assert eff is base
    assert applied is None


def test_workspace_allowed_tools_filters():
    base = _registry("a", "b", "c")
    eff, applied = _build_effective_registry(base, _ws(["a", "c"]), None)
    assert eff is not base
    assert set(eff.names()) == {"a", "c"}
    assert applied == ["a", "c"]


def test_skill_overrides_workspace():
    """skill.allowed_tools 非空时优先 (skill 最具体)."""
    base = _registry("a", "b", "c")
    eff, applied = _build_effective_registry(
        base, _ws(["a", "b", "c"]), _skill(["b"]),
    )
    assert set(eff.names()) == {"b"}
    assert applied == ["b"]


def test_skill_empty_falls_back_to_workspace():
    base = _registry("a", "b", "c")
    eff, applied = _build_effective_registry(
        base, _ws(["a"]), _skill([]),
    )
    assert set(eff.names()) == {"a"}
    assert applied == ["a"]


def test_both_empty_no_filter():
    base = _registry("a", "b", "c")
    eff, applied = _build_effective_registry(
        base, _ws([]), _skill([]),
    )
    assert eff is base
    assert applied is None


def test_unknown_tool_is_skipped_silently():
    """skill 配了但 registry 没注册的 tool, 跳过, 不挂."""
    base = _registry("a", "b")
    eff, applied = _build_effective_registry(
        base, None, _skill(["a", "ghost", "b"]),
    )
    assert set(eff.names()) == {"a", "b"}
    assert applied == ["a", "b"]


def test_filtered_registry_get_schemas_only_lists_allowed():
    base = _registry("a", "b", "c")
    eff, _ = _build_effective_registry(base, None, _skill(["a"]))
    schemas = eff.get_schemas()
    names = [s["function"]["name"] for s in schemas]
    assert names == ["a"]


def test_filtered_registry_execute_blocks_others():
    """没注册的 tool 调用应抛 KeyError (Executor 转 tool_result.error)."""
    import pytest
    base = _registry("a", "b")
    eff, _ = _build_effective_registry(base, None, _skill(["a"]))

    import asyncio
    asyncio.run(eff.execute("a", {}))  # 允许的, OK
    with pytest.raises(KeyError):
        asyncio.run(eff.execute("b", {}))  # 被过滤掉的, 拒绝
