"""Session tags + API Key role 路由测试 (mock DB)."""

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from api_server.db.api_keys import ApiKeyRow
from api_server.db.chat import SessionRow
from api_server.main import app

AUTH = {"Authorization": "Bearer dev-key-change-me"}
TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _sess(sid: UUID | None = None, tags: list[str] | None = None) -> SessionRow:
    return SessionRow(
        id=sid or uuid4(),
        tenant_id=TENANT, actor_id="dev",
        title="测试会话",
        message_count=3, total_cost_usd=0.0001,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        workspace_id=None, skill_id=None,
        tags=tags or [],
    )


# ---------------- session tags ----------------

def test_list_sessions_passes_tag_filter():
    seen: dict = {}
    def _capture(**kw):
        seen.update(kw)
        return ([], None)
    with patch(
        "api_server.routes.sessions.chat_db.list_sessions",
        side_effect=_capture,
    ), TestClient(app) as client:
        r = client.get("/v1/sessions?tag=monthly_report", headers=AUTH)
        assert r.status_code == 200
    assert seen["tag"] == "monthly_report"


def test_list_session_tags_returns_distinct():
    with patch(
        "api_server.routes.sessions.chat_db.list_distinct_tags",
        return_value=["alpha", "beta"],
    ), TestClient(app) as client:
        r = client.get("/v1/sessions/tags", headers=AUTH)
        assert r.status_code == 200
        assert r.json() == {"tags": ["alpha", "beta"]}


def test_patch_session_tags_persists():
    sid = uuid4()
    seen_tags: dict = {}
    def _update_tags(**kw):
        seen_tags.update(kw)
        return True
    with patch(
        "api_server.routes.sessions.chat_db.update_session_tags",
        side_effect=_update_tags,
    ), patch(
        "api_server.routes.sessions.chat_db.get_session",
        return_value=_sess(sid=sid, tags=["x", "y"]),
    ), TestClient(app) as client:
        r = client.patch(
            f"/v1/sessions/{sid}",
            json={"tags": ["X", "y "]},
            headers=AUTH,
        )
        assert r.status_code == 200, r.text
        assert r.json()["tags"] == ["x", "y"]
    assert seen_tags["tags"] == ["X", "y "]  # 后端再做规范化


def test_patch_session_400_when_nothing_to_update():
    sid = uuid4()
    with TestClient(app) as client:
        r = client.patch(f"/v1/sessions/{sid}", json={}, headers=AUTH)
        assert r.status_code == 400


# ---------------- API key role ----------------

def _key(role: str = "admin", h: str = "a" * 64) -> ApiKeyRow:
    return ApiKeyRow(
        key_hash=h, tenant_id=TENANT, actor_id="dev",
        principals=["user:dev"], label="x",
        role=role,
        created_at=datetime.now(timezone.utc),
        last_used_at=None, revoked_at=None,
    )


def test_create_key_passes_role_to_db():
    seen: dict = {}
    def _create(**kw):
        seen.update(kw)
        return ("ck_secret", _key(role=kw.get("role", "admin")))
    with patch(
        "api_server.routes.keys.keys_db.create_key", side_effect=_create,
    ), TestClient(app) as client:
        r = client.post(
            "/v1/keys", json={"label": "ci", "role": "viewer"}, headers=AUTH,
        )
        assert r.status_code == 200, r.text
        assert r.json()["role"] == "viewer"
    assert seen["role"] == "viewer"


def test_create_key_default_role_admin():
    def _create(**kw):
        return ("ck_secret", _key(role=kw.get("role", "admin")))
    with patch(
        "api_server.routes.keys.keys_db.create_key", side_effect=_create,
    ), TestClient(app) as client:
        r = client.post("/v1/keys", json={"label": "ci"}, headers=AUTH)
        assert r.status_code == 200
        assert r.json()["role"] == "admin"


def test_create_key_validates_role_enum():
    with TestClient(app) as client:
        r = client.post(
            "/v1/keys", json={"label": "x", "role": "superadmin"}, headers=AUTH,
        )
        assert r.status_code == 422


def test_patch_key_role():
    h = "b" * 64
    with patch(
        "api_server.routes.keys.keys_db.update_role", return_value=True,
    ), patch(
        "api_server.routes.keys.keys_db.list_keys",
        return_value=[_key(role="editor", h=h)],
    ), TestClient(app) as client:
        r = client.patch(
            f"/v1/keys/{h}", json={"role": "editor"}, headers=AUTH,
        )
        assert r.status_code == 200, r.text
        assert r.json()["role"] == "editor"


def test_patch_key_400_when_nothing_to_update():
    h = "c" * 64
    with TestClient(app) as client:
        r = client.patch(f"/v1/keys/{h}", json={}, headers=AUTH)
        assert r.status_code == 400
