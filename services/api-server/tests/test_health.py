"""Health endpoint smoke test"""

from fastapi.testclient import TestClient

from api_server.main import app


def test_health():
    """Liveness: 不需要 lifespan,直接拿 endpoint。"""
    with TestClient(app) as client:
        r = client.get("/health/")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def test_chat_no_auth():
    """无 Authorization header 应该 401。"""
    with TestClient(app) as client:
        r = client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 401


def test_root_serves_chat_html():
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert "Custom Agent" in r.text
