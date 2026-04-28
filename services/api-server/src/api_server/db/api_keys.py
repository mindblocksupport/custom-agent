"""api_keys 表读写 (Day 1).

存的是 sha256(raw_key), 不是明文; 验证流程:
    raw_key (Bearer header) → sha256 → 查表 → Principal

CRUD (Day n): list/create/revoke 给 console UI 用.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from api_server.acl import Principal

logger = logging.getLogger(__name__)

DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_ACTOR_ID = "dev"
DEFAULT_PRINCIPALS = ["user:dev", "group:public"]


def _db_url() -> str:
    return os.environ.get(
        "RAG_DB_URL",
        "postgresql://agent:agent@localhost:5432/agent",
    )


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def lookup_principal(raw_key: str) -> Principal | None:
    """raw key → Principal. 找不到 (含已撤销) 返回 None."""
    if not raw_key:
        return None
    key_hash = hash_api_key(raw_key)
    with psycopg.connect(_db_url(), row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT tenant_id, actor_id, principals
            FROM api_keys
            WHERE key_hash = %s AND revoked_at IS NULL
            """,
            (key_hash,),
        )
        row = cur.fetchone()
        if not row:
            return None
        cur.execute(
            "UPDATE api_keys SET last_used_at = now() WHERE key_hash = %s",
            (key_hash,),
        )
        conn.commit()
        return Principal(
            tenant_id=UUID(str(row["tenant_id"])),
            actor_id=row["actor_id"],
            principals=list(row["principals"] or []),
        )


@dataclass
class ApiKeyRow:
    key_hash: str
    tenant_id: UUID
    actor_id: str
    principals: list[str]
    label: str | None
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
    role: str = "admin"          # admin / editor / viewer


def _row(r: dict) -> ApiKeyRow:
    return ApiKeyRow(
        key_hash=r["key_hash"], tenant_id=UUID(str(r["tenant_id"])),
        actor_id=r["actor_id"],
        principals=list(r["principals"] or []),
        label=r["label"],
        role=r.get("role") or "admin",
        created_at=r["created_at"], last_used_at=r["last_used_at"],
        revoked_at=r["revoked_at"],
    )


def list_keys(*, tenant_id: UUID, include_revoked: bool = False) -> list[ApiKeyRow]:
    sql = """
        SELECT key_hash, tenant_id, actor_id, principals, label, role,
               created_at, last_used_at, revoked_at
        FROM api_keys
        WHERE tenant_id = %s
    """
    params: list = [str(tenant_id)]
    if not include_revoked:
        sql += " AND revoked_at IS NULL"
    sql += " ORDER BY created_at DESC"
    with psycopg.connect(_db_url(), row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return [_row(r) for r in cur.fetchall()]


def create_key(
    *, tenant_id: UUID, actor_id: str, principals: list[str],
    label: str | None = None, role: str = "admin",
) -> tuple[str, ApiKeyRow]:
    """生成 raw key, 写表, 返回 (raw_key, row). raw_key 仅本次返回, 不再可见."""
    if role not in {"admin", "editor", "viewer"}:
        raise ValueError(f"invalid role: {role}")
    raw = "ck_" + secrets.token_urlsafe(32)
    key_hash = hash_api_key(raw)
    with psycopg.connect(_db_url(), row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO api_keys
              (key_hash, tenant_id, actor_id, principals, label, role)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING key_hash, tenant_id, actor_id, principals, label, role,
                      created_at, last_used_at, revoked_at
            """,
            (key_hash, str(tenant_id), actor_id, principals, label, role),
        )
        out = _row(cur.fetchone())
        conn.commit()
        return raw, out


def revoke_key(*, key_hash: str, tenant_id: UUID) -> bool:
    with psycopg.connect(_db_url()) as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE api_keys SET revoked_at = now()
            WHERE key_hash = %s AND tenant_id = %s AND revoked_at IS NULL
            """,
            (key_hash, str(tenant_id)),
        )
        ok = cur.rowcount > 0
        conn.commit()
        return ok


def update_label(
    *, key_hash: str, tenant_id: UUID, label: str,
) -> bool:
    with psycopg.connect(_db_url()) as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE api_keys SET label = %s
            WHERE key_hash = %s AND tenant_id = %s
            """,
            (label, key_hash, str(tenant_id)),
        )
        ok = cur.rowcount > 0
        conn.commit()
        return ok


def update_role(
    *, key_hash: str, tenant_id: UUID, role: str,
) -> bool:
    if role not in {"admin", "editor", "viewer"}:
        raise ValueError(f"invalid role: {role}")
    with psycopg.connect(_db_url()) as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE api_keys SET role = %s
            WHERE key_hash = %s AND tenant_id = %s
            """,
            (role, key_hash, str(tenant_id)),
        )
        ok = cur.rowcount > 0
        conn.commit()
        return ok


def seed_dev_key() -> None:
    """开发模式: 把 RAG_DEV_API_KEY (默认 'dev-key-change-me') 注册成 dev tenant.

    幂等: 已存在则更新 last_used_at; 不存在则插入.
    生产环境 (ENV=prod) 绝不调用此函数.
    """
    raw_key = os.environ.get("RAG_DEV_API_KEY", "dev-key-change-me")
    key_hash = hash_api_key(raw_key)
    try:
        with psycopg.connect(_db_url()) as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO api_keys
                  (key_hash, tenant_id, actor_id, principals, label)
                VALUES (%s, %s, %s, %s, 'dev-default-key')
                ON CONFLICT (key_hash) DO NOTHING
                """,
                (
                    key_hash, str(DEFAULT_TENANT_ID),
                    DEFAULT_ACTOR_ID, DEFAULT_PRINCIPALS,
                ),
            )
            conn.commit()
            if cur.rowcount > 0:
                logger.info("seeded dev api key (key_hash=%s...)", key_hash[:8])
    except psycopg.errors.UndefinedTable:
        logger.warning(
            "api_keys table missing — run infra/migrations/003_api_keys.sql first"
        )
    except Exception as e:
        logger.warning("seed_dev_key failed: %s", e)
