"""Sessions endpoints (Day 4 P0 #7).

POST   /v1/sessions                 创建空 session
GET    /v1/sessions?limit=20&before 列出当前 actor 的 sessions (cursor 分页)
GET    /v1/sessions/{id}            session 元数据 + 最近 N 条 messages
GET    /v1/sessions/{id}/messages   全部 messages (after_seq 分页)
DELETE /v1/sessions/{id}            软删
PATCH  /v1/sessions/{id}            改标题 (其他字段 v2)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api_server.acl import Principal
from api_server.auth import verify_api_key
from api_server.db import chat as chat_db

logger = logging.getLogger(__name__)
router = APIRouter()


class SessionCreate(BaseModel):
    title: str = Field(default="", max_length=200)
    workspace_id: UUID | None = None         # v1.5: session 锁定到 workspace
    skill_id: UUID | None = None


class SessionPatch(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


class SessionOut(BaseModel):
    id: UUID
    title: str
    message_count: int
    total_cost_usd: float
    created_at: datetime
    updated_at: datetime
    workspace_id: UUID | None = None
    skill_id: UUID | None = None


class SessionList(BaseModel):
    items: list[SessionOut]
    next_cursor: datetime | None = None


class MessageOut(BaseModel):
    id: UUID
    sequence_no: int
    role: str
    content: str
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    trace_id: str | None = None
    cost_usd: float = 0.0
    model: str | None = None
    created_at: datetime


def _row_to_out(row: chat_db.SessionRow) -> SessionOut:
    return SessionOut(
        id=row.id, title=row.title,
        message_count=row.message_count,
        total_cost_usd=float(row.total_cost_usd),
        created_at=row.created_at, updated_at=row.updated_at,
        workspace_id=row.workspace_id, skill_id=row.skill_id,
    )


def _msg_to_out(m: chat_db.MessageRow) -> MessageOut:
    return MessageOut(
        id=m.id, sequence_no=m.sequence_no, role=m.role, content=m.content,
        tool_calls=m.tool_calls, tool_call_id=m.tool_call_id,
        tool_name=m.tool_name, trace_id=m.trace_id,
        cost_usd=m.cost_usd, model=m.model, created_at=m.created_at,
    )


@router.post("/sessions", response_model=SessionOut)
async def create_session(
    payload: SessionCreate,
    principal: Principal = Depends(verify_api_key),
) -> SessionOut:
    sid = await asyncio.to_thread(
        chat_db.create_session,
        tenant_id=principal.tenant_id,
        actor_id=principal.actor_id,
        title=payload.title,
        workspace_id=payload.workspace_id,
        skill_id=payload.skill_id,
    )
    row = await asyncio.to_thread(
        chat_db.get_session, session_id=sid, tenant_id=principal.tenant_id,
    )
    if row is None:
        raise HTTPException(500, "session created but not retrievable")
    return _row_to_out(row)


@router.get("/sessions", response_model=SessionList)
async def list_sessions(
    workspace_id: UUID | None = Query(None, description="只列本 workspace 的 session"),
    limit: int = Query(20, ge=1, le=100),
    before: datetime | None = None,
    principal: Principal = Depends(verify_api_key),
) -> SessionList:
    rows, next_cursor = await asyncio.to_thread(
        chat_db.list_sessions,
        tenant_id=principal.tenant_id,
        actor_id=principal.actor_id,
        workspace_id=workspace_id,
        limit=limit, before=before,
    )
    return SessionList(
        items=[_row_to_out(r) for r in rows],
        next_cursor=next_cursor,
    )


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: UUID,
    include_messages: bool = Query(True),
    msg_limit: int = Query(100, ge=1, le=500),
    principal: Principal = Depends(verify_api_key),
) -> dict[str, Any]:
    row = await asyncio.to_thread(
        chat_db.get_session,
        session_id=session_id, tenant_id=principal.tenant_id,
    )
    if row is None:
        raise HTTPException(404, "session not found")
    out: dict[str, Any] = {"session": _row_to_out(row).model_dump()}
    if include_messages:
        msgs = await asyncio.to_thread(
            chat_db.get_messages,
            session_id=session_id,
            tenant_id=principal.tenant_id,
            limit=msg_limit,
        )
        out["messages"] = [_msg_to_out(m).model_dump() for m in msgs]
    return out


@router.get("/sessions/{session_id}/messages")
async def list_messages(
    session_id: UUID,
    after_seq: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    principal: Principal = Depends(verify_api_key),
) -> dict[str, Any]:
    msgs = await asyncio.to_thread(
        chat_db.get_messages,
        session_id=session_id,
        tenant_id=principal.tenant_id,
        after_seq=after_seq, limit=limit,
    )
    return {"messages": [_msg_to_out(m).model_dump() for m in msgs]}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: UUID,
    principal: Principal = Depends(verify_api_key),
) -> dict[str, bool]:
    ok = await asyncio.to_thread(
        chat_db.delete_session,
        session_id=session_id, tenant_id=principal.tenant_id,
    )
    if not ok:
        raise HTTPException(404, "session not found or already deleted")
    return {"deleted": True}


@router.patch("/sessions/{session_id}", response_model=SessionOut)
async def patch_session(
    session_id: UUID,
    payload: SessionPatch,
    principal: Principal = Depends(verify_api_key),
) -> SessionOut:
    ok = await asyncio.to_thread(
        chat_db.update_session_title,
        session_id=session_id, tenant_id=principal.tenant_id,
        title=payload.title,
    )
    if not ok:
        raise HTTPException(404, "session not found")
    row = await asyncio.to_thread(
        chat_db.get_session,
        session_id=session_id, tenant_id=principal.tenant_id,
    )
    return _row_to_out(row)  # type: ignore[arg-type]
