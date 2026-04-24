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
              (tenant_id, name, description, default_model, allowed_tools,
               default_collection, allowed_collections,
               budget_daily_usd, budget_monthly_usd, features, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            RETURNING id
            """,
            (
                str(tenant_id), name, description, default_model,
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
) -> bool:
    if role not in {"owner", "editor", "viewer"}:
        raise ValueError(f"invalid role: {role}")
    with _conn() as conn, conn.cursor() as cur:
        # 校验 workspace 属于本 tenant
        cur.execute(
            "SELECT 1 FROM workspaces WHERE id = %s AND tenant_id = %s AND deleted_at IS NULL",
            (str(workspace_id), str(tenant_id)),
        )
        if not cur.fetchone():
            return False
        cur.execute(
            """
            INSERT INTO workspace_members (workspace_id, actor_id, role)
            VALUES (%s, %s, %s)
            ON CONFLICT (workspace_id, actor_id) DO UPDATE SET role = EXCLUDED.role
            """,
            (str(workspace_id), actor_id, role),
        )
        conn.commit()
        return True


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


def list_members(*, workspace_id: UUID, tenant_id: UUID) -> list[MemberRow]:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT m.workspace_id, m.actor_id, m.role, m.created_at
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
            )
            for r in cur.fetchall()
        ]
