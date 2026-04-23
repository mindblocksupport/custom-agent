"""Feedback endpoint validation 测试.

不验 DB 写入 (要求真 PG); 只验 schema + 路由挂上 + 正向反馈不入库.
"""

from fastapi.testclient import TestClient

from api_server.main import app

AUTH = {"Authorization": "Bearer dev-key-change-me"}


def test_feedback_route_mounted():
    """endpoint 存在 (不验 DB, 只验路由 + auth)."""
    with TestClient(app) as client:
        r = client.post("/v1/feedback", json={
            "trace_id": "x", "rating": "thumb_up",
            "query": "hi", "answer": "ok",
        }, headers=AUTH)
        # thumb_up = 正向, 不入 DB, 应直接 200 + persisted_as_badcase=False
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["accepted"] is True
        assert body["persisted_as_badcase"] is False


def test_feedback_validates_rating_enum():
    with TestClient(app) as client:
        r = client.post("/v1/feedback", json={
            "trace_id": "x", "rating": "bogus",
            "query": "hi", "answer": "ok",
        }, headers=AUTH)
        assert r.status_code == 422


def test_feedback_requires_auth():
    with TestClient(app) as client:
        r = client.post("/v1/feedback", json={
            "trace_id": "x", "rating": "thumb_up",
            "query": "hi", "answer": "ok",
        })  # 无 auth header
        assert r.status_code in (401, 403)
