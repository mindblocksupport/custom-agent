"""鉴权 (Day 1 重构 P0 #3): API Key → Principal.

变化:
- 旧: verify_api_key 返回 raw key (str)
- 新: verify_api_key 返回 Principal (tenant_id + actor_id + principals)
- 兼容: 旧 caller 只把它当 auth gate, 不读返回值, 改动 0

兼容性策略:
- 优先查 api_keys 表 (新路径) → 命中返回 Principal
- 表为空/不存在 → 退化到 settings.api_key 静态比对 (老逻辑保留, 给 dev tenant)
- 都不匹配 → 401
"""

from __future__ import annotations

import logging

from fastapi import Header, HTTPException

from api_server.acl import Principal
from api_server.config import settings
from api_server.db.api_keys import (
    DEFAULT_ACTOR_ID,
    DEFAULT_PRINCIPALS,
    DEFAULT_TENANT_ID,
    lookup_principal,
)

logger = logging.getLogger(__name__)


def verify_api_key(authorization: str | None = Header(None)) -> Principal:
    """API Key → Principal. 401 当 key 缺/错/过期.

    Returns:
        Principal: 含 tenant_id / actor_id / principals[] (用于后续 ACL 注入)
    """
    if not authorization:
        raise HTTPException(401, "Missing Authorization header")
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authorization must be: Bearer <key>")
    token = authorization.removeprefix("Bearer ").strip()

    # 路径 1: 查 api_keys 表 (Day 1 新逻辑)
    try:
        principal = lookup_principal(token)
        if principal is not None:
            return principal
    except Exception as e:
        # DB 不可用 → 走 fallback (不能挂掉整个服务)
        logger.warning("api_keys lookup failed, falling back to static key: %s", e)

    # 路径 2: 兼容老 settings.api_key (单租户 dev 模式)
    if token == settings.api_key:
        return Principal(
            tenant_id=DEFAULT_TENANT_ID,
            actor_id=DEFAULT_ACTOR_ID,
            principals=list(DEFAULT_PRINCIPALS),
        )

    raise HTTPException(401, "Invalid API key")
