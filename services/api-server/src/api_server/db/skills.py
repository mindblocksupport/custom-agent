"""skills DB 层 (v1.5 沉淀层).

Skill 归属 workspace, 同 workspace 下用 (name, version) 唯一.
"""

from __future__ import annotations

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
class SkillRow:
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
    created_by: str | None
    created_at: datetime
    updated_at: datetime


def _conn():
    return psycopg.connect(_db_url(), row_factory=dict_row)


def _row(r: dict) -> SkillRow:
    return SkillRow(
        id=r["id"],
        workspace_id=r["workspace_id"],
        name=r["name"],
        description=r.get("description") or "",
        version=int(r["version"]),
        system_prompt=r.get("system_prompt") or "",
        allowed_tools=list(r.get("allowed_tools") or []),
        default_collections=list(r.get("default_collections") or []),
        starter_examples=list(r.get("starter_examples") or []),
        visibility=r["visibility"],
        budget_per_call_usd=(
            float(r["budget_per_call_usd"])
            if r.get("budget_per_call_usd") is not None
            else None
        ),
        tags=list(r.get("tags") or []),
        created_by=r.get("created_by"),
        created_at=r["created_at"],
        updated_at=r["updated_at"],
    )


def _check_workspace_belongs(
    cur, workspace_id: UUID, tenant_id: UUID,
) -> bool:
    cur.execute(
        "SELECT 1 FROM workspaces WHERE id = %s AND tenant_id = %s AND deleted_at IS NULL",
        (str(workspace_id), str(tenant_id)),
    )
    return cur.fetchone() is not None


def create(
    *,
    workspace_id: UUID,
    tenant_id: UUID,
    name: str,
    actor_id: str,
    description: str = "",
    system_prompt: str = "",
    allowed_tools: list[str] | None = None,
    default_collections: list[str] | None = None,
    starter_examples: list[str] | None = None,
    visibility: str = "workspace",
    budget_per_call_usd: float | None = None,
    tags: list[str] | None = None,
) -> UUID | None:
    if visibility not in {"private", "workspace", "public"}:
        raise ValueError(f"invalid visibility: {visibility}")
    with _conn() as conn, conn.cursor() as cur:
        if not _check_workspace_belongs(cur, workspace_id, tenant_id):
            return None
        cur.execute(
            """
            INSERT INTO skills
              (workspace_id, name, description, version, system_prompt,
               allowed_tools, default_collections, starter_examples,
               visibility, budget_per_call_usd, tags, created_by)
            VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                str(workspace_id), name, description, system_prompt,
                allowed_tools or [], default_collections or [],
                starter_examples or [], visibility, budget_per_call_usd,
                tags or [], actor_id,
            ),
        )
        new_id = cur.fetchone()["id"]
        conn.commit()
        return new_id


def list_for_workspace(
    *, workspace_id: UUID, tenant_id: UUID,
) -> list[SkillRow]:
    """列出本 workspace 的最新版 skill (每 name 取 max version)."""
    with _conn() as conn, conn.cursor() as cur:
        if not _check_workspace_belongs(cur, workspace_id, tenant_id):
            return []
        cur.execute(
            """
            SELECT DISTINCT ON (name) *
            FROM skills
            WHERE workspace_id = %s AND deleted_at IS NULL
            ORDER BY name, version DESC
            """,
            (str(workspace_id),),
        )
        return [_row(r) for r in cur.fetchall()]


def list_public_in_tenant(
    *, tenant_id: UUID, exclude_workspace_id: UUID | None = None,
) -> list[SkillRow]:
    """v1.5 Skill 市场: 列出本 tenant 下所有 visibility=public 的 skill (最新版).

    - 跨 workspace, 但不跨 tenant (租户隔离)
    - exclude_workspace_id: 排除某个 workspace (通常是当前 workspace 自己的 skill 已单独列了)
    - 每个 (workspace_id, name) 只返回最新版
    """
    sql = """
        SELECT DISTINCT ON (s.workspace_id, s.name) s.*
        FROM skills s
        JOIN workspaces w ON w.id = s.workspace_id
        WHERE w.tenant_id = %s
          AND s.visibility = 'public'
          AND s.deleted_at IS NULL
          AND w.deleted_at IS NULL
    """
    params: list[Any] = [str(tenant_id)]
    if exclude_workspace_id is not None:
        sql += " AND s.workspace_id != %s"
        params.append(str(exclude_workspace_id))
    sql += " ORDER BY s.workspace_id, s.name, s.version DESC"
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return [_row(r) for r in cur.fetchall()]


def get(
    *, skill_id: UUID, tenant_id: UUID,
) -> SkillRow | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.* FROM skills s
            JOIN workspaces w ON w.id = s.workspace_id
            WHERE s.id = %s AND w.tenant_id = %s
              AND s.deleted_at IS NULL AND w.deleted_at IS NULL
            """,
            (str(skill_id), str(tenant_id)),
        )
        r = cur.fetchone()
        return _row(r) if r else None


def update(
    *, skill_id: UUID, tenant_id: UUID, **fields: Any,
) -> bool:
    """部分更新 (不改 version, 改 version 用 new_version)."""
    allowed = {
        "name", "description", "system_prompt", "allowed_tools",
        "default_collections", "starter_examples", "visibility",
        "budget_per_call_usd", "tags",
    }
    sets: list[str] = []
    params: list[Any] = []
    for k, v in fields.items():
        if k not in allowed or v is None:
            continue
        sets.append(f"{k} = %s")
        params.append(v)
    if not sets:
        return False
    sets.append("updated_at = now()")
    params.extend([str(skill_id), str(tenant_id)])
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE skills SET {', '.join(sets)}
            WHERE id = %s AND deleted_at IS NULL
              AND workspace_id IN (
                SELECT id FROM workspaces WHERE tenant_id = %s AND deleted_at IS NULL
              )
            """,
            params,
        )
        ok = cur.rowcount > 0
        conn.commit()
        return ok


def delete(*, skill_id: UUID, tenant_id: UUID) -> bool:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE skills SET deleted_at = now()
            WHERE id = %s AND deleted_at IS NULL
              AND workspace_id IN (
                SELECT id FROM workspaces WHERE tenant_id = %s AND deleted_at IS NULL
              )
            """,
            (str(skill_id), str(tenant_id)),
        )
        ok = cur.rowcount > 0
        conn.commit()
        return ok


def rollback_to(
    *, skill_id: UUID, tenant_id: UUID, target_version: int,
) -> UUID | None:
    """把 (workspace_id, name) 下的 target_version 拷贝成最新版.

    - 不真正删除新版 (历史保留, 审计可追溯)
    - 等价于 new_version + override 全字段 = target_version 内容
    - 返回新建 row id; 找不到 / target_version 不存在 → None
    """
    src = get(skill_id=skill_id, tenant_id=tenant_id)
    if src is None:
        return None
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT * FROM skills
            WHERE workspace_id = %s AND name = %s AND version = %s
              AND deleted_at IS NULL
            """,
            (str(src.workspace_id), src.name, target_version),
        )
        target_raw = cur.fetchone()
        if target_raw is None:
            return None
        target = _row(target_raw)
        # 找下一个 version no
        cur.execute(
            """
            SELECT coalesce(max(version), 0) + 1 AS next_v
            FROM skills
            WHERE workspace_id = %s AND name = %s
            """,
            (str(src.workspace_id), src.name),
        )
        next_v = int(cur.fetchone()["next_v"])
        cur.execute(
            """
            INSERT INTO skills
              (workspace_id, name, description, version, system_prompt,
               allowed_tools, default_collections, starter_examples,
               visibility, budget_per_call_usd, tags, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                str(target.workspace_id), target.name,
                target.description, next_v,
                target.system_prompt,
                target.allowed_tools, target.default_collections,
                target.starter_examples,
                target.visibility, target.budget_per_call_usd,
                target.tags, target.created_by,
            ),
        )
        new_id = cur.fetchone()["id"]
        conn.commit()
        return new_id


def list_versions(
    *, skill_id: UUID, tenant_id: UUID,
) -> list[SkillRow]:
    """给定一个 skill_id, 返回同 workspace+name 的所有历史版本 (含本身), version DESC."""
    cur_skill = get(skill_id=skill_id, tenant_id=tenant_id)
    if cur_skill is None:
        return []
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.* FROM skills s
            JOIN workspaces w ON w.id = s.workspace_id
            WHERE s.workspace_id = %s
              AND s.name = %s
              AND w.tenant_id = %s
              AND s.deleted_at IS NULL
              AND w.deleted_at IS NULL
            ORDER BY s.version DESC
            """,
            (str(cur_skill.workspace_id), cur_skill.name, str(tenant_id)),
        )
        return [_row(r) for r in cur.fetchall()]


def new_version(
    *, skill_id: UUID, tenant_id: UUID, **overrides: Any,
) -> UUID | None:
    """基于现有 skill 发新版 (不改原版本, 复制 + bump version)."""
    src = get(skill_id=skill_id, tenant_id=tenant_id)
    if src is None:
        return None
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO skills
              (workspace_id, name, description, version, system_prompt,
               allowed_tools, default_collections, starter_examples,
               visibility, budget_per_call_usd, tags, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                str(src.workspace_id), src.name,
                overrides.get("description", src.description),
                src.version + 1,
                overrides.get("system_prompt", src.system_prompt),
                overrides.get("allowed_tools", src.allowed_tools),
                overrides.get("default_collections", src.default_collections),
                overrides.get("starter_examples", src.starter_examples),
                overrides.get("visibility", src.visibility),
                overrides.get("budget_per_call_usd", src.budget_per_call_usd),
                overrides.get("tags", src.tags),
                src.created_by,
            ),
        )
        new_id = cur.fetchone()["id"]
        conn.commit()
        return new_id
