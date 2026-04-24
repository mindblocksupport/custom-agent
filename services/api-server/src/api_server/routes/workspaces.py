"""Workspaces endpoints (v1.5 沉淀层).

POST   /v1/workspaces                          创建
GET    /v1/workspaces                          列出本 actor 可见的
GET    /v1/workspaces/{id}                     详情
PATCH  /v1/workspaces/{id}                     部分更新
DELETE /v1/workspaces/{id}                     软删
GET    /v1/workspaces/{id}/members             列成员
POST   /v1/workspaces/{id}/members             加成员
DELETE /v1/workspaces/{id}/members/{actor_id}  踢成员
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api_server.acl import Principal
from api_server.auth import verify_api_key
from api_server.db import workspaces as ws_db

router = APIRouter()


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    default_model: str = "auto"
    allowed_tools: list[str] = Field(default_factory=list)
    default_collection: str = "default"
    allowed_collections: list[str] = Field(default_factory=lambda: ["default"])
    budget_daily_usd: float | None = None
    budget_monthly_usd: float | None = None
    features: dict[str, Any] = Field(default_factory=dict)


class WorkspacePatch(BaseModel):
    name: str | None = None
    description: str | None = None
    default_model: str | None = None
    allowed_tools: list[str] | None = None
    default_collection: str | None = None
    allowed_collections: list[str] | None = None
    budget_daily_usd: float | None = None
    budget_monthly_usd: float | None = None
    features: dict[str, Any] | None = None


class WorkspaceOut(BaseModel):
    id: UUID
    name: str
    description: str
    default_model: str
    allowed_tools: list[str]
    default_collection: str
    allowed_collections: list[str]
    budget_daily_usd: float | None
    budget_monthly_usd: float | None
    features: dict
    created_at: datetime
    updated_at: datetime


class MemberAdd(BaseModel):
    actor_id: str = Field(..., min_length=1)
    role: str = Field(default="viewer", pattern="^(owner|editor|viewer)$")


class MemberOut(BaseModel):
    actor_id: str
    role: str
    created_at: datetime


def _to_out(r: ws_db.WorkspaceRow) -> WorkspaceOut:
    return WorkspaceOut(
        id=r.id, name=r.name, description=r.description,
        default_model=r.default_model, allowed_tools=r.allowed_tools,
        default_collection=r.default_collection,
        allowed_collections=r.allowed_collections,
        budget_daily_usd=r.budget_daily_usd,
        budget_monthly_usd=r.budget_monthly_usd,
        features=r.features,
        created_at=r.created_at, updated_at=r.updated_at,
    )


@router.post("/workspaces", response_model=WorkspaceOut)
async def create_workspace(
    payload: WorkspaceCreate,
    principal: Principal = Depends(verify_api_key),
) -> WorkspaceOut:
    try:
        wid = await asyncio.to_thread(
            ws_db.create,
            tenant_id=principal.tenant_id,
            name=payload.name, actor_id=principal.actor_id,
            description=payload.description,
            default_model=payload.default_model,
            allowed_tools=payload.allowed_tools,
            default_collection=payload.default_collection,
            allowed_collections=payload.allowed_collections,
            budget_daily_usd=payload.budget_daily_usd,
            budget_monthly_usd=payload.budget_monthly_usd,
            features=payload.features,
        )
    except Exception as e:
        raise HTTPException(409, f"create failed: {e}") from e
    row = await asyncio.to_thread(
        ws_db.get, workspace_id=wid, tenant_id=principal.tenant_id,
    )
    if row is None:
        raise HTTPException(500, "created but not retrievable")
    return _to_out(row)


@router.get("/workspaces", response_model=list[WorkspaceOut])
async def list_workspaces(
    mine_only: bool = Query(True, description="只列出本 actor 是 member 的"),
    principal: Principal = Depends(verify_api_key),
) -> list[WorkspaceOut]:
    fn = ws_db.list_for_actor if mine_only else ws_db.list_for_tenant
    kwargs: dict = {"tenant_id": principal.tenant_id}
    if mine_only:
        kwargs["actor_id"] = principal.actor_id
    rows = await asyncio.to_thread(fn, **kwargs)
    return [_to_out(r) for r in rows]


@router.get("/workspaces/{wid}", response_model=WorkspaceOut)
async def get_workspace(
    wid: UUID,
    principal: Principal = Depends(verify_api_key),
) -> WorkspaceOut:
    row = await asyncio.to_thread(
        ws_db.get, workspace_id=wid, tenant_id=principal.tenant_id,
    )
    if row is None:
        raise HTTPException(404, "workspace not found")
    return _to_out(row)


@router.patch("/workspaces/{wid}", response_model=WorkspaceOut)
async def patch_workspace(
    wid: UUID,
    payload: WorkspacePatch,
    principal: Principal = Depends(verify_api_key),
) -> WorkspaceOut:
    fields = payload.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(400, "no fields to update")
    ok = await asyncio.to_thread(
        ws_db.update,
        workspace_id=wid, tenant_id=principal.tenant_id, **fields,
    )
    if not ok:
        raise HTTPException(404, "workspace not found")
    row = await asyncio.to_thread(
        ws_db.get, workspace_id=wid, tenant_id=principal.tenant_id,
    )
    return _to_out(row)  # type: ignore[arg-type]


@router.delete("/workspaces/{wid}")
async def delete_workspace(
    wid: UUID,
    principal: Principal = Depends(verify_api_key),
) -> dict[str, bool]:
    ok = await asyncio.to_thread(
        ws_db.delete, workspace_id=wid, tenant_id=principal.tenant_id,
    )
    if not ok:
        raise HTTPException(404, "workspace not found")
    return {"deleted": True}


# ---------- members ----------

@router.get("/workspaces/{wid}/members", response_model=list[MemberOut])
async def list_members(
    wid: UUID,
    principal: Principal = Depends(verify_api_key),
) -> list[MemberOut]:
    rows = await asyncio.to_thread(
        ws_db.list_members,
        workspace_id=wid, tenant_id=principal.tenant_id,
    )
    return [
        MemberOut(actor_id=r.actor_id, role=r.role, created_at=r.created_at)
        for r in rows
    ]


@router.post("/workspaces/{wid}/members", response_model=MemberOut)
async def add_member(
    wid: UUID,
    payload: MemberAdd,
    principal: Principal = Depends(verify_api_key),
) -> MemberOut:
    ok = await asyncio.to_thread(
        ws_db.add_member,
        workspace_id=wid, tenant_id=principal.tenant_id,
        actor_id=payload.actor_id, role=payload.role,
    )
    if not ok:
        raise HTTPException(404, "workspace not found")
    return MemberOut(actor_id=payload.actor_id, role=payload.role, created_at=datetime.now())


@router.delete("/workspaces/{wid}/members/{actor_id}")
async def remove_member(
    wid: UUID,
    actor_id: str,
    principal: Principal = Depends(verify_api_key),
) -> dict[str, bool]:
    ok = await asyncio.to_thread(
        ws_db.remove_member,
        workspace_id=wid, tenant_id=principal.tenant_id,
        actor_id=actor_id,
    )
    if not ok:
        raise HTTPException(404, "member not found")
    return {"removed": True}
