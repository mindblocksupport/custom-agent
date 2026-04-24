"""Skills endpoints (v1.5 沉淀层).

POST   /v1/workspaces/{wid}/skills              创建
GET    /v1/workspaces/{wid}/skills              列出 (默认每 name 最新版)
GET    /v1/skills/{id}                          详情
PATCH  /v1/skills/{id}                          部分更新 (不改 version)
DELETE /v1/skills/{id}                          软删
POST   /v1/skills/{id}/versions                 发新版 (复制 + bump)
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api_server.acl import Principal
from api_server.auth import verify_api_key
from api_server.db import skills as skill_db

router = APIRouter()


class SkillCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    system_prompt: str = Field(default="", max_length=8000)
    allowed_tools: list[str] = Field(default_factory=list)
    default_collections: list[str] = Field(default_factory=list)
    starter_examples: list[str] = Field(default_factory=list)
    visibility: str = Field(default="workspace", pattern="^(private|workspace|public)$")
    budget_per_call_usd: float | None = None
    tags: list[str] = Field(default_factory=list)


class SkillPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    allowed_tools: list[str] | None = None
    default_collections: list[str] | None = None
    starter_examples: list[str] | None = None
    visibility: str | None = Field(default=None, pattern="^(private|workspace|public)$")
    budget_per_call_usd: float | None = None
    tags: list[str] | None = None


class SkillVersionRequest(BaseModel):
    description: str | None = None
    system_prompt: str | None = None
    allowed_tools: list[str] | None = None
    default_collections: list[str] | None = None
    starter_examples: list[str] | None = None
    visibility: str | None = Field(default=None, pattern="^(private|workspace|public)$")
    budget_per_call_usd: float | None = None
    tags: list[str] | None = None


class SkillOut(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    description: str
    version: int
    system_prompt: str
    allowed_tools: list[str]
    default_collections: list[str]
    starter_examples: list[str]
    visibility: str
    budget_per_call_usd: float | None
    tags: list[str]
    created_at: datetime
    updated_at: datetime


def _to_out(r: skill_db.SkillRow) -> SkillOut:
    return SkillOut(
        id=r.id, workspace_id=r.workspace_id, name=r.name,
        description=r.description, version=r.version,
        system_prompt=r.system_prompt, allowed_tools=r.allowed_tools,
        default_collections=r.default_collections,
        starter_examples=r.starter_examples, visibility=r.visibility,
        budget_per_call_usd=r.budget_per_call_usd, tags=r.tags,
        created_at=r.created_at, updated_at=r.updated_at,
    )


@router.post("/workspaces/{wid}/skills", response_model=SkillOut)
async def create_skill(
    wid: UUID,
    payload: SkillCreate,
    principal: Principal = Depends(verify_api_key),
) -> SkillOut:
    sid = await asyncio.to_thread(
        skill_db.create,
        workspace_id=wid, tenant_id=principal.tenant_id,
        actor_id=principal.actor_id,
        name=payload.name, description=payload.description,
        system_prompt=payload.system_prompt,
        allowed_tools=payload.allowed_tools,
        default_collections=payload.default_collections,
        starter_examples=payload.starter_examples,
        visibility=payload.visibility,
        budget_per_call_usd=payload.budget_per_call_usd,
        tags=payload.tags,
    )
    if sid is None:
        raise HTTPException(404, "workspace not found")
    row = await asyncio.to_thread(
        skill_db.get, skill_id=sid, tenant_id=principal.tenant_id,
    )
    if row is None:
        raise HTTPException(500, "created but not retrievable")
    return _to_out(row)


@router.get("/workspaces/{wid}/skills", response_model=list[SkillOut])
async def list_skills(
    wid: UUID,
    include_public: bool = False,
    principal: Principal = Depends(verify_api_key),
) -> list[SkillOut]:
    """列出本 workspace 的 skill.

    include_public=true: 同时附带本 tenant 其他 workspace 的 visibility=public skill.
    """
    rows = await asyncio.to_thread(
        skill_db.list_for_workspace,
        workspace_id=wid, tenant_id=principal.tenant_id,
    )
    out = [_to_out(r) for r in rows]
    if include_public:
        public_rows = await asyncio.to_thread(
            skill_db.list_public_in_tenant,
            tenant_id=principal.tenant_id, exclude_workspace_id=wid,
        )
        out.extend(_to_out(r) for r in public_rows)
    return out


@router.get("/skills/public", response_model=list[SkillOut])
async def list_public_skills(
    principal: Principal = Depends(verify_api_key),
) -> list[SkillOut]:
    """v1.5 Skill 市场: 列出本 tenant 下所有 public skill (跨 workspace)."""
    rows = await asyncio.to_thread(
        skill_db.list_public_in_tenant,
        tenant_id=principal.tenant_id,
    )
    return [_to_out(r) for r in rows]


@router.get("/skills/{sid}", response_model=SkillOut)
async def get_skill(
    sid: UUID,
    principal: Principal = Depends(verify_api_key),
) -> SkillOut:
    row = await asyncio.to_thread(
        skill_db.get, skill_id=sid, tenant_id=principal.tenant_id,
    )
    if row is None:
        raise HTTPException(404, "skill not found")
    return _to_out(row)


@router.patch("/skills/{sid}", response_model=SkillOut)
async def patch_skill(
    sid: UUID,
    payload: SkillPatch,
    principal: Principal = Depends(verify_api_key),
) -> SkillOut:
    fields = payload.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(400, "no fields to update")
    ok = await asyncio.to_thread(
        skill_db.update,
        skill_id=sid, tenant_id=principal.tenant_id, **fields,
    )
    if not ok:
        raise HTTPException(404, "skill not found")
    row = await asyncio.to_thread(
        skill_db.get, skill_id=sid, tenant_id=principal.tenant_id,
    )
    return _to_out(row)  # type: ignore[arg-type]


@router.delete("/skills/{sid}")
async def delete_skill(
    sid: UUID,
    principal: Principal = Depends(verify_api_key),
) -> dict[str, bool]:
    ok = await asyncio.to_thread(
        skill_db.delete, skill_id=sid, tenant_id=principal.tenant_id,
    )
    if not ok:
        raise HTTPException(404, "skill not found")
    return {"deleted": True}


class InstallRequest(BaseModel):
    workspace_id: UUID


@router.post("/skills/{sid}/install", response_model=SkillOut)
async def install_skill(
    sid: UUID,
    payload: InstallRequest,
    principal: Principal = Depends(verify_api_key),
) -> SkillOut:
    """v1.5 Skill 市场: 把 visibility=public 的 skill 安装到 target workspace (复制).

    - 安装后是独立 skill (修改不影响原 skill)
    - 同名重复 → 返回已存在的 (idempotent)
    - 仅 public skill 可安装; 否则 404
    """
    new_id = await asyncio.to_thread(
        skill_db.install_to_workspace,
        source_skill_id=sid,
        target_workspace_id=payload.workspace_id,
        tenant_id=principal.tenant_id,
        actor_id=principal.actor_id,
    )
    if new_id is None:
        raise HTTPException(
            404,
            "source skill not found / not public, or target workspace not found",
        )
    row = await asyncio.to_thread(
        skill_db.get, skill_id=new_id, tenant_id=principal.tenant_id,
    )
    return _to_out(row)  # type: ignore[arg-type]


@router.post("/skills/{sid}/versions", response_model=SkillOut)
async def new_version(
    sid: UUID,
    payload: SkillVersionRequest,
    principal: Principal = Depends(verify_api_key),
) -> SkillOut:
    overrides: dict[str, Any] = payload.model_dump(exclude_none=True)
    new_id = await asyncio.to_thread(
        skill_db.new_version,
        skill_id=sid, tenant_id=principal.tenant_id, **overrides,
    )
    if new_id is None:
        raise HTTPException(404, "skill not found")
    row = await asyncio.to_thread(
        skill_db.get, skill_id=new_id, tenant_id=principal.tenant_id,
    )
    return _to_out(row)  # type: ignore[arg-type]
