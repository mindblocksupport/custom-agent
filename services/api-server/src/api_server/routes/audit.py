"""Audit log read endpoints + CSV 导出 + retention 清理.

GET    /v1/audit             分页 list (含 since/until/actor/action/resource_type)
GET    /v1/audit.csv         同上, 但流式返回 CSV (含 BOM 让 Excel 正确显示中文)
POST   /v1/audit/cleanup     删 retain_days 天前的记录 (返回 deleted 数)
"""

from __future__ import annotations

import asyncio
import csv
import io
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api_server.acl import Principal
from api_server.auth import verify_api_key
from api_server.db import audit as audit_db

router = APIRouter()


class AuditOut(BaseModel):
    id: int
    actor_id: str
    action: str
    resource_type: str | None
    resource_id: str | None
    detail: dict[str, Any]
    ip: str | None
    user_agent: str | None
    created_at: datetime


class AuditList(BaseModel):
    items: list[AuditOut]
    next_cursor: int | None = None


def _to_out(r: audit_db.AuditRow) -> AuditOut:
    return AuditOut(
        id=r.id, actor_id=r.actor_id,
        action=r.action,
        resource_type=r.resource_type,
        resource_id=r.resource_id,
        detail=r.detail, ip=r.ip,
        user_agent=r.user_agent,
        created_at=r.created_at,
    )


@router.get("/audit", response_model=AuditList)
async def list_audit(
    actor_id: str | None = Query(None),
    action_prefix: str | None = Query(None),
    resource_type: str | None = Query(None),
    resource_id: str | None = Query(None),
    since: datetime | None = Query(None, description="ISO 时间, >= 该时刻"),
    until: datetime | None = Query(None, description="ISO 时间, < 该时刻"),
    limit: int = Query(50, ge=1, le=200),
    before_id: int | None = Query(None),
    principal: Principal = Depends(verify_api_key),
) -> AuditList:
    rows, next_cursor = await asyncio.to_thread(
        audit_db.list_recent,
        tenant_id=principal.tenant_id,
        actor_id=actor_id,
        action_prefix=action_prefix,
        resource_type=resource_type,
        resource_id=resource_id,
        since=since,
        until=until,
        limit=limit,
        before_id=before_id,
    )
    return AuditList(items=[_to_out(r) for r in rows], next_cursor=next_cursor)


@router.get("/audit/csv")
async def export_audit_csv(
    actor_id: str | None = Query(None),
    action_prefix: str | None = Query(None),
    resource_type: str | None = Query(None),
    resource_id: str | None = Query(None),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    max_rows: int = Query(5000, ge=1, le=50000),
    principal: Principal = Depends(verify_api_key),
):
    """导出审计为 CSV. 默认最多 5000 行 (max_rows ≤ 50000).

    含 UTF-8 BOM, Excel 打开不乱码.
    """
    rows, _ = await asyncio.to_thread(
        audit_db.list_recent,
        tenant_id=principal.tenant_id,
        actor_id=actor_id,
        action_prefix=action_prefix,
        resource_type=resource_type,
        resource_id=resource_id,
        since=since,
        until=until,
        limit=max_rows,
        before_id=None,
    )

    def gen():
        buf = io.StringIO()
        # UTF-8 BOM 让 Excel 正确识别中文 CSV
        buf.write("\ufeff")
        w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
        w.writerow([
            "id", "created_at", "actor_id", "action",
            "resource_type", "resource_id", "ip", "user_agent",
            "detail_json",
        ])
        yield buf.getvalue()
        buf.seek(0); buf.truncate(0)
        for r in rows:
            w.writerow([
                r.id,
                r.created_at.isoformat(),
                r.actor_id,
                r.action,
                r.resource_type or "",
                r.resource_id or "",
                r.ip or "",
                (r.user_agent or "").replace("\n", " "),
                json.dumps(r.detail, ensure_ascii=False, separators=(",", ":")),
            ])
            yield buf.getvalue()
            buf.seek(0); buf.truncate(0)

    fname = f"audit-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.csv"
    return StreamingResponse(
        gen(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


class CleanupRequest(BaseModel):
    retain_days: int = Field(..., ge=1, le=3650, description="保留多少天")


class CleanupResponse(BaseModel):
    deleted: int
    retain_days: int


@router.post("/audit/cleanup", response_model=CleanupResponse)
async def cleanup_audit(
    payload: CleanupRequest,
    request: Request,
    principal: Principal = Depends(verify_api_key),
) -> CleanupResponse:
    """删 retain_days 天前的 audit. 自身行为也会被记录 (meta-audit)."""
    n = await asyncio.to_thread(
        audit_db.cleanup_older_than,
        tenant_id=principal.tenant_id,
        retain_days=payload.retain_days,
    )
    # meta-audit
    ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else None)
    )
    audit_db.insert(
        tenant_id=principal.tenant_id, actor_id=principal.actor_id,
        action="audit.cleanup",
        resource_type="audit_log", resource_id=None,
        detail={"retain_days": payload.retain_days, "deleted": n},
        ip=ip, user_agent=request.headers.get("user-agent"),
    )
    return CleanupResponse(deleted=n, retain_days=payload.retain_days)
