"""api_keys 表读写 (Day 1).

存的是 sha256(raw_key), 不是明文; 验证流程:
    raw_key (Bearer header) → sha256 → 查表 → Principal
"""

from __future__ import annotations

import hashlib
import logging
import os
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
