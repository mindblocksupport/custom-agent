"""/v1/workspaces/{wid}/me/budget endpoint 测试 (mock DB)."""

from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from api_server.db.workspaces import BudgetUsage
from api_server.main import app

AUTH = {"Authorization": "Bearer dev-key-change-me"}
TENANT = UUID("00000000-0000-0000-0000-000000000001")


def test_my_budget_returns_usage_and_limits():
    wid = uuid4()
    b = BudgetUsage(
        today_cost_usd=0.85, month_cost_usd=12.0,
        budget_daily_usd=5.0, budget_monthly_usd=100.0,
    )
    with patch(
        "api_server.routes.me.ws_db.fetch_actor_budget_usage",
        return_value=b,
    ), TestClient(app) as client:
        r = client.get(f"/v1/workspaces/{wid}/me/budget", headers=AUTH)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["today_cost_usd"] == 0.85
        assert body["budget_daily_usd"] == 5.0
        assert body["has_limit"] is True


def test_my_budget_has_limit_false_when_no_budget():
    wid = uuid4()
    b = BudgetUsage(
        today_cost_usd=0.85, month_cost_usd=12.0,
        budget_daily_usd=None, budget_monthly_usd=None,
    )
    with patch(
        "api_server.routes.me.ws_db.fetch_actor_budget_usage",
        return_value=b,
    ), TestClient(app) as client:
        r = client.get(f"/v1/workspaces/{wid}/me/budget", headers=AUTH)
        assert r.status_code == 200
        assert r.json()["has_limit"] is False


def test_my_budget_404_when_not_member():
    wid = uuid4()
    with patch(
        "api_server.routes.me.ws_db.fetch_actor_budget_usage",
        return_value=None,
    ), TestClient(app) as client:
        r = client.get(f"/v1/workspaces/{wid}/me/budget", headers=AUTH)
        assert r.status_code == 404
