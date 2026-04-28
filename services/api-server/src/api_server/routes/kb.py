"""KB endpoints (Day 6 P0 #4).

POST   /v1/kb/upload?collection=...  上传文件 -> 创建 doc + job, 后台 ingest
GET    /v1/kb/docs                   列 docs (按 collection / status filter)
GET    /v1/kb/docs/{id}              doc 详情 (含 chunk_count)
DELETE /v1/kb/docs/{id}              软删 doc + chunks
GET    /v1/kb/jobs/{id}              job 状态 (轮询用; SSE 留 Day 8)
POST   /v1/kb/test-search            不进 chat, 直接看检索 (调试用)
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile,
)
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

import psycopg
from psycopg.rows import dict_row

from fastapi import Request

from api_server.acl import Principal
from api_server.auth import verify_api_key
from api_server.db import audit as audit_db
from api_server.db import kb as kb_db
from api_server.db.api_keys import _db_url
from api_server.ingest_worker import run_ingest_job, save_upload_to_tmp


def _client_meta(req: Request | None) -> tuple[str | None, str | None]:
    if not req:
        return None, None
    ip = (
        req.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (req.client.host if req.client else None)
    )
    return ip, req.headers.get("user-agent")

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_UPLOAD_BYTES = 50 * 1024 * 1024   # 50 MB; 大于走 multipart 分片 (后续)


class DocOut(BaseModel):
    id: UUID
    source_uri: str
    source_type: str
    title: str | None
    collection: str
    status: str
    current_version: int
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class DocList(BaseModel):
    items: list[DocOut]
    next_cursor: datetime | None = None


class JobOut(BaseModel):
    id: UUID
    doc_id: UUID | None
    collection: str
    source_uri: str
    status: str                       # pending / parsing / done / failed
    progress: int                     # 0-100
    stage: str | None = None
    error: str | None = None
    chunks_created: int = 0
    chunks_reused: int = 0
    created_at: datetime
    finished_at: datetime | None = None


class UploadResponse(BaseModel):
    job_id: UUID
    status: str
    collection: str


class TestSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    k: int = Field(default=5, ge=1, le=10)
    collection: str = Field(default="default")


class TestSearchHit(BaseModel):
    chunk_id: UUID
    doc_id: UUID
    title: str | None = None
    source_uri: str | None = None
    score: float
    snippet: str


def _doc_to_out(d: kb_db.DocRow) -> DocOut:
    return DocOut(
        id=d.id, source_uri=d.source_uri, source_type=d.source_type,
        title=d.title, collection=d.collection, status=d.status,
        current_version=d.current_version, chunk_count=d.chunk_count,
        created_at=d.created_at, updated_at=d.updated_at,
    )


def _job_to_out(j: kb_db.IngestJobRow) -> JobOut:
    return JobOut(
        id=j.id, doc_id=j.doc_id, collection=j.collection,
        source_uri=j.source_uri, status=j.status, progress=j.progress,
        stage=j.stage, error=j.error,
        chunks_created=j.chunks_created, chunks_reused=j.chunks_reused,
        created_at=j.created_at, finished_at=j.finished_at,
    )


@router.post("/kb/upload", response_model=UploadResponse)
async def upload_doc(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    collection: str | None = Form(default=None),
    workspace_id: str | None = Form(default=None),
    principal: Principal = Depends(verify_api_key),
) -> UploadResponse:
    if not file.filename:
        raise HTTPException(400, "filename missing")
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"file > {MAX_UPLOAD_BYTES} bytes")
    if not data:
        raise HTTPException(400, "file empty")

    # 解析 collection: 优先级 explicit collection > workspace.default_collection > "default"
    final_collection = collection
    if not final_collection and workspace_id:
        from api_server.db import workspaces as ws_db
        from uuid import UUID as _UUID
        try:
            wid = _UUID(workspace_id)
        except ValueError as e:
            raise HTTPException(400, "invalid workspace_id") from e
        ws = await asyncio.to_thread(
            ws_db.get, workspace_id=wid, tenant_id=principal.tenant_id,
        )
        if ws is None:
            raise HTTPException(404, "workspace not found")
        final_collection = ws.default_collection
        # 校验 collection 在 workspace.allowed_collections 内 (兜底)
        if (ws.allowed_collections and final_collection
                not in ws.allowed_collections):
            final_collection = ws.allowed_collections[0]
    if not final_collection:
        final_collection = "default"

    tmp_path = save_upload_to_tmp(file.filename, data)
    job_id = await asyncio.to_thread(
        kb_db.create_ingest_job,
        tenant_id=principal.tenant_id, actor_id=principal.actor_id,
        source_uri=str(tmp_path), source_type="file",
        collection=final_collection, bytes_total=len(data),
    )
    background_tasks.add_task(
        run_ingest_job,
        job_id=job_id, tenant_id=principal.tenant_id,
        principals=principal.principals, file_path=tmp_path,
        collection=final_collection,
    )
    return UploadResponse(
        job_id=job_id, status="pending", collection=final_collection,
    )


@router.get("/kb/collections")
async def list_collections(
    workspace_id: str | None = Query(default=None),
    principal: Principal = Depends(verify_api_key),
) -> dict[str, Any]:
    """列出本 tenant 已使用的 collection (从 rag_docs distinct).

    若给 workspace_id, 返回 workspace.allowed_collections 作为白名单 + 实际已用.
    """
    def _do_list() -> list[str]:
        with psycopg.connect(_db_url(), row_factory=dict_row) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT collection FROM rag_docs
                WHERE tenant_id = %s AND deleted_at IS NULL
                ORDER BY collection ASC
                """,
                (str(principal.tenant_id),),
            )
            return [r["collection"] for r in cur.fetchall()]

    used = await asyncio.to_thread(_do_list)
    allowed: list[str] = []
    default = "default"
    if workspace_id:
        from api_server.db import workspaces as ws_db
        from uuid import UUID as _UUID
        try:
            wid = _UUID(workspace_id)
        except ValueError:
            wid = None
        if wid:
            ws = await asyncio.to_thread(
                ws_db.get, workspace_id=wid, tenant_id=principal.tenant_id,
            )
            if ws:
                allowed = list(ws.allowed_collections)
                default = ws.default_collection
    return {"used": used, "allowed": allowed, "default": default}


@router.get("/kb/docs", response_model=DocList)
async def list_docs(
    collection: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    before: datetime | None = None,
    principal: Principal = Depends(verify_api_key),
) -> DocList:
    rows, next_cursor = await asyncio.to_thread(
        kb_db.list_docs,
        tenant_id=principal.tenant_id,
        collection=collection, status=status,
        limit=limit, before=before,
    )
    return DocList(
        items=[_doc_to_out(r) for r in rows],
        next_cursor=next_cursor,
    )


@router.get("/kb/docs/{doc_id}", response_model=DocOut)
async def get_doc(
    doc_id: UUID,
    principal: Principal = Depends(verify_api_key),
) -> DocOut:
    row = await asyncio.to_thread(
        kb_db.get_doc, doc_id=doc_id, tenant_id=principal.tenant_id,
    )
    if row is None:
        raise HTTPException(404, "doc not found")
    return _doc_to_out(row)


class ChunkOut(BaseModel):
    id: UUID
    chunk_seq: int
    doc_version: int
    content: str
    page: int | None = None
    char_offset_start: int | None = None
    char_offset_end: int | None = None
    parent_id: UUID | None = None


class ChunkList(BaseModel):
    doc_id: UUID
    items: list[ChunkOut]
    truncated: bool


@router.get("/kb/docs/{doc_id}/chunks", response_model=ChunkList)
async def list_chunks(
    doc_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    principal: Principal = Depends(verify_api_key),
) -> ChunkList:
    """看 doc 的全部 chunk 文本 (调试 / 审 KB 质量)."""
    rows = await asyncio.to_thread(
        kb_db.list_chunks,
        doc_id=doc_id, tenant_id=principal.tenant_id, limit=limit + 1,
    )
    truncated = len(rows) > limit
    items = [
        ChunkOut(
            id=r.id, chunk_seq=r.chunk_seq, doc_version=r.doc_version,
            content=r.content, page=r.page,
            char_offset_start=r.char_offset_start,
            char_offset_end=r.char_offset_end,
            parent_id=r.parent_id,
        )
        for r in rows[:limit]
    ]
    return ChunkList(doc_id=doc_id, items=items, truncated=truncated)


@router.delete("/kb/docs/{doc_id}")
async def delete_doc(
    doc_id: UUID,
    request: Request,
    principal: Principal = Depends(verify_api_key),
) -> dict[str, bool]:
    # 取一下 doc 信息便于 audit detail
    doc_row = await asyncio.to_thread(
        kb_db.get_doc, doc_id=doc_id, tenant_id=principal.tenant_id,
    )
    ok = await asyncio.to_thread(
        kb_db.delete_doc, doc_id=doc_id, tenant_id=principal.tenant_id,
    )
    if not ok:
        raise HTTPException(404, "doc not found or already deleted")
    ip, ua = _client_meta(request)
    audit_db.insert(
        tenant_id=principal.tenant_id, actor_id=principal.actor_id,
        action="kb_doc.delete",
        resource_type="kb_doc", resource_id=str(doc_id),
        detail={
            "title": doc_row.title if doc_row else None,
            "source_uri": doc_row.source_uri if doc_row else None,
            "collection": doc_row.collection if doc_row else None,
        },
        ip=ip, user_agent=ua,
    )
    return {"deleted": True}


@router.get("/kb/jobs/{job_id}", response_model=JobOut)
async def get_job(
    job_id: UUID,
    principal: Principal = Depends(verify_api_key),
) -> JobOut:
    row = await asyncio.to_thread(
        kb_db.get_job, job_id=job_id, tenant_id=principal.tenant_id,
    )
    if row is None:
        raise HTTPException(404, "job not found")
    return _job_to_out(row)


@router.get("/kb/jobs/{job_id}/stream")
async def stream_job(
    job_id: UUID,
    principal: Principal = Depends(verify_api_key),
):
    """SSE 流: 推送 ingest job 的 progress 变化, 直到 done/failed.

    协议:
        event: progress  data: <JobOut JSON>     # 状态/progress/stage 任一变化
        event: end       data: {}                # done / failed
        event: timeout   data: {}                # 5 分钟内未结束

    替代前端轮询; 同源 EventSource API 直接订阅.
    """
    async def gen():
        last_sig = None
        for _ in range(300):  # 5 分钟 = 300 × 1s
            row = await asyncio.to_thread(
                kb_db.get_job, job_id=job_id, tenant_id=principal.tenant_id,
            )
            if row is None:
                yield {"event": "error", "data": json.dumps({"error": "not found"})}
                return
            sig = (row.status, row.progress, row.stage, row.error)
            if sig != last_sig:
                last_sig = sig
                payload = _job_to_out(row).model_dump(mode="json")
                yield {"event": "progress", "data": json.dumps(payload)}
            if row.status in ("done", "failed"):
                yield {"event": "end", "data": "{}"}
                return
            await asyncio.sleep(1.0)
        yield {"event": "timeout", "data": "{}"}

    return EventSourceResponse(gen())


@router.post("/kb/test-search")
async def test_search(
    payload: TestSearchRequest,
    principal: Principal = Depends(verify_api_key),
) -> dict[str, Any]:
    """绕开 chat 直接看检索结果 (调试 / KB 质量评估)."""
    from rag_core.config import Settings, make_embedder, make_reranker
    from rag_core.retrieval.hybrid import HybridRetriever
    from rag_core.storage.pgvector_store import PgVectorStore

    def _do_search() -> tuple[list[TestSearchHit], int, int, bool]:
        s = Settings.from_env()
        store = PgVectorStore(s.db_url)
        embedder = make_embedder(s)
        reranker = make_reranker(s)
        hr = HybridRetriever(
            store, embedder, reranker=reranker,
            rrf_k=s.rrf_k, candidate_pool=s.candidate_pool,
            refusal_threshold=s.refusal_threshold,
        )
        # collection 通过 metadata filter 透传
        filters = {"collection": payload.collection} if payload.collection else None
        result = hr.search(
            query=payload.query, tenant_id=principal.tenant_id,
            principals=principal.principals, k=payload.k, filters=filters,
        )
        hits = [
            TestSearchHit(
                chunk_id=h.chunk.id,  # type: ignore[arg-type]
                doc_id=h.chunk.doc_id,
                title=h.title, source_uri=h.source_uri,
                score=h.score,
                snippet=(h.parent_content or h.chunk.content)[:300],
            )
            for h in result.hits if h.chunk.id
        ]
        return hits, result.n_dense, result.n_bm25, result.refused

    hits, n_dense, n_bm25, refused = await asyncio.to_thread(_do_search)
    return {
        "hits": [h.model_dump() for h in hits],
        "n_dense": n_dense, "n_bm25": n_bm25, "refused": refused,
    }
