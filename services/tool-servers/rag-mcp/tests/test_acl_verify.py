"""rag-mcp ACL 验签测试 (Day 2 P0 #3)."""

import time

import jwt
import pytest

from rag_mcp.acl import (
    AUDIENCE,
    ISSUER,
    DEV_PRINCIPALS,
    DEV_TENANT_ID,
    resolve_acl,
)

SECRET = "test-secret-32-bytes-or-more----xxx"
PREV_SECRET = "test-prev-secret-32-bytes-or-more"


def _sign(payload: dict, secret: str = SECRET) -> str:
    return jwt.encode(payload, secret, algorithm="HS256")


def _good_payload(**overrides):
    now = int(time.time())
    base = {
        "iss": ISSUER, "aud": AUDIENCE,
        "tenant_id": "00000000-0000-0000-0000-000000000042",
        "actor_id": "u_alice",
        "principals": ["user:u_alice", "group:eng"],
        "iat": now, "exp": now + 60,
    }
    base.update(overrides)
    return base


def test_valid_token_resolves_tenant_and_principals(monkeypatch):
    monkeypatch.setenv("RAG_MCP_JWT_SECRET", SECRET)
    token = _sign(_good_payload())
    tenant, principals, default_collections = resolve_acl(token)
    assert str(tenant) == "00000000-0000-0000-0000-000000000042"
    assert principals == ["user:u_alice", "group:eng"]
    assert default_collections == []  # 默认不传


def test_token_with_default_collections(monkeypatch):
    """v1.5: JWT 含 default_collections 应能取出."""
    monkeypatch.setenv("RAG_MCP_JWT_SECRET", SECRET)
    payload = _good_payload(default_collections=["legal", "finance"])
    token = _sign(payload)
    _, _, default_collections = resolve_acl(token)
    assert default_collections == ["legal", "finance"]


def test_missing_token_raises(monkeypatch):
    monkeypatch.setenv("RAG_MCP_JWT_SECRET", SECRET)
    monkeypatch.delenv("RAG_MCP_DEV_FALLBACK", raising=False)
    monkeypatch.setenv("ENV", "prod")  # 强制不退化
    with pytest.raises(PermissionError, match="missing"):
        resolve_acl(None)


def test_dev_fallback_when_enabled(monkeypatch):
    monkeypatch.setenv("RAG_MCP_JWT_SECRET", SECRET)
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("RAG_MCP_DEV_FALLBACK", "1")
    tenant, principals, default_collections = resolve_acl(None)
    assert tenant == DEV_TENANT_ID
    assert principals == DEV_PRINCIPALS
    assert default_collections == []


def test_dev_fallback_disabled_in_prod(monkeypatch):
    monkeypatch.setenv("RAG_MCP_JWT_SECRET", SECRET)
    monkeypatch.setenv("ENV", "prod")
    monkeypatch.setenv("RAG_MCP_DEV_FALLBACK", "1")  # 即使设了
    with pytest.raises(PermissionError):
        resolve_acl(None)


def test_expired_token_rejected(monkeypatch):
    monkeypatch.setenv("RAG_MCP_JWT_SECRET", SECRET)
    expired = _good_payload(iat=int(time.time()) - 100, exp=int(time.time()) - 30)
    token = _sign(expired)
    with pytest.raises(PermissionError, match="invalid"):
        resolve_acl(token)


def test_wrong_signature_rejected(monkeypatch):
    monkeypatch.setenv("RAG_MCP_JWT_SECRET", SECRET)
    token = _sign(_good_payload(), secret="other-secret-do-not-share")
    with pytest.raises(PermissionError):
        resolve_acl(token)


def test_wrong_audience_rejected(monkeypatch):
    monkeypatch.setenv("RAG_MCP_JWT_SECRET", SECRET)
    token = _sign(_good_payload(aud="other-audience"))
    with pytest.raises(PermissionError):
        resolve_acl(token)


def test_prev_secret_accepted_during_rotation(monkeypatch):
    monkeypatch.setenv("RAG_MCP_JWT_SECRET", SECRET)
    monkeypatch.setenv("RAG_MCP_JWT_SECRET_PREV", PREV_SECRET)
    # token 用 PREV 签 (旧密钥), 应仍能通过
    token = _sign(_good_payload(), secret=PREV_SECRET)
    _, principals, _ = resolve_acl(token)
    assert principals == ["user:u_alice", "group:eng"]


def test_no_secret_configured_raises(monkeypatch):
    monkeypatch.delenv("RAG_MCP_JWT_SECRET", raising=False)
    monkeypatch.delenv("RAG_MCP_JWT_SECRET_PREV", raising=False)
    monkeypatch.setenv("ENV", "prod")
    token = _sign(_good_payload())
    with pytest.raises(PermissionError, match="not configured"):
        resolve_acl(token)
