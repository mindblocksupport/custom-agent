"""轻量后台 cron — 不引入额外 scheduler 依赖.

支持任务: 审计日志自动 retention 清理 (每 N 小时一次, 删 retain_days 前的)
"""

from __future__ import annotations

import asyncio
import logging
import os

import psycopg
from psycopg.rows import dict_row

from api_server.db import audit as audit_db
from api_server.db.api_keys import _db_url

logger = logging.getLogger(__name__)


def _retain_days() -> int:
    try:
        return max(1, int(os.environ.get("AUDIT_RETAIN_DAYS", "365")))
    except ValueError:
        return 365


def _interval_seconds() -> int:
    try:
        return max(60, int(os.environ.get("AUDIT_CLEANUP_INTERVAL_SEC", "86400")))  # 默认每 24h
    except ValueError:
        return 86400


def _enabled() -> bool:
    return os.environ.get("AUDIT_AUTO_CLEANUP", "true").lower() in {
        "1", "true", "yes", "on",
    }


async def _cleanup_all_tenants() -> int:
    """对所有 tenant 跑一次清理. 返回总删行数."""
    retain = _retain_days()

    def _list_tenants() -> list[str]:
        with psycopg.connect(_db_url(), row_factory=dict_row) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT tenant_id::text AS tid
                FROM audit_logs
                """,
            )
            return [r["tid"] for r in cur.fetchall()]

    tenants = await asyncio.to_thread(_list_tenants)
    total = 0
    from uuid import UUID as _UUID
    for tid in tenants:
        try:
            tid_uuid = _UUID(tid)
            n = await asyncio.to_thread(
                audit_db.cleanup_older_than,
                tenant_id=tid_uuid, retain_days=retain,
            )
            total += n
            if n > 0:
                logger.info(
                    "audit cron: cleaned %d rows for tenant %s (retain=%d days)",
                    n, tid[:8], retain,
                )
                # 自审: 写一条 cron 触发的清理记录, actor=system
                await asyncio.to_thread(
                    audit_db.insert,
                    tenant_id=tid_uuid, actor_id="system:cron",
                    action="audit.cleanup_auto",
                    resource_type="audit_log", resource_id=None,
                    detail={"retain_days": retain, "deleted": n},
                )
        except Exception as e:
            logger.warning("audit cron failed for tenant %s: %s", tid[:8], e)
    return total


async def run_audit_cleanup_cron() -> None:
    """长跑协程: 每 N 秒触发一次清理. 由 main.py lifespan 拉起."""
    if not _enabled():
        logger.info("audit cron disabled (AUDIT_AUTO_CLEANUP=false)")
        return
    interval = _interval_seconds()
    logger.info(
        "audit cron started (every %ds, retain %d days)",
        interval, _retain_days(),
    )
    # 启动后等 60s 再首跑, 避免和服务启动竞争
    try:
        await asyncio.sleep(60)
    except asyncio.CancelledError:
        return
    while True:
        try:
            n = await _cleanup_all_tenants()
            if n > 0:
                logger.info("audit cron: total cleaned %d rows across tenants", n)
        except asyncio.CancelledError:
            logger.info("audit cron cancelled")
            return
        except Exception as e:
            logger.warning("audit cron iteration failed: %s", e)
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            return
