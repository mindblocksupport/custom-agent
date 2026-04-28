"""KB DB 层: rag_docs 列表/删除 + ingest_jobs 状态管理 (Day 6 P0 #4).

读 rag_docs / rag_chunks 跟现有 rag-core 同表; jobs 表是 005 迁移加的.
所有写都强制 tenant_id 过滤.
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
class DocRow:
    id: UUID
    tenant_id: UUID
    source_uri: str
    source_type: str
    title: str | None
    collection: str
    status: str
    current_version: int
    chunk_count: int
    created_at: datetime
    updated_at: datetime


@dataclass
class IngestJobRow:
    id: UUID
    tenant_id: UUID
    actor_id: str
    doc_id: UUID | None
    collection: str
    source_uri: str
    source_type: str
    status: str
    progress: int
    stage: str | None
    error: str | None
    chunks_created: int
    chunks_reused: int
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None


def _conn():
    return psycopg.connect(_db_url(), row_factory=dict_row)


# ---------- docs ----------

def list_docs(
    *, tenant_id: UUID, collection: str | None = None,
    status: str | None = None, limit: int = 50,
    before: datetime | None = None,
) -> tuple[list[DocRow], datetime | None]:
    sql = """
        SELECT d.id, d.tenant_id, d.source_uri, d.source_type, d.title,
               d.collection, d.status, d.current_version,
               d.created_at, d.updated_at,
               (SELECT COUNT(*) FROM rag_chunks c
                WHERE c.doc_id = d.id AND NOT c.is_deleted) AS chunk_count
        FROM rag_docs d
        WHERE d.tenant_id = %s AND d.deleted_at IS NULL
    """
    params: list[Any] = [str(tenant_id)]
    if collection:
        sql += " AND d.collection = %s"
        params.append(collection)
    if status:
        sql += " AND d.status = %s"
        params.append(status)
    if before is not None:
        sql += " AND d.updated_at < %s"
        params.append(before)
    sql += " ORDER BY d.updated_at DESC LIMIT %s"
    params.append(limit + 1)
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = [DocRow(**r) for r in cur.fetchall()]
    if len(rows) > limit:
        next_cursor = rows[limit - 1].updated_at
        return rows[:limit], next_cursor
    return rows, None


def get_doc(*, doc_id: UUID, tenant_id: UUID) -> DocRow | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, d.tenant_id, d.source_uri, d.source_type, d.title,
                   d.collection, d.status, d.current_version,
                   d.created_at, d.updated_at,
                   (SELECT COUNT(*) FROM rag_chunks c
                    WHERE c.doc_id = d.id AND NOT c.is_deleted) AS chunk_count
            FROM rag_docs d
            WHERE d.id = %s AND d.tenant_id = %s AND d.deleted_at IS NULL
            """,
            (str(doc_id), str(tenant_id)),
        )
        r = cur.fetchone()
        return DocRow(**r) if r else None


@dataclass
class ChunkRow:
    id: UUID
    chunk_seq: int
    doc_version: int
    content: str
    page: int | None
    char_offset_start: int | None
    char_offset_end: int | None
    parent_id: UUID | None


def list_chunks(
    *, doc_id: UUID, tenant_id: UUID, limit: int = 200,
) -> list[ChunkRow]:
    """列 doc 的全部 chunk (默认按 chunk_seq 升序). tenant_id 强制过滤."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, chunk_seq, doc_version, content,
                   page, char_offset_start, char_offset_end, parent_id
            FROM rag_chunks
            WHERE doc_id = %s AND tenant_id = %s AND NOT is_deleted
            ORDER BY chunk_seq ASC
            LIMIT %s
            """,
            (str(doc_id), str(tenant_id), limit),
        )
        return [
            ChunkRow(
                id=r["id"], chunk_seq=int(r["chunk_seq"]),
                doc_version=int(r["doc_version"]),
                content=r["content"], page=r["page"],
                char_offset_start=r["char_offset_start"],
                char_offset_end=r["char_offset_end"],
                parent_id=r["parent_id"],
            )
            for r in cur.fetchall()
        ]


def delete_doc(*, doc_id: UUID, tenant_id: UUID) -> bool:
    """软删 doc + chunks (HNSW 索引会自动跳过 is_deleted=True)."""
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE rag_docs SET deleted_at = now() "
            "WHERE id = %s AND tenant_id = %s AND deleted_at IS NULL",
            (str(doc_id), str(tenant_id)),
        )
        ok = cur.rowcount > 0
        cur.execute(
            "UPDATE rag_chunks SET is_deleted = TRUE "
            "WHERE doc_id = %s AND tenant_id = %s",
            (str(doc_id), str(tenant_id)),
        )
        conn.commit()
        return ok


# ---------- jobs ----------

def create_ingest_job(
    *, tenant_id: UUID, actor_id: str, source_uri: str,
    source_type: str = "file", collection: str = "default",
    bytes_total: int | None = None,
) -> UUID:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ingest_jobs
              (tenant_id, actor_id, source_uri, source_type,
               collection, bytes_total)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (str(tenant_id), actor_id, source_uri, source_type,
             collection, bytes_total),
        )
        new_id = cur.fetchone()["id"]
        conn.commit()
        return new_id


def update_job(
    *, job_id: UUID,
    status: str | None = None,
    progress: int | None = None,
    stage: str | None = None,
    error: str | None = None,
    doc_id: UUID | None = None,
    chunks_created: int | None = None,
    chunks_reused: int | None = None,
    finished: bool = False,
) -> None:
    """部分更新. job 不强制 tenant_id (由 worker 内部更新, tenant 已隐含)."""
    sets: list[str] = []
    params: list[Any] = []
    if status is not None: sets.append("status = %s"); params.append(status)
    if progress is not None: sets.append("progress = %s"); params.append(progress)
    if stage is not None: sets.append("stage = %s"); params.append(stage)
    if error is not None: sets.append("error = %s"); params.append(error)
    if doc_id is not None: sets.append("doc_id = %s"); params.append(str(doc_id))
    if chunks_created is not None:
        sets.append("chunks_created = %s"); params.append(chunks_created)
    if chunks_reused is not None:
        sets.append("chunks_reused = %s"); params.append(chunks_reused)
    if finished:
        sets.append("finished_at = now()")
    sets.append("updated_at = now()")
    if not sets:
        return
    params.append(str(job_id))
    sql = f"UPDATE ingest_jobs SET {', '.join(sets)} WHERE id = %s"
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        conn.commit()


def get_job(*, job_id: UUID, tenant_id: UUID) -> IngestJobRow | None:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, tenant_id, actor_id, doc_id, collection, source_uri,
                   source_type, status, progress, stage, error,
                   chunks_created, chunks_reused, created_at, updated_at, finished_at
            FROM ingest_jobs
            WHERE id = %s AND tenant_id = %s
            """,
            (str(job_id), str(tenant_id)),
        )
        r = cur.fetchone()
        return IngestJobRow(**r) if r else None
