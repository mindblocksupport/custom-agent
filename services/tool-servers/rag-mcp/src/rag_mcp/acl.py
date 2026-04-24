"""rag-mcp ACL 验签 (Day 2 P0 #3).

验证 api-server 签的 short-lived JWT (HS256, 60s TTL).
失败行为:
- token 缺失/过期/签错 → PermissionError
- ENV=dev + RAG_MCP_DEV_FALLBACK=1 → 退化到 dev tenant
- 双密钥 (PRIMARY + PREV) 支持轮换
"""

from __future__ import annotations

import logging
import os
from uuid import UUID

import jwt

logger = logging.getLogger(__name__)

ISSUER = "api-server"
AUDIENCE = "rag-mcp"
LEEWAY_SECONDS = 5

DEV_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
DEV_PRINCIPALS = ["user:dev", "group:public"]


def _verify_secrets() -> list[str]:
    primary = os.environ.get("RAG_MCP_JWT_SECRET")
    prev = os.environ.get("RAG_MCP_JWT_SECRET_PREV")
    return [s for s in [primary, prev] if s]


def _dev_fallback_enabled() -> bool:
    """仅 ENV=dev 且显式 RAG_MCP_DEV_FALLBACK=1 时退化到 dev tenant."""
    if os.environ.get("ENV", "dev") != "dev":
        return False
    return os.environ.get("RAG_MCP_DEV_FALLBACK") == "1"


def resolve_acl(
    token: str | None,
) -> tuple[UUID, list[str], list[str]]:
    """token → (tenant_id, principals, default_collections). 失败抛 PermissionError.

    Args:
        token: JWT string (api-server 用 RAG_MCP_JWT_SECRET 签的).
    Returns:
        (tenant_id, principals, default_collections)
        default_collections v1.5: 来自 workspace/skill 配置, search_kb 无显式
        filter 时用作默认; 空列表 = 不限制.
    """
    if not token:
        if _dev_fallback_enabled():
            logger.warning("ACL token missing — using dev fallback")
            return DEV_TENANT_ID, list(DEV_PRINCIPALS), []
        raise PermissionError("missing principal_token")

    secrets_list = _verify_secrets()
    if not secrets_list:
        raise PermissionError("RAG_MCP_JWT_SECRET not configured")

    last_err: Exception | None = None
    for secret in secrets_list:
        try:
            payload = jwt.decode(
                token, secret, algorithms=["HS256"],
                audience=AUDIENCE, issuer=ISSUER,
                leeway=LEEWAY_SECONDS,
            )
            return (
                UUID(payload["tenant_id"]),
                list(payload.get("principals") or []),
                list(payload.get("default_collections") or []),
            )
        except jwt.PyJWTError as e:
            last_err = e
            continue
    raise PermissionError(f"invalid principal_token: {last_err}")
