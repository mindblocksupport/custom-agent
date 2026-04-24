"""Ingest worker (Day 6 P0 #4).

MVP: FastAPI BackgroundTasks (in-process asyncio) — 单实例够用; 重启会丢未跑完任务
生产: 切 Arq (Redis 队列) — 多 worker 进程; 失败重试

任务流:
1. 上传文件保存到临时目录
2. 创建 rag_docs (status=pending), 创建 ingest_jobs (status=pending)
3. 后台任务: parse → chunk → embed → upsert; 实时更新 jobs.progress
4. 完成 → status=done; 失败 → status=failed + error
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from uuid import UUID

from rag_core.config import Settings, make_embedder
from rag_core.ingest.pipeline import IngestPipeline, ingest_file
from rag_core.storage.pgvector_store import PgVectorStore

from api_server.db import kb as kb_db

logger = logging.getLogger(__name__)


# 进程级懒加载 (避免 FastAPI 启动慢)
_pipeline: IngestPipeline | None = None


def _get_pipeline() -> IngestPipeline:
    global _pipeline
    if _pipeline is None:
        s = Settings.from_env()
        store = PgVectorStore(s.db_url)
        embedder = make_embedder(s)
        _pipeline = IngestPipeline(store, embedder)
    return _pipeline


async def run_ingest_job(
    *, job_id: UUID, tenant_id: UUID, principals: list[str],
    file_path: Path, collection: str = "default",
    cleanup_file: bool = True,
) -> None:
    """后台任务: parse + ingest + 更新 job 状态."""
    pipeline = _get_pipeline()
    try:
        await asyncio.to_thread(
            kb_db.update_job,
            job_id=job_id, status="parsing", progress=10, stage="parse",
        )
        # parse + ingest 是同步 IO+CPU, 包到线程
        report = await asyncio.to_thread(
            ingest_file,
            pipeline, file_path,
            tenant_id=tenant_id, acl=principals,
            collection=collection,           # v1.5: 写到 rag_docs/chunks.collection
        )
        await asyncio.to_thread(
            kb_db.update_job,
            job_id=job_id, status="done", progress=100, stage="done",
            doc_id=report.doc_id,
            chunks_created=report.chunks_created,
            chunks_reused=report.chunks_reused,
            finished=True,
        )
        logger.info(
            "ingest job %s done: doc=%s, +%d chunks (%d reused)",
            job_id, report.doc_id, report.chunks_created, report.chunks_reused,
        )
    except NotImplementedError as e:
        # 扫描件等 → ScannedPdfNotSupported
        await asyncio.to_thread(
            kb_db.update_job,
            job_id=job_id, status="failed", progress=0, stage="parse",
            error=f"unsupported: {e}", finished=True,
        )
    except Exception as e:
        logger.exception("ingest job %s failed", job_id)
        await asyncio.to_thread(
            kb_db.update_job,
            job_id=job_id, status="failed", progress=0,
            error=f"{type(e).__name__}: {e}", finished=True,
        )
    finally:
        if cleanup_file:
            try:
                if file_path.exists():
                    file_path.unlink()
            except Exception:
                pass


def save_upload_to_tmp(filename: str, data: bytes) -> Path:
    """保存上传到临时目录, 返回路径 (调用方负责清理 / worker 自动清理)."""
    suffix = Path(filename).suffix or ""
    fd, name = tempfile.mkstemp(suffix=suffix, prefix="rag_upload_")
    os.write(fd, data)
    os.close(fd)
    return Path(name)
