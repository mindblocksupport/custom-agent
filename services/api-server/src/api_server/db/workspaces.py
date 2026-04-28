"""workspaces + workspace_members DB 层 (v1.5 沉淀层)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from api_server.db.api_keys import _db_url

logger = logging.getLogger(__name__)


@dataclass
class WorkspaceRow:
    id: UUID
    tenant_id: UUID
    name: str
    description: str
    default_model: str
    allowed_models: list[str]
    allowed_tools: list[str]
    default_collection: str
    allowed_collections: list[str]
    budget_daily_usd: float | None
    budget_monthly_usd: float | None
    features: dict
    created_by: str | None
    created_at: datetime
    updated_at: datetime


@dataclass
class MemberRow:
    workspace_id: UUID
    actor_id: str
    role: str
    created_at: datetime
    budget_daily_usd: float | None = None
    budget_monthly_usd: float | None = None


def _conn():
    return psycopg.connect(_db_url(), row_factory=dict_row)


def _row(r: dict) -> WorkspaceRow:
    return WorkspaceRow(
        id=r["id"], tenant_id=r["tenant_id"], name=r["name"],
        description=r.get("description") or "",
        default_model=r["default_model"],
        allowed_models=list(r.get("allowed_models") or []),
        allowed_tools=list(r.get("allowed_tools") or []),
        default_collection=r["default_collection"],
        allowed_collections=list(r.get("allowed_collections") or []),
        budget_daily_usd=float(r["budget_daily_usd"]) if r.get("budget_daily_usd") is not None else None,
        budget_monthly_usd=float(r["budget_monthly_usd"]) if r.get("budget_monthly_usd") is not None else None,
        features=r.get("features") or {},
        created_by=r.get("created_by"),
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def create(
    *, tenant_id: UUID, name: str, actor_id: str,
    description: str = "", default_model: str = "auto",
    allowed_models: list[str] | None = None,
    allowed_tools: list[str] | None = None,
    default_collection: str = "default",
    allowed_collections: list[str] | None = None,
    budget_daily_usd: float | None = None,
    budget_monthly_usd: float | None = None,
    features: dict | None = None,
) -> UUID:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO workspaces
              (tenant_id, name, description, default_model,
               allowed_models, allowed_tools,
               default_collection, allowed_collections,
               budget_daily_usd, budget_monthly_usd, features, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            RETURNING id
            """,
            (
                str(tenant_id), name, description, default_model,
                allowed_models or [],
                allowed_tools or [],
                default_collection, allowed_collections or ["default"],
                budget_daily_usd, budget_monthly_usd,
                json.dumps(features or {}), actor_id,
            ),
        )
        new_id = cur.fetchone()["id"]
        # 创建者自动成为 owner
        cur.execute(
            """
            INSERT INTO workspace_members (workspace_id, actor_id, role)
            VALUES (%s, %s, 'owner')
            ON CONFLICT DO NOTHING
            """,
            (str(new_id), actor_id),
        )
        conn.commit()
        return new_id


def list_for_tenant(*, tenant_id: UUID) -> list[WorkspaceRow]:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT * FROM workspaces
            WHERE tenant_id = %s AND deleted_at IS NULL
            ORDER BY updated_at DESC
            """,
            (str(tenant_id),),
        )
        return [_row(r) for r in cur.fetchall()]


def list_for_actor(*, tenant_id: UUID, actor_id: str) -> list[WorkspaceRow]:
    """返回当前 actor 是 member 的所有 workspace."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT w.* FROM workspaces w
            JOIN workspace_members m ON m.workspace_id = w.id
            WHERE w.tenant_id = %s AND w.deleted_at IS NULL
              AND m.actor_id = %s
            ORDER BY w.updated_at DESC
            """,
            (str(tenant_id), actor_id),
        )
        return [_row(r) for r in cur.fetchall()]


def get(*, workspace_id: UUID, tenant_id: UUID) -> WorkspaceRow | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT * FROM workspaces
            WHERE id = %s AND tenant_id = %s AND deleted_at IS NULL
            """,
            (str(workspace_id), str(tenant_id)),
        )
        r = cur.fetchone()
        return _row(r) if r else None


def update(
    *, workspace_id: UUID, tenant_id: UUID, **fields: Any,
) -> bool:
    """部分更新. 仅允许白名单字段."""
    allowed = {
        "name", "description", "default_model", "allowed_models",
        "allowed_tools", "default_collection", "allowed_collections",
        "budget_daily_usd", "budget_monthly_usd",
    }
    sets: list[str] = []
    params: list[Any] = []
    for k, v in fields.items():
        if k not in allowed or v is None:
            continue
        sets.append(f"{k} = %s")
        params.append(v)
    if "features" in fields and fields["features"] is not None:
        sets.append("features = %s::jsonb")
        params.append(json.dumps(fields["features"]))
    if not sets:
        return False
    sets.append("updated_at = now()")
    params.extend([str(workspace_id), str(tenant_id)])
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE workspaces SET {', '.join(sets)} "
            "WHERE id = %s AND tenant_id = %s AND deleted_at IS NULL",
            params,
        )
        ok = cur.rowcount > 0
        conn.commit()
        return ok


def delete(*, workspace_id: UUID, tenant_id: UUID) -> bool:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE workspaces SET deleted_at = now() "
            "WHERE id = %s AND tenant_id = %s AND deleted_at IS NULL",
            (str(workspace_id), str(tenant_id)),
        )
        ok = cur.rowcount > 0
        conn.commit()
        return ok


# ---------- members ----------

def add_member(
    *, workspace_id: UUID, tenant_id: UUID, actor_id: str, role: str = "viewer",
    budget_daily_usd: float | None = None,
    budget_monthly_usd: float | None = None,
) -> bool:
    if role not in {"owner", "editor", "viewer"}:
        raise ValueError(f"invalid role: {role}")
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM workspaces WHERE id = %s AND tenant_id = %s AND deleted_at IS NULL",
            (str(workspace_id), str(tenant_id)),
        )
        if not cur.fetchone():
            return False
        cur.execute(
            """
            INSERT INTO workspace_members
              (workspace_id, actor_id, role, budget_daily_usd, budget_monthly_usd)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (workspace_id, actor_id) DO UPDATE
              SET role = EXCLUDED.role,
                  budget_daily_usd = EXCLUDED.budget_daily_usd,
                  budget_monthly_usd = EXCLUDED.budget_monthly_usd
            """,
            (
                str(workspace_id), actor_id, role,
                budget_daily_usd, budget_monthly_usd,
            ),
        )
        conn.commit()
        return True


def update_member_budget(
    *, workspace_id: UUID, tenant_id: UUID, actor_id: str,
    budget_daily_usd: float | None,
    budget_monthly_usd: float | None,
) -> bool:
    """更新成员 budget. 不影响 role. None = 解除限制."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE workspace_members
            SET budget_daily_usd = %s, budget_monthly_usd = %s
            WHERE workspace_id = %s AND actor_id = %s
              AND workspace_id IN (
                SELECT id FROM workspaces WHERE tenant_id = %s AND deleted_at IS NULL
              )
            """,
            (
                budget_daily_usd, budget_monthly_usd,
                str(workspace_id), actor_id, str(tenant_id),
            ),
        )
        ok = cur.rowcount > 0
        conn.commit()
        return ok


def remove_member(
    *, workspace_id: UUID, tenant_id: UUID, actor_id: str,
) -> bool:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM workspace_members
            WHERE workspace_id = %s AND actor_id = %s
              AND workspace_id IN (
                SELECT id FROM workspaces WHERE tenant_id = %s AND deleted_at IS NULL
              )
            """,
            (str(workspace_id), actor_id, str(tenant_id)),
        )
        ok = cur.rowcount > 0
        conn.commit()
        return ok


@dataclass
class BudgetUsage:
    """workspace 当前预算使用快照. 跟 routes/me.py UsageOut 的 today/month 同源."""
    today_cost_usd: float
    month_cost_usd: float
    budget_daily_usd: float | None
    budget_monthly_usd: float | None

    @property
    def daily_exceeded(self) -> bool:
        return (
            self.budget_daily_usd is not None
            and self.today_cost_usd >= self.budget_daily_usd
        )

    @property
    def monthly_exceeded(self) -> bool:
        return (
            self.budget_monthly_usd is not None
            and self.month_cost_usd >= self.budget_monthly_usd
        )

    @property
    def any_exceeded(self) -> bool:
        return self.daily_exceeded or self.monthly_exceeded


def fetch_actor_budget_usage(
    *, workspace_id: UUID, tenant_id: UUID, actor_id: str,
) -> BudgetUsage | None:
    """同 fetch_budget_usage 但只算 actor 自己的 cost.

    workspace_members.budget_* 没设 → 返回 None (调用方应跳过 actor 检查).
    """
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              m.budget_daily_usd,
              m.budget_monthly_usd,
              coalesce((
                SELECT sum(msg.cost_usd) FROM chat_messages msg
                JOIN chat_sessions s ON s.id = msg.session_id
                WHERE s.workspace_id = m.workspace_id
                  AND s.tenant_id = w.tenant_id
                  AND s.actor_id = m.actor_id
                  AND s.deleted_at IS NULL
                  AND msg.created_at >= date_trunc('day', now())
              ), 0)::float AS today_cost,
              coalesce((
                SELECT sum(msg.cost_usd) FROM chat_messages msg
                JOIN chat_sessions s ON s.id = msg.session_id
                WHERE s.workspace_id = m.workspace_id
                  AND s.tenant_id = w.tenant_id
                  AND s.actor_id = m.actor_id
                  AND s.deleted_at IS NULL
                  AND msg.created_at >= date_trunc('month', now())
              ), 0)::float AS month_cost
            FROM workspace_members m
            JOIN workspaces w ON w.id = m.workspace_id
            WHERE m.workspace_id = %s
              AND m.actor_id = %s
              AND w.tenant_id = %s
              AND w.deleted_at IS NULL
            """,
            (str(workspace_id), actor_id, str(tenant_id)),
        )
        r = cur.fetchone()
        if r is None:
            return None
        return BudgetUsage(
            today_cost_usd=float(r["today_cost"] or 0),
            month_cost_usd=float(r["month_cost"] or 0),
            budget_daily_usd=(
                float(r["budget_daily_usd"]) if r.get("budget_daily_usd") is not None else None
            ),
            budget_monthly_usd=(
                float(r["budget_monthly_usd"]) if r.get("budget_monthly_usd") is not None else None
            ),
        )


def fetch_budget_usage(
    *, workspace_id: UUID, tenant_id: UUID,
) -> BudgetUsage | None:
    """单次 SQL 拉今日 + 当月 cost + workspace.budget_*. 找不到 ws → None."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              w.budget_daily_usd,
              w.budget_monthly_usd,
              coalesce((
                SELECT sum(m.cost_usd) FROM chat_messages m
                JOIN chat_sessions s ON s.id = m.session_id
                WHERE s.workspace_id = w.id AND s.tenant_id = w.tenant_id
                  AND s.deleted_at IS NULL
                  AND m.created_at >= date_trunc('day', now())
              ), 0)::float AS today_cost,
              coalesce((
                SELECT sum(m.cost_usd) FROM chat_messages m
                JOIN chat_sessions s ON s.id = m.session_id
                WHERE s.workspace_id = w.id AND s.tenant_id = w.tenant_id
                  AND s.deleted_at IS NULL
                  AND m.created_at >= date_trunc('month', now())
              ), 0)::float AS month_cost
            FROM workspaces w
            WHERE w.id = %s AND w.tenant_id = %s AND w.deleted_at IS NULL
            """,
            (str(workspace_id), str(tenant_id)),
        )
        r = cur.fetchone()
        if r is None:
            return None
        return BudgetUsage(
            today_cost_usd=float(r["today_cost"] or 0),
            month_cost_usd=float(r["month_cost"] or 0),
            budget_daily_usd=(
                float(r["budget_daily_usd"]) if r.get("budget_daily_usd") is not None else None
            ),
            budget_monthly_usd=(
                float(r["budget_monthly_usd"]) if r.get("budget_monthly_usd") is not None else None
            ),
        )


def list_members(*, workspace_id: UUID, tenant_id: UUID) -> list[MemberRow]:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT m.workspace_id, m.actor_id, m.role, m.created_at,
                   m.budget_daily_usd, m.budget_monthly_usd
            FROM workspace_members m
            JOIN workspaces w ON w.id = m.workspace_id
            WHERE w.id = %s AND w.tenant_id = %s AND w.deleted_at IS NULL
            ORDER BY m.created_at ASC
            """,
            (str(workspace_id), str(tenant_id)),
        )
        return [
            MemberRow(
                workspace_id=r["workspace_id"],
                actor_id=r["actor_id"],
                role=r["role"],
                created_at=r["created_at"],
                budget_daily_usd=(
                    float(r["budget_daily_usd"])
                    if r.get("budget_daily_usd") is not None else None
                ),
                budget_monthly_usd=(
                    float(r["budget_monthly_usd"])
                    if r.get("budget_monthly_usd") is not None else None
                ),
            )
            for r in cur.fetchall()
        ]
