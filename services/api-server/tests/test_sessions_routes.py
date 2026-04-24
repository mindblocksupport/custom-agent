"""Sessions routes 测试 (mock chat_db, 不需要真 PG)."""

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from api_server.db.chat import MessageRow, SessionRow
from api_server.main import app

AUTH = {"Authorization": "Bearer dev-key-change-me"}
T = UUID("00000000-0000-0000-0000-000000000001")


def _row(sid: UUID = None, title: str = "test") -> SessionRow:
    return SessionRow(
        id=sid or uuid4(), tenant_id=T, actor_id="dev",
        title=title, message_count=0, total_cost_usd=0.0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_create_session():
    sid = uuid4()
    with patch("api_server.routes.sessions.chat_db.create_session", return_value=sid), \
         patch("api_server.routes.sessions.chat_db.get_session", return_value=_row(sid, "hello")), \
         TestClient(app) as client:
        r = client.post("/v1/sessions", json={"title": "hello"}, headers=AUTH)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["title"] == "hello"
        assert body["id"] == str(sid)


def test_list_sessions_empty():
    with patch("api_server.routes.sessions.chat_db.list_sessions",
               return_value=([], None)), \
         TestClient(app) as client:
        r = client.get("/v1/sessions", headers=AUTH)
        assert r.status_code == 200
        body = r.json()
        assert body["items"] == []
        assert body["next_cursor"] is None


def test_list_sessions_with_data():
    rows = [_row(title=f"s{i}") for i in range(3)]
    with patch("api_server.routes.sessions.chat_db.list_sessions",
               return_value=(rows, None)), \
         TestClient(app) as client:
        r = client.get("/v1/sessions?limit=10", headers=AUTH)
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 3
        titles = {item["title"] for item in body["items"]}
        assert titles == {"s0", "s1", "s2"}


def test_get_session_with_messages():
    sid = uuid4()
    msg = MessageRow(
        id=uuid4(), session_id=sid, sequence_no=1,
        role="user", content="hi", tool_calls=None, tool_call_id=None,
        tool_name=None, trace_id="t1", cost_usd=0.0, input_tokens=0,
        output_tokens=0, model=None, metadata={},
        created_at=datetime.now(timezone.utc),
    )
    with patch("api_server.routes.sessions.chat_db.get_session", return_value=_row(sid)), \
         patch("api_server.routes.sessions.chat_db.get_messages", return_value=[msg]), \
         TestClient(app) as client:
        r = client.get(f"/v1/sessions/{sid}", headers=AUTH)
        assert r.status_code == 200
        body = r.json()
        assert body["session"]["id"] == str(sid)
        assert len(body["messages"]) == 1
        assert body["messages"][0]["content"] == "hi"


def test_get_session_404():
    with patch("api_server.routes.sessions.chat_db.get_session", return_value=None), \
         TestClient(app) as client:
        r = client.get(f"/v1/sessions/{uuid4()}", headers=AUTH)
        assert r.status_code == 404


def test_delete_session():
    with patch("api_server.routes.sessions.chat_db.delete_session", return_value=True), \
         TestClient(app) as client:
        r = client.delete(f"/v1/sessions/{uuid4()}", headers=AUTH)
        assert r.status_code == 200
        assert r.json() == {"deleted": True}


def test_patch_session_title():
    sid = uuid4()
    with patch("api_server.routes.sessions.chat_db.update_session_title",
               return_value=True), \
         patch("api_server.routes.sessions.chat_db.get_session",
               return_value=_row(sid, "new title")), \
         TestClient(app) as client:
        r = client.patch(f"/v1/sessions/{sid}",
                         json={"title": "new title"}, headers=AUTH)
        assert r.status_code == 200
        assert r.json()["title"] == "new title"


def test_sessions_require_auth():
    with TestClient(app) as client:
        for m, path in [("POST", "/v1/sessions"), ("GET", "/v1/sessions"),
                          ("DELETE", f"/v1/sessions/{uuid4()}")]:
            r = client.request(m, path, json={"title": "x"} if m == "POST" else None)
            assert r.status_code in (401, 403)
