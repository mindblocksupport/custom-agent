"""鉴权 (L8 - MVP: 单 API Key;后续 SSO/RBAC)"""

from fastapi import Header, HTTPException

from api_server.config import settings


def verify_api_key(authorization: str | None = Header(None)) -> str:
    """简易 API Key 鉴权。

    Raises:
        HTTPException 401: 缺失 / 格式错 / key 不匹配
    """
    if not authorization:
        raise HTTPException(401, "Missing Authorization header")
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authorization must be: Bearer <key>")
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.api_key:
        raise HTTPException(401, "Invalid API key")
    return token
