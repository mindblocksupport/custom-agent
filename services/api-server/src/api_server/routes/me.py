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


class MyBudgetOut(BaseModel):
    workspace_id: UUID
    today_cost_usd: float
    month_cost_usd: float
    budget_daily_usd: float | None
    budget_monthly_usd: float | None
    has_limit: bool


@router.get("/workspaces/{wid}/me/budget", response_model=MyBudgetOut)
async def my_budget(
    wid: UUID,
    principal: Principal = Depends(verify_api_key),
) -> MyBudgetOut:
    """当前 actor 在指定 workspace 的预算与已用. 用于 sidebar 实时反馈.

    没设 budget → has_limit=false (前端不显示 pill).
    """
    b = await asyncio.to_thread(
        ws_db.fetch_actor_budget_usage,
        workspace_id=wid,
        tenant_id=principal.tenant_id,
        actor_id=principal.actor_id,
    )
    if b is None:
        # 不是 member 或 workspace 不存在
        raise HTTPException(404, "not a member of this workspace")
    return MyBudgetOut(
        workspace_id=wid,
        today_cost_usd=b.today_cost_usd,
        month_cost_usd=b.month_cost_usd,
        budget_daily_usd=b.budget_daily_usd,
        budget_monthly_usd=b.budget_monthly_usd,
        has_limit=(
            b.budget_daily_usd is not None or b.budget_monthly_usd is not None
        ),
    )


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
            # skills 没有 tenant_id 列, 通过 workspaces JOIN 算
            cur.execute(
                """
                SELECT count(*) AS n
                FROM skills s
                JOIN workspaces w ON w.id = s.workspace_id
                WHERE w.tenant_id = %s
                  AND s.deleted_at IS NULL
                  AND w.deleted_at IS NULL
                  AND (
                    s.visibility = 'public'
                    OR s.workspace_id IN (
                      SELECT workspace_id FROM workspace_members
                      WHERE actor_id = %s
                    )
                  )
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


class UsageBySkillPoint(BaseModel):
    skill_id: UUID | None
    skill_name: str          # "(通用对话)" if skill_id is null
    sessions: int
    messages: int
    cost_usd: float


class UsageDailyBySkillPoint(BaseModel):
    """每天 × 每 skill 的成本/消息. 用来画 stacked bar chart."""
    day: date
    skill_id: UUID | None
    skill_name: str
    cost_usd: float
    messages: int


class UsageDailyByModelPoint(BaseModel):
    """每天 × 每 model 的成本/消息. 用来对比模型成本结构."""
    day: date
    model: str
    cost_usd: float
    messages: int


class UsageByActorPoint(BaseModel):
    """每 actor 总成本 + 会话数 (谁烧的预算)."""
    actor_id: str
    sessions: int
    messages: int
    cost_usd: float


class UsageDailyByActorPoint(BaseModel):
    """每天 × 每 actor 的成本 (堆叠图)."""
    day: date
    actor_id: str
    cost_usd: float
    messages: int


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
    by_skill: list[UsageBySkillPoint]
    daily_by_skill: list[UsageDailyBySkillPoint]
    daily_by_model: list[UsageDailyByModelPoint]
    by_actor: list[UsageByActorPoint]
    daily_by_actor: list[UsageDailyByActorPoint]
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

            # 按 skill 聚合 (LEFT JOIN, NULL = 通用对话)
            cur.execute(
                """
                SELECT s.skill_id,
                       coalesce(sk.name, '(通用对话)') AS skill_name,
                       count(DISTINCT s.id) AS sessions,
                       count(m.id) AS messages,
                       coalesce(sum(m.cost_usd), 0)::float AS cost_usd
                FROM chat_messages m
                JOIN chat_sessions s ON s.id = m.session_id
                LEFT JOIN skills sk ON sk.id = s.skill_id
                WHERE s.workspace_id = %s
                  AND s.tenant_id = %s
                  AND s.deleted_at IS NULL
                  AND m.created_at >= %s
                GROUP BY s.skill_id, sk.name
                ORDER BY cost_usd DESC
                """,
                (str(wid), str(principal.tenant_id), cutoff),
            )
            skill_rows = cur.fetchall()

            # 每日 × skill 堆叠 (用于 stacked chart)
            cur.execute(
                """
                SELECT date_trunc('day', m.created_at)::date AS day,
                       s.skill_id,
                       coalesce(sk.name, '(通用对话)') AS skill_name,
                       count(m.id) AS messages,
                       coalesce(sum(m.cost_usd), 0)::float AS cost_usd
                FROM chat_messages m
                JOIN chat_sessions s ON s.id = m.session_id
                LEFT JOIN skills sk ON sk.id = s.skill_id
                WHERE s.workspace_id = %s
                  AND s.tenant_id = %s
                  AND s.deleted_at IS NULL
                  AND m.created_at >= %s
                GROUP BY day, s.skill_id, sk.name
                ORDER BY day ASC, cost_usd DESC
                """,
                (str(wid), str(principal.tenant_id), cutoff),
            )
            daily_skill_rows = cur.fetchall()

            # 每日 × model
            cur.execute(
                """
                SELECT date_trunc('day', m.created_at)::date AS day,
                       coalesce(m.model, 'unknown') AS model,
                       count(m.id) AS messages,
                       coalesce(sum(m.cost_usd), 0)::float AS cost_usd
                FROM chat_messages m
                JOIN chat_sessions s ON s.id = m.session_id
                WHERE s.workspace_id = %s
                  AND s.tenant_id = %s
                  AND s.deleted_at IS NULL
                  AND m.created_at >= %s
                  AND m.role = 'assistant'
                GROUP BY day, model
                ORDER BY day ASC, cost_usd DESC
                """,
                (str(wid), str(principal.tenant_id), cutoff),
            )
            daily_model_rows = cur.fetchall()

            # 按 actor 聚合 — "谁烧的预算"
            cur.execute(
                """
                SELECT s.actor_id,
                       count(DISTINCT s.id) AS sessions,
                       count(m.id) AS messages,
                       coalesce(sum(m.cost_usd), 0)::float AS cost_usd
                FROM chat_messages m
                JOIN chat_sessions s ON s.id = m.session_id
                WHERE s.workspace_id = %s
                  AND s.tenant_id = %s
                  AND s.deleted_at IS NULL
                  AND m.created_at >= %s
                GROUP BY s.actor_id
                ORDER BY cost_usd DESC
                """,
                (str(wid), str(principal.tenant_id), cutoff),
            )
            actor_rows = cur.fetchall()

            # 每日 × actor 堆叠
            cur.execute(
                """
                SELECT date_trunc('day', m.created_at)::date AS day,
                       s.actor_id,
                       count(m.id) AS messages,
                       coalesce(sum(m.cost_usd), 0)::float AS cost_usd
                FROM chat_messages m
                JOIN chat_sessions s ON s.id = m.session_id
                WHERE s.workspace_id = %s
                  AND s.tenant_id = %s
                  AND s.deleted_at IS NULL
                  AND m.created_at >= %s
                GROUP BY day, s.actor_id
                ORDER BY day ASC, cost_usd DESC
                """,
                (str(wid), str(principal.tenant_id), cutoff),
            )
            daily_actor_rows = cur.fetchall()

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
            "skill_rows": skill_rows,
            "daily_skill_rows": daily_skill_rows,
            "daily_model_rows": daily_model_rows,
            "actor_rows": actor_rows,
            "daily_actor_rows": daily_actor_rows,
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
    by_skill = [
        UsageBySkillPoint(
            skill_id=r["skill_id"],
            skill_name=r["skill_name"],
            sessions=int(r["sessions"]),
            messages=int(r["messages"]),
            cost_usd=float(r["cost_usd"]),
        )
        for r in res["skill_rows"]
    ]
    daily_by_skill = [
        UsageDailyBySkillPoint(
            day=r["day"],
            skill_id=r["skill_id"],
            skill_name=r["skill_name"],
            cost_usd=float(r["cost_usd"]),
            messages=int(r["messages"]),
        )
        for r in res["daily_skill_rows"]
    ]
    daily_by_model = [
        UsageDailyByModelPoint(
            day=r["day"],
            model=r["model"],
            cost_usd=float(r["cost_usd"]),
            messages=int(r["messages"]),
        )
        for r in res["daily_model_rows"]
    ]
    by_actor = [
        UsageByActorPoint(
            actor_id=r["actor_id"],
            sessions=int(r["sessions"]),
            messages=int(r["messages"]),
            cost_usd=float(r["cost_usd"]),
        )
        for r in res["actor_rows"]
    ]
    daily_by_actor = [
        UsageDailyByActorPoint(
            day=r["day"],
            actor_id=r["actor_id"],
            cost_usd=float(r["cost_usd"]),
            messages=int(r["messages"]),
        )
        for r in res["daily_actor_rows"]
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
        by_skill=by_skill,
        daily_by_skill=daily_by_skill,
        daily_by_model=daily_by_model,
        by_actor=by_actor,
        daily_by_actor=daily_by_actor,
        budget_daily_usd=ws.budget_daily_usd,
        budget_monthly_usd=ws.budget_monthly_usd,
        today_cost_usd=res["today"],
        month_cost_usd=res["month"],
    )
