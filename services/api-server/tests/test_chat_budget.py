"""Workspace budget pre-check 测试.

只测拦截路径 (true positives + true negatives), 不真发 LLM.
"""

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from api_server.db.workspaces import BudgetUsage, WorkspaceRow
from api_server.main import app

AUTH = {"Authorization": "Bearer dev-key-change-me"}
TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _ws(
    wid: UUID | None = None,
    daily: float | None = None,
    monthly: float | None = None,
) -> WorkspaceRow:
    return WorkspaceRow(
        id=wid or uuid4(),
        tenant_id=TENANT, name="测试空间",
        description="",
        default_model="auto",
        allowed_models=[], allowed_tools=[],
        default_collection="default",
        allowed_collections=["default"],
        budget_daily_usd=daily,
        budget_monthly_usd=monthly,
        features={},
        created_by="dev",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _budget(today: float, month: float, daily_limit: float | None,
            monthly_limit: float | None) -> BudgetUsage:
    return BudgetUsage(
        today_cost_usd=today, month_cost_usd=month,
        budget_daily_usd=daily_limit,
        budget_monthly_usd=monthly_limit,
    )


def test_budget_property_logic():
    # 没设 budget → 永远不算超
    assert _budget(100, 100, None, None).any_exceeded is False
    # 日预算超 (today >= limit)
    assert _budget(5, 0, 5, None).daily_exceeded is True
    assert _budget(5, 0, 5, None).any_exceeded is True
    # 月预算超
    assert _budget(0, 100, None, 100).monthly_exceeded is True
    # 没超
    assert _budget(3, 50, 5, 100).any_exceeded is False


def test_chat_blocked_by_daily_budget():
    wid = uuid4()
    ws = _ws(wid=wid, daily=1.0)
    body = {
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
        "workspace_id": str(wid),
    }
    with patch(
        "api_server.routes.chat._resolve_workspace_skill",
        return_value=(ws, None),
    ), patch(
        "api_server.routes.chat.ws_db.fetch_budget_usage",
        return_value=_budget(today=1.5, month=2.0, daily_limit=1.0, monthly_limit=10.0),
    ), TestClient(app) as client:
        r = client.post("/v1/chat/completions", json=body, headers=AUTH)
        assert r.status_code == 402, r.text
        body_json = r.json()
        assert body_json["detail"]["code"] == "budget_exceeded"
        assert body_json["detail"]["scope"] == "daily"
        assert body_json["detail"]["limit_usd"] == 1.0
        assert body_json["detail"]["used_usd"] == 1.5


def test_chat_blocked_by_monthly_budget():
    wid = uuid4()
    ws = _ws(wid=wid, monthly=20.0)
    body = {
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
        "workspace_id": str(wid),
    }
    with patch(
        "api_server.routes.chat._resolve_workspace_skill",
        return_value=(ws, None),
    ), patch(
        "api_server.routes.chat.ws_db.fetch_budget_usage",
        return_value=_budget(today=0.5, month=20.5, daily_limit=None, monthly_limit=20.0),
    ), TestClient(app) as client:
        r = client.post("/v1/chat/completions", json=body, headers=AUTH)
        assert r.status_code == 402, r.text
        assert r.json()["detail"]["scope"] == "monthly"


def test_chat_passes_when_no_budget_set():
    """没设 budget → 跳过预检, 走原路径 (会因没 mock LLM 报别的错, 关键: 不是 402)"""
    wid = uuid4()
    ws = _ws(wid=wid)
    body = {
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
        "workspace_id": str(wid),
    }
    with patch(
        "api_server.routes.chat._resolve_workspace_skill",
        return_value=(ws, None),
    ), patch(
        "api_server.routes.chat.ws_db.fetch_budget_usage",
        return_value=_budget(today=999, month=999, daily_limit=None, monthly_limit=None),
    ), TestClient(app) as client:
        r = client.post("/v1/chat/completions", json=body, headers=AUTH)
        # 不应该是 402; 后续会 500 因 LLM 没 mock, 这里只关心不被预算拦
        assert r.status_code != 402


def test_chat_passes_when_under_budget():
    wid = uuid4()
    ws = _ws(wid=wid, daily=10.0, monthly=100.0)
    body = {
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
        "workspace_id": str(wid),
    }
    with patch(
        "api_server.routes.chat._resolve_workspace_skill",
        return_value=(ws, None),
    ), patch(
        "api_server.routes.chat.ws_db.fetch_budget_usage",
        return_value=_budget(today=5.0, month=50.0, daily_limit=10.0, monthly_limit=100.0),
    ), TestClient(app) as client:
        r = client.post("/v1/chat/completions", json=body, headers=AUTH)
        assert r.status_code != 402


def test_chat_blocked_records_audit():
    """超限拦截会写一条 workspace.budget_exceeded audit"""
    wid = uuid4()
    ws = _ws(wid=wid, daily=1.0)
    body = {
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
        "workspace_id": str(wid),
    }
    seen: dict = {}
    def _ins(**kw):
        seen.update(kw)
        return 1
    with patch(
        "api_server.routes.chat._resolve_workspace_skill",
        return_value=(ws, None),
    ), patch(
        "api_server.routes.chat.ws_db.fetch_budget_usage",
        return_value=_budget(today=2.0, month=5.0, daily_limit=1.0, monthly_limit=None),
    ), patch(
        "api_server.db.audit.insert", side_effect=_ins,
    ), TestClient(app) as client:
        r = client.post("/v1/chat/completions", json=body, headers=AUTH)
        assert r.status_code == 402
    assert seen.get("action") == "workspace.budget_exceeded"
    assert seen["detail"]["scope"] == "daily"
    assert seen["detail"]["used_usd"] == 2.0


def test_chat_blocked_by_disallowed_model():
    """workspace.allowed_models 白名单 enforce: 模型不在 → 403"""
    wid = uuid4()
    ws = _ws(wid=wid)
    # allowed_models 不空 + 不含 deepseek-chat → 拒绝
    ws.allowed_models = ["anthropic/claude-sonnet-4-6"]
    body = {
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
        "workspace_id": str(wid),
        "model": "deepseek/deepseek-chat",  # 显式
    }
    with patch(
        "api_server.routes.chat._resolve_workspace_skill",
        return_value=(ws, None),
    ), patch(
        "api_server.routes.chat.ws_db.fetch_budget_usage",
        return_value=_budget(today=0, month=0, daily_limit=None, monthly_limit=None),
    ), TestClient(app) as client:
        r = client.post("/v1/chat/completions", json=body, headers=AUTH)
        assert r.status_code == 403, r.text
        body_json = r.json()
        assert body_json["detail"]["code"] == "model_not_allowed"
        assert "anthropic/claude-sonnet-4-6" in body_json["detail"]["allowed"]


def test_chat_blocked_by_actor_daily_budget():
    """actor 维度 budget 超限 → 402 + code=actor_budget_exceeded"""
    wid = uuid4()
    ws = _ws(wid=wid)
    body = {
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
        "workspace_id": str(wid),
    }
    actor_b = _budget(today=3.0, month=5.0, daily_limit=2.0, monthly_limit=10.0)
    with patch(
        "api_server.routes.chat._resolve_workspace_skill",
        return_value=(ws, None),
    ), patch(
        "api_server.routes.chat.ws_db.fetch_actor_budget_usage",
        return_value=actor_b,
    ), patch(
        "api_server.routes.chat.ws_db.fetch_budget_usage",
        return_value=_budget(0, 0, None, None),
    ), TestClient(app) as client:
        r = client.post("/v1/chat/completions", json=body, headers=AUTH)
        assert r.status_code == 402, r.text
        body_json = r.json()
        assert body_json["detail"]["code"] == "actor_budget_exceeded"
        assert body_json["detail"]["scope"] == "daily"
        assert body_json["detail"]["limit_usd"] == 2.0


def test_chat_actor_budget_takes_priority_over_workspace():
    """同时超限 → 优先报 actor (更具体, 业务上更想知道)"""
    wid = uuid4()
    ws = _ws(wid=wid, daily=10.0)
    body = {
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
        "workspace_id": str(wid),
    }
    actor_b = _budget(today=2.0, month=0, daily_limit=1.0, monthly_limit=None)
    ws_b = _budget(today=11.0, month=0, daily_limit=10.0, monthly_limit=None)
    with patch(
        "api_server.routes.chat._resolve_workspace_skill",
        return_value=(ws, None),
    ), patch(
        "api_server.routes.chat.ws_db.fetch_actor_budget_usage",
        return_value=actor_b,
    ), patch(
        "api_server.routes.chat.ws_db.fetch_budget_usage",
        return_value=ws_b,
    ), TestClient(app) as client:
        r = client.post("/v1/chat/completions", json=body, headers=AUTH)
        assert r.status_code == 402, r.text
        # actor 应优先
        assert r.json()["detail"]["code"] == "actor_budget_exceeded"


def test_chat_passes_when_actor_no_budget_set():
    """actor 没设 budget → 跳过 actor 检查 → 走 workspace (这里 ws 也没设, 不拦)"""
    wid = uuid4()
    ws = _ws(wid=wid)
    body = {
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
        "workspace_id": str(wid),
    }
    actor_b = _budget(today=999, month=999, daily_limit=None, monthly_limit=None)
    with patch(
        "api_server.routes.chat._resolve_workspace_skill",
        return_value=(ws, None),
    ), patch(
        "api_server.routes.chat.ws_db.fetch_actor_budget_usage",
        return_value=actor_b,
    ), patch(
        "api_server.routes.chat.ws_db.fetch_budget_usage",
        return_value=_budget(0, 0, None, None),
    ), TestClient(app) as client:
        r = client.post("/v1/chat/completions", json=body, headers=AUTH)
        assert r.status_code != 402


def test_chat_passes_when_allowed_models_empty():
    """allowed_models = [] → 不限制 (默认行为)"""
    wid = uuid4()
    ws = _ws(wid=wid)
    body = {
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
        "workspace_id": str(wid),
        "model": "deepseek/deepseek-chat",
    }
    with patch(
        "api_server.routes.chat._resolve_workspace_skill",
        return_value=(ws, None),
    ), patch(
        "api_server.routes.chat.ws_db.fetch_budget_usage",
        return_value=_budget(today=0, month=0, daily_limit=None, monthly_limit=None),
    ), TestClient(app) as client:
        r = client.post("/v1/chat/completions", json=body, headers=AUTH)
        assert r.status_code != 403
