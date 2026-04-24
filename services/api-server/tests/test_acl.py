"""Day 1 ACL/JWT 测试 (P0 #3 基础部分)."""

import os
import time
from uuid import UUID

import jwt
import pytest

from api_server.acl import (
    AUDIENCE,
    DEFAULT_TTL_SECONDS,
    ISSUER,
    Principal,
    sign_principal_token,
)

T = UUID("00000000-0000-0000-0000-000000000001")
SECRET = "test-secret-do-not-use-in-prod"
PREV_SECRET = "test-secret-prev"


def _principal() -> Principal:
    return Principal(
        tenant_id=T, actor_id="u_alice",
        principals=["user:u_alice", "group:eng"],
    )


def test_sign_requires_primary_secret(monkeypatch):
    monkeypatch.delenv("RAG_MCP_JWT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="RAG_MCP_JWT_SECRET"):
        sign_principal_token(_principal())


def test_sign_emits_well_formed_jwt(monkeypatch):
    monkeypatch.setenv("RAG_MCP_JWT_SECRET", SECRET)
    token = sign_principal_token(_principal())
    payload = jwt.decode(
        token, SECRET, algorithms=["HS256"],
        audience=AUDIENCE, issuer=ISSUER,
    )
    assert payload["tenant_id"] == str(T)
    assert payload["actor_id"] == "u_alice"
    assert payload["principals"] == ["user:u_alice", "group:eng"]
    assert payload["aud"] == AUDIENCE
    assert payload["iss"] == ISSUER
    assert "jti" in payload
    assert payload["exp"] - payload["iat"] == DEFAULT_TTL_SECONDS


def test_sign_uses_primary_when_prev_set(monkeypatch):
    """有 PREV 时, sign 仍只用 PRIMARY (PREV 仅供验签)."""
    monkeypatch.setenv("RAG_MCP_JWT_SECRET", SECRET)
    monkeypatch.setenv("RAG_MCP_JWT_SECRET_PREV", PREV_SECRET)
    token = sign_principal_token(_principal())
    # 用 PRIMARY 验签 OK
    jwt.decode(token, SECRET, algorithms=["HS256"],
               audience=AUDIENCE, issuer=ISSUER)
    # 用 PREV 应失败
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, PREV_SECRET, algorithms=["HS256"],
                   audience=AUDIENCE, issuer=ISSUER)


def test_token_expires_quickly(monkeypatch):
    monkeypatch.setenv("RAG_MCP_JWT_SECRET", SECRET)
    token = sign_principal_token(_principal(), ttl_seconds=1)
    payload = jwt.decode(token, SECRET, algorithms=["HS256"],
                        audience=AUDIENCE, issuer=ISSUER)
    assert payload["exp"] - int(time.time()) <= 1


def test_jti_unique_per_call(monkeypatch):
    monkeypatch.setenv("RAG_MCP_JWT_SECRET", SECRET)
    t1 = sign_principal_token(_principal())
    t2 = sign_principal_token(_principal())
    p1 = jwt.decode(t1, SECRET, algorithms=["HS256"],
                    audience=AUDIENCE, issuer=ISSUER)
    p2 = jwt.decode(t2, SECRET, algorithms=["HS256"],
                    audience=AUDIENCE, issuer=ISSUER)
    assert p1["jti"] != p2["jti"]


def test_principal_immutable():
    p = _principal()
    with pytest.raises(Exception):
        # frozen=True dataclass
        p.tenant_id = UUID("00000000-0000-0000-0000-000000000002")  # type: ignore
