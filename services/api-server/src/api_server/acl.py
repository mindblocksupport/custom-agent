"""Per-call ACL: Principal + JWT 签名 (Day 1 / P0 #3).

设计 (per-call ACL JWT 调研报告):
- HS256, 共享密钥, 60s TTL
- 双密钥 (PRIMARY + PREV) 支持平滑轮换
- payload: tenant_id / actor_id / principals[] / iss / aud / exp / iat / jti
- 调用方 (api-server) 签名; rag-mcp / 其他 MCP server 验签
- Principal 由 auth.py 从 api_keys 表查出来后塞 request.state
"""

from __future__ import annotations

import os
import secrets
import time
from dataclasses import dataclass, field
from uuid import UUID

import jwt

ISSUER = "api-server"
AUDIENCE = "rag-mcp"
DEFAULT_TTL_SECONDS = 60


@dataclass(frozen=True)
class Principal:
    """请求的认证主体 (Identity + ACL principals).

    auth.py 从 api_keys 表查出 → 塞 request.state.principal → 路由用 Depends 取.
    """

    tenant_id: UUID
    actor_id: str
    principals: list[str] = field(default_factory=list)


def _signing_secrets() -> list[str]:
    """获取签名密钥列表 (PRIMARY + PREV); 至少要 PRIMARY, 否则 fail-fast."""
    primary = os.environ.get("RAG_MCP_JWT_SECRET")
    if not primary:
        raise RuntimeError(
            "RAG_MCP_JWT_SECRET env var missing. "
            "Generate one: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    prev = os.environ.get("RAG_MCP_JWT_SECRET_PREV")
    return [s for s in [primary, prev] if s]


def sign_principal_token(
    principal: Principal,
    *,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    default_collections: list[str] | None = None,
) -> str:
    """签发 ACL JWT. 用 PRIMARY 密钥签.

    Args:
        default_collections: v1.5, 当前 workspace/skill 的默认 KB collection 列表.
                             rag-mcp 验签后, search_kb 在无显式 filter 时用作默认.
    """
    secrets_list = _signing_secrets()
    now = int(time.time())
    payload = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": f"actor:{principal.actor_id}",
        "tenant_id": str(principal.tenant_id),
        "actor_id": principal.actor_id,
        "principals": list(principal.principals),
        "iat": now,
        "exp": now + ttl_seconds,
        "jti": secrets.token_urlsafe(12),
    }
    if default_collections:
        payload["default_collections"] = list(default_collections)
    return jwt.encode(payload, secrets_list[0], algorithm="HS256")
