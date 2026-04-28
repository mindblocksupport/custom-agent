"""API Keys management endpoints.

GET    /v1/keys                  列本 tenant 全部 keys (mask hash)
POST   /v1/keys                  创建新 key (返回 raw 一次)
DELETE /v1/keys/{key_hash}       撤销
PATCH  /v1/keys/{key_hash}       改 label

注意: 所有操作必须用 owner-grade key 调 (这里 v1 简化: 任何同 tenant key 都行,
v2 加 RBAC 后 enforce: 仅 actor 自己创的 key 或 admin role).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from fastapi import Request

from api_server.acl import Principal
from api_server.auth import verify_api_key
from api_server.db import api_keys as keys_db
from api_server.db import audit as audit_db


def _client_meta(req: Request | None) -> tuple[str | None, str | None]:
    if not req:
        return None, None
    ip = (
        req.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (req.client.host if req.client else None)
    )
    ua = req.headers.get("user-agent")
    return ip, ua

router = APIRouter()


class KeyCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)
    actor_id: str | None = Field(
        default=None,
        description="不填则用当前 actor; 填了等于代申 (仅 admin)",
    )
    principals: list[str] = Field(default_factory=list)
    role: str = Field(
        default="admin", pattern="^(admin|editor|viewer)$",
        description="v1 仅记录, v2 RBAC 强制",
    )


class KeyOut(BaseModel):
    key_hash: str
    label: str | None
    actor_id: str
    principals: list[str]
    role: str = "admin"
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
    is_current: bool = False  # True = 当前请求用的就是这把


class KeyCreateResponse(KeyOut):
    raw_key: str = Field(..., description="明文 key, 仅本次返回, 之后不可见")


class KeyPatch(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    role: str | None = Field(default=None, pattern="^(admin|editor|viewer)$")


def _to_out(r: keys_db.ApiKeyRow, current_hash: str | None = None) -> KeyOut:
    return KeyOut(
        key_hash=r.key_hash, label=r.label,
        actor_id=r.actor_id, principals=r.principals,
        role=getattr(r, "role", "admin"),
        created_at=r.created_at, last_used_at=r.last_used_at,
        revoked_at=r.revoked_at,
        is_current=(current_hash is not None and r.key_hash == current_hash),
    )


@router.get("/keys", response_model=list[KeyOut])
async def list_keys(
    include_revoked: bool = False,
    principal: Principal = Depends(verify_api_key),
) -> list[KeyOut]:
    rows = await asyncio.to_thread(
        keys_db.list_keys,
        tenant_id=principal.tenant_id, include_revoked=include_revoked,
    )
    # 算 current_hash: principal 没存原 raw key, 但 verify_api_key 用了 hash 查表;
    # 为了在 UI 标"当前", 我们让 principal 携带它的 key_hash. 但当前 Principal
    # dataclass 没这个字段; 简化处理: 不标 is_current, 由前端比对 settings.apiKey
    # 自己算 hash.
    return [_to_out(r) for r in rows]


@router.post("/keys", response_model=KeyCreateResponse)
async def create_key_route(
    payload: KeyCreate,
    request: Request,
    principal: Principal = Depends(verify_api_key),
) -> KeyCreateResponse:
    actor = payload.actor_id or principal.actor_id
    principals = payload.principals or list(principal.principals)
    raw, row = await asyncio.to_thread(
        keys_db.create_key,
        tenant_id=principal.tenant_id,
        actor_id=actor, principals=principals, label=payload.label,
        role=payload.role,
    )
    ip, ua = _client_meta(request)
    audit_db.insert(
        tenant_id=principal.tenant_id, actor_id=principal.actor_id,
        action="key.create",
        resource_type="api_key", resource_id=row.key_hash[:12],
        detail={
            "label": payload.label, "for_actor": actor,
            "role": payload.role,
            "principals_n": len(principals),
        },
        ip=ip, user_agent=ua,
    )
    out = _to_out(row)
    return KeyCreateResponse(**out.model_dump(), raw_key=raw)


@router.delete("/keys/{key_hash}")
async def revoke_key_route(
    key_hash: str,
    request: Request,
    principal: Principal = Depends(verify_api_key),
) -> dict[str, bool]:
    if len(key_hash) != 64:
        raise HTTPException(400, "key_hash must be 64-char sha256 hex")
    ok = await asyncio.to_thread(
        keys_db.revoke_key,
        key_hash=key_hash, tenant_id=principal.tenant_id,
    )
    if not ok:
        raise HTTPException(404, "key not found or already revoked")
    ip, ua = _client_meta(request)
    audit_db.insert(
        tenant_id=principal.tenant_id, actor_id=principal.actor_id,
        action="key.revoke",
        resource_type="api_key", resource_id=key_hash[:12],
        ip=ip, user_agent=ua,
    )
    return {"revoked": True}


@router.patch("/keys/{key_hash}", response_model=KeyOut)
async def patch_key_route(
    key_hash: str,
    payload: KeyPatch,
    request: Request,
    principal: Principal = Depends(verify_api_key),
) -> KeyOut:
    if not payload.label and not payload.role:
        raise HTTPException(400, "nothing to update")
    if payload.label is not None:
        ok = await asyncio.to_thread(
            keys_db.update_label,
            key_hash=key_hash, tenant_id=principal.tenant_id,
            label=payload.label,
        )
        if not ok:
            raise HTTPException(404, "key not found")
    if payload.role is not None:
        ok = await asyncio.to_thread(
            keys_db.update_role,
            key_hash=key_hash, tenant_id=principal.tenant_id,
            role=payload.role,
        )
        if not ok:
            raise HTTPException(404, "key not found")
    rows = await asyncio.to_thread(
        keys_db.list_keys,
        tenant_id=principal.tenant_id, include_revoked=True,
    )
    ip, ua = _client_meta(request)
    audit_db.insert(
        tenant_id=principal.tenant_id, actor_id=principal.actor_id,
        action="key.patch",
        resource_type="api_key", resource_id=key_hash[:12],
        detail={k: v for k, v in payload.model_dump(exclude_none=True).items()},
        ip=ip, user_agent=ua,
    )
    for r in rows:
        if r.key_hash == key_hash:
            return _to_out(r)
    raise HTTPException(404, "key not found")
