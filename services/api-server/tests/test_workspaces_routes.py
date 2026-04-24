"""Workspaces routes 测试 (mock DB layer, 不需要真 PG)."""

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from api_server.db.workspaces import MemberRow, WorkspaceRow
from api_server.main import app

AUTH = {"Authorization": "Bearer dev-key-change-me"}
T = UUID("00000000-0000-0000-0000-000000000001")


def _ws(wid: UUID = None, name: str = "风控分析") -> WorkspaceRow:
    return WorkspaceRow(
        id=wid or uuid4(), tenant_id=T, name=name, description="",
        default_model="auto",
        allowed_models=[], allowed_tools=["search_kb", "calculator"],
        default_collection="default",
        allowed_collections=["default", "legal"],
        budget_daily_usd=10.0, budget_monthly_usd=200.0,
        features={"rag": True}, created_by="dev",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_create_workspace():
    wid = uuid4()
    with patch("api_server.routes.workspaces.ws_db.create", return_value=wid), \
         patch("api_server.routes.workspaces.ws_db.get", return_value=_ws(wid, "风控")), \
         TestClient(app) as client:
        r = client.post("/v1/workspaces", json={"name": "风控"}, headers=AUTH)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["name"] == "风控"
        assert body["id"] == str(wid)


def test_list_workspaces_mine_only():
    rows = [_ws(name=f"ws{i}") for i in range(3)]
    with patch("api_server.routes.workspaces.ws_db.list_for_actor",
               return_value=rows), \
         TestClient(app) as client:
        r = client.get("/v1/workspaces", headers=AUTH)
        assert r.status_code == 200
        assert len(r.json()) == 3


def test_list_workspaces_all():
    rows = [_ws()]
    with patch("api_server.routes.workspaces.ws_db.list_for_tenant",
               return_value=rows), \
         TestClient(app) as client:
        r = client.get("/v1/workspaces?mine_only=false", headers=AUTH)
        assert r.status_code == 200
        assert len(r.json()) == 1


def test_get_workspace():
    wid = uuid4()
    with patch("api_server.routes.workspaces.ws_db.get", return_value=_ws(wid)), \
         TestClient(app) as client:
        r = client.get(f"/v1/workspaces/{wid}", headers=AUTH)
        assert r.status_code == 200
        assert r.json()["id"] == str(wid)


def test_get_workspace_404():
    with patch("api_server.routes.workspaces.ws_db.get", return_value=None), \
         TestClient(app) as client:
        r = client.get(f"/v1/workspaces/{uuid4()}", headers=AUTH)
        assert r.status_code == 404


def test_patch_workspace():
    wid = uuid4()
    with patch("api_server.routes.workspaces.ws_db.update", return_value=True), \
         patch("api_server.routes.workspaces.ws_db.get",
               return_value=_ws(wid, "新名字")), \
         TestClient(app) as client:
        r = client.patch(f"/v1/workspaces/{wid}",
                         json={"name": "新名字"}, headers=AUTH)
        assert r.status_code == 200
        assert r.json()["name"] == "新名字"


def test_patch_workspace_no_fields():
    with TestClient(app) as client:
        r = client.patch(f"/v1/workspaces/{uuid4()}",
                         json={}, headers=AUTH)
        assert r.status_code == 400


def test_delete_workspace():
    with patch("api_server.routes.workspaces.ws_db.delete", return_value=True), \
         TestClient(app) as client:
        r = client.delete(f"/v1/workspaces/{uuid4()}", headers=AUTH)
        assert r.status_code == 200


def test_add_member():
    with patch("api_server.routes.workspaces.ws_db.add_member", return_value=True), \
         TestClient(app) as client:
        r = client.post(
            f"/v1/workspaces/{uuid4()}/members",
            json={"actor_id": "alice", "role": "editor"},
            headers=AUTH,
        )
        assert r.status_code == 200
        assert r.json()["role"] == "editor"


def test_add_member_invalid_role():
    with TestClient(app) as client:
        r = client.post(
            f"/v1/workspaces/{uuid4()}/members",
            json={"actor_id": "alice", "role": "god"},
            headers=AUTH,
        )
        assert r.status_code == 422


def test_list_members():
    rows = [
        MemberRow(workspace_id=uuid4(), actor_id="alice", role="owner",
                  created_at=datetime.now(timezone.utc)),
        MemberRow(workspace_id=uuid4(), actor_id="bob", role="viewer",
                  created_at=datetime.now(timezone.utc)),
    ]
    with patch("api_server.routes.workspaces.ws_db.list_members",
               return_value=rows), \
         TestClient(app) as client:
        r = client.get(f"/v1/workspaces/{uuid4()}/members", headers=AUTH)
        assert r.status_code == 200
        assert {m["actor_id"] for m in r.json()} == {"alice", "bob"}


def test_remove_member():
    with patch("api_server.routes.workspaces.ws_db.remove_member", return_value=True), \
         TestClient(app) as client:
        r = client.delete(f"/v1/workspaces/{uuid4()}/members/alice", headers=AUTH)
        assert r.status_code == 200


def test_workspaces_require_auth():
    with TestClient(app) as client:
        r = client.get("/v1/workspaces")
        assert r.status_code in (401, 403)
