"""audit_logs CRUD + insert helper 测试 (mock DB)."""

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient

from api_server.db.audit import AuditRow
from api_server.main import app

AUTH = {"Authorization": "Bearer dev-key-change-me"}
TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _row(
    id_: int = 1,
    actor: str = "dev",
    action: str = "key.create",
    resource_type: str = "api_key",
    resource_id: str = "abc",
    detail: dict | None = None,
) -> AuditRow:
    return AuditRow(
        id=id_, tenant_id=TENANT, actor_id=actor,
        action=action,
        resource_type=resource_type, resource_id=resource_id,
        detail=detail or {}, ip="127.0.0.1", user_agent="test/1.0",
        created_at=datetime.now(timezone.utc),
    )


def test_list_audit_returns_items():
    rows = [_row(id_=2), _row(id_=1, action="workspace.delete")]
    with patch(
        "api_server.routes.audit.audit_db.list_recent",
        return_value=(rows, None),
    ), TestClient(app) as client:
        r = client.get("/v1/audit", headers=AUTH)
        assert r.status_code == 200
        body = r.json()
        assert body["next_cursor"] is None
        assert len(body["items"]) == 2
        assert body["items"][0]["action"] == "key.create"
        assert body["items"][1]["action"] == "workspace.delete"


def test_list_audit_passes_filters():
    seen: dict = {}
    def _capture(**kw):
        seen.update(kw)
        return ([], None)
    with patch(
        "api_server.routes.audit.audit_db.list_recent",
        side_effect=_capture,
    ), TestClient(app) as client:
        r = client.get(
            "/v1/audit?actor_id=ci-bot&action_prefix=key.&resource_type=api_key&limit=20",
            headers=AUTH,
        )
        assert r.status_code == 200
    assert seen["actor_id"] == "ci-bot"
    assert seen["action_prefix"] == "key."
    assert seen["resource_type"] == "api_key"
    assert seen["limit"] == 20


def test_list_audit_with_cursor_pagination():
    rows = [_row(id_=10), _row(id_=9), _row(id_=8)]
    with patch(
        "api_server.routes.audit.audit_db.list_recent",
        return_value=(rows, 5),  # 还有更早的 id<5
    ), TestClient(app) as client:
        r = client.get("/v1/audit?limit=3", headers=AUTH)
        assert r.status_code == 200
        body = r.json()
        assert body["next_cursor"] == 5
        assert len(body["items"]) == 3


def test_list_audit_passes_since_until():
    seen: dict = {}
    def _capture(**kw):
        seen.update(kw)
        return ([], None)
    with patch(
        "api_server.routes.audit.audit_db.list_recent", side_effect=_capture,
    ), TestClient(app) as client:
        r = client.get(
            "/v1/audit?since=2026-01-01T00:00:00&until=2026-04-01T00:00:00",
            headers=AUTH,
        )
        assert r.status_code == 200
    assert seen["since"] is not None
    assert seen["until"] is not None
    assert seen["since"].isoformat().startswith("2026-01-01")
    assert seen["until"].isoformat().startswith("2026-04-01")


def test_export_audit_csv_returns_text_with_bom():
    rows = [
        _row(id_=2, action="key.create", detail={"label": "ci"}),
        _row(id_=1, action="workspace.delete"),
    ]
    with patch(
        "api_server.routes.audit.audit_db.list_recent",
        return_value=(rows, None),
    ), TestClient(app) as client:
        r = client.get("/v1/audit/csv", headers=AUTH)
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        assert "attachment" in r.headers["content-disposition"]
        body = r.text
        assert body.startswith("\ufeff"), "CSV 应含 UTF-8 BOM"
        assert "id,created_at,actor_id,action" in body
        assert "key.create" in body
        assert "workspace.delete" in body
        # CSV 把内嵌引号 doubled 了, 所以原 JSON {"label":"ci"} 变成 ""label"":""ci""
        assert '""label"":""ci""' in body


def test_audit_cleanup_deletes_and_self_audits():
    inserted: dict = {}
    def _ins(**kw):
        inserted.update(kw)
        return 1
    with patch(
        "api_server.routes.audit.audit_db.cleanup_older_than", return_value=42,
    ), patch(
        "api_server.routes.audit.audit_db.insert", side_effect=_ins,
    ), TestClient(app) as client:
        r = client.post(
            "/v1/audit/cleanup", json={"retain_days": 30}, headers=AUTH,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body == {"deleted": 42, "retain_days": 30}
    # meta-audit
    assert inserted["action"] == "audit.cleanup"
    assert inserted["detail"]["retain_days"] == 30
    assert inserted["detail"]["deleted"] == 42


def test_list_audit_passes_resource_id():
    seen: dict = {}
    def _capture(**kw):
        seen.update(kw)
        return ([], None)
    with patch(
        "api_server.routes.audit.audit_db.list_recent", side_effect=_capture,
    ), TestClient(app) as client:
        r = client.get(
            "/v1/audit?resource_type=api_key&resource_id=abc12345",
            headers=AUTH,
        )
        assert r.status_code == 200
    assert seen["resource_type"] == "api_key"
    assert seen["resource_id"] == "abc12345"


def test_audit_cleanup_validates_retain_days():
    with TestClient(app) as client:
        r = client.post(
            "/v1/audit/cleanup", json={"retain_days": 0}, headers=AUTH,
        )
        assert r.status_code == 422
        r2 = client.post(
            "/v1/audit/cleanup", json={"retain_days": 99999}, headers=AUTH,
        )
        assert r2.status_code == 422
