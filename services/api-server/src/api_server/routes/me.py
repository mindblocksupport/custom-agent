"""Profile / 当前 actor 的元信息 endpoints.

GET /v1/me                                   当前身份 + 简要可用资源
GET /v1/workspaces/{wid}/usage?days=7        按天聚合 cost / messages / sessions
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg.rows import dict_row
from pydantic import BaseModel

from api_server.acl import Principal
from api_server.auth import verify_api_key
from api_server.db import workspaces as ws_db
from api_server.db.api_keys import _db_url

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------- /v1/me ----------

class MeOut(BaseModel):
    actor_id: str
    tenant_id: UUID
    principals: list[str]
    workspace_count: int
    skill_count_visible: int  # own + public
    api_version: str = "v1.5"


@router.get("/me", response_model=MeOut)
async def me(principal: Principal = Depends(verify_api_key)) -> MeOut:
    def _do() -> tuple[int, int]:
        with psycopg.connect(_db_url(), row_factory=dict_row) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*) AS n
                FROM workspaces w
                JOIN workspace_members m ON m.workspace_id = w.id
                WHERE w.tenant_id = %s AND w.deleted_at IS NULL AND m.actor_id = %s
                """,
                (str(principal.tenant_id), principal.actor_id),
            )
            ws_n = int(cur.fetchone()["n"])
            cur.execute(
                """
                SELECT count(*) AS n FROM skills
                WHERE tenant_id = %s AND deleted_at IS NULL
                  AND (visibility = 'public' OR workspace_id IN (
                    SELECT workspace_id FROM workspace_members WHERE actor_id = %s
                  ))
                """,
                (str(principal.tenant_id), principal.actor_id),
            )
            sk_n = int(cur.fetchone()["n"])
        return ws_n, sk_n

    ws_n, sk_n = await asyncio.to_thread(_do)
    return MeOut(
        actor_id=principal.actor_id,
        tenant_id=principal.tenant_id,
        principals=list(principal.principals),
        workspace_count=ws_n,
        skill_count_visible=sk_n,
    )


# ---------- /v1/workspaces/{wid}/usage ----------

class UsageDayPoint(BaseModel):
    day: date
    sessions: int
    messages: int
    cost_usd: float


class UsageByModelPoint(BaseModel):
    model: str
    messages: int
    cost_usd: float
    input_tokens: int
    output_tokens: int


class UsageOut(BaseModel):
    workspace_id: UUID
    workspace_name: str
    days: int
    total_sessions: int
    total_messages: int
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    daily: list[UsageDayPoint]
    by_model: list[UsageByModelPoint]
    budget_daily_usd: float | None
    budget_monthly_usd: float | None
    today_cost_usd: float
    month_cost_usd: float


@router.get("/workspaces/{wid}/usage", response_model=UsageOut)
async def workspace_usage(
    wid: UUID,
    days: int = Query(7, ge=1, le=90),
    principal: Principal = Depends(verify_api_key),
) -> UsageOut:
    # 校验 workspace 属于本 tenant
    ws = await asyncio.to_thread(
        ws_db.get, workspace_id=wid, tenant_id=principal.tenant_id,
    )
    if ws is None:
        raise HTTPException(404, "workspace not found")

    def _do() -> dict[str, Any]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        with psycopg.connect(_db_url(), row_factory=dict_row) as conn, conn.cursor() as cur:
            # 按天聚合 (从 chat_messages, JOIN sessions for workspace_id)
            cur.execute(
                """
                SELECT date_trunc('day', m.created_at)::date AS day,
                       count(DISTINCT m.session_id) AS sessions,
                       count(*) AS messages,
                       coalesce(sum(m.cost_usd), 0)::float AS cost_usd,
                       coalesce(sum(m.input_tokens), 0)::int AS input_tokens,
                       coalesce(sum(m.output_tokens), 0)::int AS output_tokens
                FROM chat_messages m
                JOIN chat_sessions s ON s.id = m.session_id
                WHERE s.workspace_id = %s
                  AND s.tenant_id = %s
                  AND s.deleted_at IS NULL
                  AND m.created_at >= %s
                GROUP BY day
                ORDER BY day ASC
                """,
                (str(wid), str(principal.tenant_id), cutoff),
            )
            day_rows = cur.fetchall()

            # 按模型聚合
            cur.execute(
                """
                SELECT coalesce(m.model, 'unknown') AS model,
                       count(*) AS messages,
                       coalesce(sum(m.cost_usd), 0)::float AS cost_usd,
                       coalesce(sum(m.input_tokens), 0)::int AS input_tokens,
                       coalesce(sum(m.output_tokens), 0)::int AS output_tokens
                FROM chat_messages m
                JOIN chat_sessions s ON s.id = m.session_id
                WHERE s.workspace_id = %s
                  AND s.tenant_id = %s
                  AND s.deleted_at IS NULL
                  AND m.created_at >= %s
                  AND m.role = 'assistant'
                GROUP BY model
                ORDER BY cost_usd DESC
                """,
                (str(wid), str(principal.tenant_id), cutoff),
            )
            model_rows = cur.fetchall()

            # 总计
            cur.execute(
                """
                SELECT count(DISTINCT s.id) AS sessions,
                       count(m.id) AS messages,
                       coalesce(sum(m.cost_usd), 0)::float AS cost_usd,
                       coalesce(sum(m.input_tokens), 0)::int AS input_tokens,
                       coalesce(sum(m.output_tokens), 0)::int AS output_tokens
                FROM chat_messages m
                JOIN chat_sessions s ON s.id = m.session_id
                WHERE s.workspace_id = %s
                  AND s.tenant_id = %s
                  AND s.deleted_at IS NULL
                  AND m.created_at >= %s
                """,
                (str(wid), str(principal.tenant_id), cutoff),
            )
            tot = cur.fetchone()

            # 今日成本 (UTC day)
            cur.execute(
                """
                SELECT coalesce(sum(m.cost_usd), 0)::float AS c
                FROM chat_messages m
                JOIN chat_sessions s ON s.id = m.session_id
                WHERE s.workspace_id = %s
                  AND s.tenant_id = %s
                  AND s.deleted_at IS NULL
                  AND m.created_at >= date_trunc('day', now())
                """,
                (str(wid), str(principal.tenant_id)),
            )
            today = float(cur.fetchone()["c"])

            cur.execute(
                """
                SELECT coalesce(sum(m.cost_usd), 0)::float AS c
                FROM chat_messages m
                JOIN chat_sessions s ON s.id = m.session_id
                WHERE s.workspace_id = %s
                  AND s.tenant_id = %s
                  AND s.deleted_at IS NULL
                  AND m.created_at >= date_trunc('month', now())
                """,
                (str(wid), str(principal.tenant_id)),
            )
            month = float(cur.fetchone()["c"])

        return {
            "day_rows": day_rows, "model_rows": model_rows,
            "tot": tot, "today": today, "month": month,
        }

    res = await asyncio.to_thread(_do)
    daily = [
        UsageDayPoint(
            day=r["day"], sessions=int(r["sessions"]),
            messages=int(r["messages"]), cost_usd=float(r["cost_usd"]),
        )
        for r in res["day_rows"]
    ]
    by_model = [
        UsageByModelPoint(
            model=r["model"], messages=int(r["messages"]),
            cost_usd=float(r["cost_usd"]),
            input_tokens=int(r["input_tokens"]),
            output_tokens=int(r["output_tokens"]),
        )
        for r in res["model_rows"]
    ]
    tot = res["tot"]
    return UsageOut(
        workspace_id=wid,
        workspace_name=ws.name,
        days=days,
        total_sessions=int(tot["sessions"] or 0),
        total_messages=int(tot["messages"] or 0),
        total_cost_usd=float(tot["cost_usd"] or 0),
        total_input_tokens=int(tot["input_tokens"] or 0),
        total_output_tokens=int(tot["output_tokens"] or 0),
        daily=daily,
        by_model=by_model,
        budget_daily_usd=ws.budget_daily_usd,
        budget_monthly_usd=ws.budget_monthly_usd,
        today_cost_usd=res["today"],
        month_cost_usd=res["month"],
    )
