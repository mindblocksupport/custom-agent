"""chat_sessions / chat_messages DB 层 (Day 4 P0 #7).

设计:
- 同步 psycopg (与现有代码一致); 路由层用 asyncio.to_thread 包
- 所有读写都强制 tenant_id 过滤 (防越权)
- session 软删 (deleted_at)
- message append 用 advisory lock 计算 sequence_no, 避免双写竞争
"""

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
class SessionRow:
    id: UUID
    tenant_id: UUID
    actor_id: str
    title: str
    message_count: int
    total_cost_usd: float
    created_at: datetime
    updated_at: datetime
    workspace_id: UUID | None = None
    skill_id: UUID | None = None
    tags: list[str] | None = None


@dataclass
class MessageRow:
    id: UUID
    session_id: UUID
    sequence_no: int
    role: str
    content: str
    tool_calls: list[dict] | None
    tool_call_id: str | None
    tool_name: str | None
    trace_id: str | None
    cost_usd: float
    input_tokens: int
    output_tokens: int
    model: str | None
    metadata: dict
    created_at: datetime


def _conn():
    return psycopg.connect(_db_url(), row_factory=dict_row)


# ---------- session ----------

def create_session(
    *, tenant_id: UUID, actor_id: str, title: str = "",
    workspace_id: UUID | None = None,
    skill_id: UUID | None = None,
) -> UUID:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO chat_sessions
              (tenant_id, actor_id, title, workspace_id, skill_id)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                str(tenant_id), actor_id, title,
                str(workspace_id) if workspace_id else None,
                str(skill_id) if skill_id else None,
            ),
        )
        new_id = cur.fetchone()["id"]
        conn.commit()
        return new_id


def list_sessions(
    *, tenant_id: UUID, actor_id: str,
    workspace_id: UUID | None = None,
    tag: str | None = None,
    limit: int = 20, before: datetime | None = None,
) -> tuple[list[SessionRow], datetime | None]:
    """返回 (rows, next_cursor=最旧一条的 updated_at, 没下一页则 None).

    workspace_id != None: 仅本 workspace
    tag != None: 仅含该 tag 的会话 (gin 索引加速)
    """
    sql = """
        SELECT id, tenant_id, actor_id, title, message_count, total_cost_usd,
               created_at, updated_at, tags
        FROM chat_sessions
        WHERE tenant_id = %s AND actor_id = %s AND deleted_at IS NULL
    """
    params: list[Any] = [str(tenant_id), actor_id]
    if workspace_id is not None:
        sql += " AND workspace_id = %s"
        params.append(str(workspace_id))
    if tag:
        sql += " AND %s = ANY(tags)"
        params.append(tag)
    if before is not None:
        sql += " AND updated_at < %s"
        params.append(before)
    sql += " ORDER BY updated_at DESC LIMIT %s"
    params.append(limit + 1)
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = [SessionRow(**r) for r in cur.fetchall()]
    if len(rows) > limit:
        next_cursor = rows[limit - 1].updated_at
        rows = rows[:limit]
        return rows, next_cursor
    return rows, None


def get_session(
    *, session_id: UUID, tenant_id: UUID,
) -> SessionRow | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, tenant_id, actor_id, title, message_count, total_cost_usd,
                   created_at, updated_at, workspace_id, skill_id, tags
            FROM chat_sessions
            WHERE id = %s AND tenant_id = %s AND deleted_at IS NULL
            """,
            (str(session_id), str(tenant_id)),
        )
        r = cur.fetchone()
        return SessionRow(**r) if r else None


def update_session_tags(
    *, session_id: UUID, tenant_id: UUID, tags: list[str],
) -> bool:
    # 去重 + 标准化 (lower, 去 whitespace)
    norm = sorted({t.strip().lower() for t in tags if t.strip()})
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE chat_sessions
            SET tags = %s::text[], updated_at = now()
            WHERE id = %s AND tenant_id = %s AND deleted_at IS NULL
            """,
            (norm, str(session_id), str(tenant_id)),
        )
        ok = cur.rowcount > 0
        conn.commit()
        return ok


def list_distinct_tags(*, tenant_id: UUID, actor_id: str) -> list[str]:
    """全部唯一 tag (用于 sidebar 自动补全 / 筛选 chip)."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT unnest(tags) AS t
            FROM chat_sessions
            WHERE tenant_id = %s AND actor_id = %s AND deleted_at IS NULL
              AND array_length(tags, 1) > 0
            ORDER BY t ASC
            LIMIT 100
            """,
            (str(tenant_id), actor_id),
        )
        return [r["t"] for r in cur.fetchall()]


def delete_session(*, session_id: UUID, tenant_id: UUID) -> bool:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE chat_sessions
            SET deleted_at = now()
            WHERE id = %s AND tenant_id = %s AND deleted_at IS NULL
            """,
            (str(session_id), str(tenant_id)),
        )
        ok = cur.rowcount > 0
        conn.commit()
        return ok


def search_sessions(
    *, tenant_id: UUID, actor_id: str, q: str,
    workspace_id: UUID | None = None, limit: int = 30,
) -> list[tuple[SessionRow, str | None]]:
    """全文搜 (会话标题 + 消息内容). 返回 (session, snippet)."""
    sql = """
        WITH hits AS (
          SELECT s.id AS sid,
                 s.title,
                 s.message_count,
                 s.total_cost_usd,
                 s.created_at,
                 s.updated_at,
                 s.tenant_id,
                 s.actor_id,
                 (
                   CASE
                     WHEN s.title ILIKE %s THEN s.title
                     ELSE (
                       SELECT m.content FROM chat_messages m
                       WHERE m.session_id = s.id
                         AND m.content ILIKE %s
                       ORDER BY m.sequence_no DESC
                       LIMIT 1
                     )
                   END
                 ) AS snippet
          FROM chat_sessions s
          WHERE s.tenant_id = %s
            AND s.actor_id = %s
            AND s.deleted_at IS NULL
            AND (
              s.title ILIKE %s
              OR EXISTS (
                SELECT 1 FROM chat_messages m
                WHERE m.session_id = s.id AND m.content ILIKE %s
              )
            )
    """
    params: list[Any] = [
        f"%{q}%", f"%{q}%",
        str(tenant_id), actor_id,
        f"%{q}%", f"%{q}%",
    ]
    if workspace_id is not None:
        sql += " AND s.workspace_id = %s"
        params.append(str(workspace_id))
    sql += """
        )
        SELECT * FROM hits
        ORDER BY updated_at DESC
        LIMIT %s
    """
    params.append(limit)
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        out: list[tuple[SessionRow, str | None]] = []
        for r in cur.fetchall():
            row = SessionRow(
                id=r["sid"], tenant_id=r["tenant_id"],
                actor_id=r["actor_id"], title=r["title"],
                message_count=int(r["message_count"]),
                total_cost_usd=float(r["total_cost_usd"]),
                created_at=r["created_at"], updated_at=r["updated_at"],
            )
            sn = r["snippet"]
            if sn and len(sn) > 240:
                # 围绕命中片段返回上下文
                idx = sn.lower().find(q.lower())
                if idx >= 0:
                    start = max(0, idx - 60)
                    sn = ("..." if start > 0 else "") + sn[start:start + 240]
                else:
                    sn = sn[:240]
            out.append((row, sn))
        return out


def update_session_title(
    *, session_id: UUID, tenant_id: UUID, title: str,
) -> bool:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE chat_sessions
            SET title = %s, updated_at = now()
            WHERE id = %s AND tenant_id = %s AND deleted_at IS NULL
            """,
            (title, str(session_id), str(tenant_id)),
        )
        ok = cur.rowcount > 0
        conn.commit()
        return ok


# ---------- messages ----------

def append_message(
    *,
    session_id: UUID,
    tenant_id: UUID,
    role: str,
    content: str = "",
    tool_calls: list[dict] | None = None,
    tool_call_id: str | None = None,
    tool_name: str | None = None,
    trace_id: str | None = None,
    cost_usd: float = 0.0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    model: str | None = None,
    metadata: dict | None = None,
) -> int:
    """append 一条 message, 返回 sequence_no. 同时 bump session.message_count + cost.

    用 (session_id, sequence_no) UNIQUE 防双写; 用 advisory lock 算下一个 seq_no.
    """
    with _conn() as conn, conn.cursor() as cur:
        # advisory lock: hash session_id 到 bigint (一次 pg_advisory_xact_lock)
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (str(session_id),))
        # 校验 session 存在 + 同 tenant
        cur.execute(
            """
            SELECT message_count FROM chat_sessions
            WHERE id = %s AND tenant_id = %s AND deleted_at IS NULL
            FOR UPDATE
            """,
            (str(session_id), str(tenant_id)),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"session {session_id} not found or deleted")
        next_seq = int(row["message_count"]) + 1

        cur.execute(
            """
            INSERT INTO chat_messages
              (session_id, sequence_no, role, content, tool_calls, tool_call_id,
               tool_name, trace_id, cost_usd, input_tokens, output_tokens, model, metadata)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                str(session_id), next_seq, role, content,
                json.dumps(tool_calls) if tool_calls else None,
                tool_call_id, tool_name, trace_id,
                cost_usd, input_tokens, output_tokens, model,
                json.dumps(metadata or {}),
            ),
        )
        cur.execute(
            """
            UPDATE chat_sessions
            SET message_count = message_count + 1,
                total_cost_usd = total_cost_usd + %s,
                updated_at = now()
            WHERE id = %s
            """,
            (cost_usd, str(session_id)),
        )
        conn.commit()
        return next_seq


def get_messages(
    *,
    session_id: UUID,
    tenant_id: UUID,
    after_seq: int | None = None,
    limit: int = 100,
) -> list[MessageRow]:
    """按 sequence_no 升序返回 messages. tenant_id 强制过滤 (JOIN 检查)."""
    sql = """
        SELECT m.id, m.session_id, m.sequence_no, m.role, m.content,
               m.tool_calls, m.tool_call_id, m.tool_name, m.trace_id,
               m.cost_usd, m.input_tokens, m.output_tokens, m.model, m.metadata,
               m.created_at
        FROM chat_messages m
        JOIN chat_sessions s ON s.id = m.session_id
        WHERE m.session_id = %s
          AND s.tenant_id = %s
          AND s.deleted_at IS NULL
    """
    params: list[Any] = [str(session_id), str(tenant_id)]
    if after_seq is not None:
        sql += " AND m.sequence_no > %s"
        params.append(after_seq)
    sql += " ORDER BY m.sequence_no ASC LIMIT %s"
    params.append(limit)
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return [
            MessageRow(
                id=r["id"], session_id=r["session_id"], sequence_no=r["sequence_no"],
                role=r["role"], content=r["content"],
                tool_calls=r["tool_calls"], tool_call_id=r["tool_call_id"],
                tool_name=r["tool_name"], trace_id=r["trace_id"],
                cost_usd=float(r["cost_usd"]), input_tokens=int(r["input_tokens"]),
                output_tokens=int(r["output_tokens"]), model=r["model"],
                metadata=r["metadata"] or {}, created_at=r["created_at"],
            )
            for r in cur.fetchall()
        ]
