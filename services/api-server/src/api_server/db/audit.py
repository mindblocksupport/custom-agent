"""audit_logs DB 层.

最小可用接口: insert (一行) + list (分页过滤).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from api_server.db.api_keys import _db_url

logger = logging.getLogger(__name__)


@dataclass
class AuditRow:
    id: int
    tenant_id: UUID
    actor_id: str
    action: str
    resource_type: str | None
    resource_id: str | None
    detail: dict
    ip: str | None
    user_agent: str | None
    created_at: datetime


def insert(
    *, tenant_id: UUID, actor_id: str, action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict[str, Any] | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> int:
    """写一条 audit. 失败不抛异常 (audit 失败不应阻塞业务流), 但 log warning."""
    try:
        with psycopg.connect(_db_url(), row_factory=dict_row) as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_logs
                  (tenant_id, actor_id, action, resource_type, resource_id,
                   detail, ip, user_agent)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                RETURNING id
                """,
                (
                    str(tenant_id), actor_id, action,
                    resource_type, resource_id,
                    json.dumps(detail or {}),
                    ip, user_agent,
                ),
            )
            new_id = int(cur.fetchone()["id"])
            conn.commit()
            return new_id
    except Exception as e:
        logger.warning("audit insert failed: %s", e)
        return -1


def list_recent(
    *, tenant_id: UUID,
    actor_id: str | None = None,
    action_prefix: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 50,
    before_id: int | None = None,
) -> tuple[list[AuditRow], int | None]:
    """返回 (rows, next_cursor=最旧 id, 没下一页则 None). 按 id DESC."""
    sql = """
        SELECT id, tenant_id, actor_id, action, resource_type, resource_id,
               detail, ip, user_agent, created_at
        FROM audit_logs
        WHERE tenant_id = %s
    """
    params: list[Any] = [str(tenant_id)]
    if actor_id:
        sql += " AND actor_id = %s"
        params.append(actor_id)
    if action_prefix:
        sql += " AND action LIKE %s"
        params.append(f"{action_prefix}%")
    if resource_type:
        sql += " AND resource_type = %s"
        params.append(resource_type)
    if resource_id:
        sql += " AND resource_id = %s"
        params.append(resource_id)
    if since is not None:
        sql += " AND created_at >= %s"
        params.append(since)
    if until is not None:
        sql += " AND created_at < %s"
        params.append(until)
    if before_id is not None:
        sql += " AND id < %s"
        params.append(before_id)
    sql += " ORDER BY id DESC LIMIT %s"
    params.append(limit + 1)
    with psycopg.connect(_db_url(), row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = [
            AuditRow(
                id=int(r["id"]), tenant_id=UUID(str(r["tenant_id"])),
                actor_id=r["actor_id"], action=r["action"],
                resource_type=r["resource_type"], resource_id=r["resource_id"],
                detail=r["detail"] or {},
                ip=r["ip"], user_agent=r["user_agent"],
                created_at=r["created_at"],
            )
            for r in cur.fetchall()
        ]
    if len(rows) > limit:
        next_cursor = rows[limit - 1].id
        rows = rows[:limit]
        return rows, next_cursor
    return rows, None


def cleanup_older_than(
    *, tenant_id: UUID, retain_days: int,
) -> int:
    """删本 tenant 的 retain_days 天前 audit. 返回被删行数."""
    if retain_days < 1:
        raise ValueError("retain_days must be >= 1")
    cutoff = datetime.utcnow() - timedelta(days=retain_days)
    with psycopg.connect(_db_url()) as conn, conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM audit_logs
            WHERE tenant_id = %s AND created_at < %s
            """,
            (str(tenant_id), cutoff),
        )
        n = cur.rowcount
        conn.commit()
        return int(n)
