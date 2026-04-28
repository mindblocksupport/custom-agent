"""api_keys CRUD routes 测试 (mock DB)."""

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient

from api_server.db.api_keys import ApiKeyRow
from api_server.main import app

AUTH = {"Authorization": "Bearer dev-key-change-me"}
TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _key(
    h: str = "a" * 64, label: str = "demo",
    revoked: bool = False,
) -> ApiKeyRow:
    return ApiKeyRow(
        key_hash=h, tenant_id=TENANT, actor_id="dev",
        principals=["user:dev", "group:public"],
        label=label,
        created_at=datetime.now(timezone.utc),
        last_used_at=None,
        revoked_at=datetime.now(timezone.utc) if revoked else None,
    )


def test_list_keys_returns_active_only_by_default():
    rows = [_key("a" * 64, "k1"), _key("b" * 64, "k2")]
    with patch("api_server.routes.keys.keys_db.list_keys", return_value=rows), \
         TestClient(app) as client:
        r = client.get("/v1/keys", headers=AUTH)
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body) == 2
        assert body[0]["label"] == "k1"
        assert body[1]["key_hash"] == "b" * 64
        assert body[0]["revoked_at"] is None


def test_create_key_returns_raw_once():
    new_row = _key("c" * 64, "fresh")
    with patch(
        "api_server.routes.keys.keys_db.create_key",
        return_value=("ck_secret_raw_value_123", new_row),
    ), TestClient(app) as client:
        r = client.post(
            "/v1/keys",
            json={"label": "fresh"},
            headers=AUTH,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["raw_key"] == "ck_secret_raw_value_123"
        assert body["key_hash"] == "c" * 64
        assert body["label"] == "fresh"


def test_create_key_label_required():
    with TestClient(app) as client:
        r = client.post("/v1/keys", json={}, headers=AUTH)
        assert r.status_code == 422


def test_revoke_key_ok():
    with patch(
        "api_server.routes.keys.keys_db.revoke_key", return_value=True,
    ), TestClient(app) as client:
        r = client.delete("/v1/keys/" + "d" * 64, headers=AUTH)
        assert r.status_code == 200, r.text
        assert r.json() == {"revoked": True}


def test_revoke_key_404_when_not_found():
    with patch(
        "api_server.routes.keys.keys_db.revoke_key", return_value=False,
    ), TestClient(app) as client:
        r = client.delete("/v1/keys/" + "e" * 64, headers=AUTH)
        assert r.status_code == 404


def test_revoke_key_validates_hash_length():
    with TestClient(app) as client:
        r = client.delete("/v1/keys/short_hash", headers=AUTH)
        assert r.status_code == 400
        assert "64-char sha256" in r.text


def test_patch_key_label():
    updated = _key("f" * 64, "renamed")
    with patch(
        "api_server.routes.keys.keys_db.update_label", return_value=True,
    ), patch(
        "api_server.routes.keys.keys_db.list_keys", return_value=[updated],
    ), TestClient(app) as client:
        r = client.patch(
            "/v1/keys/" + "f" * 64,
            json={"label": "renamed"},
            headers=AUTH,
        )
        assert r.status_code == 200, r.text
        assert r.json()["label"] == "renamed"
