"""Feedback endpoint (L37 §8.6 Day 13).

POST /v1/feedback
    {
      "trace_id": "abc123",
      "rating": "thumb_down" | "thumb_up" | "wrong_answer",
      "query": "...",
      "answer": "...",
      "retrieved_chunk_ids": ["uuid1", "uuid2"],
      "comment": "(optional)"
    }

负向反馈 (thumb_down / wrong_answer) 自动写入 rag_eval_badcases 表,
供周会 review 持续改进 RAG.

未来 (Day 14+):
- 接 Langfuse score API (跟 trace 关联)
- LLM-as-judge 算 faithfulness 分数, < 0.5 也自动入库
"""

from __future__ import annotations

import json
import logging
import os
from typing import Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api_server.auth import verify_api_key

logger = logging.getLogger(__name__)
router = APIRouter()

NEGATIVE_RATINGS = {"thumb_down", "wrong_answer", "irrelevant"}


class FeedbackRequest(BaseModel):
    trace_id: str = Field(..., min_length=1, max_length=128)
    rating: Literal["thumb_up", "thumb_down", "wrong_answer", "irrelevant"]
    query: str = Field(..., min_length=1, max_length=2000)
    answer: str = Field(default="", max_length=20000)
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    tenant_id: str | None = Field(default=None, description="UUID; 默认 dev tenant")
    faithfulness_score: float | None = None
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackResponse(BaseModel):
    accepted: bool
    persisted_as_badcase: bool
    id: str | None = None


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    payload: FeedbackRequest,
    api_key: str = Depends(verify_api_key),
) -> FeedbackResponse:
    """收集用户反馈; 负向反馈自动归集到 rag_eval_badcases."""
    # 正向反馈只打 log, 不入 badcases
    is_negative = (
        payload.rating in NEGATIVE_RATINGS
        or (payload.faithfulness_score is not None and payload.faithfulness_score < 0.5)
    )
    logger.info(
        "feedback rating=%s trace_id=%s neg=%s comment=%r",
        payload.rating, payload.trace_id, is_negative,
        (payload.comment or "")[:80],
    )
    if not is_negative:
        return FeedbackResponse(accepted=True, persisted_as_badcase=False)

    db_url = os.environ.get(
        "RAG_DB_URL",
        "postgresql://agent:agent@localhost:5432/agent",
    )
    tenant_id = payload.tenant_id or "00000000-0000-0000-0000-000000000001"
    try:
        with psycopg.connect(db_url) as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rag_eval_badcases
                  (trace_id, tenant_id, query, answer, retrieved_chunk_ids,
                   faithfulness_score, user_feedback)
                VALUES (%s, %s::uuid, %s, %s, %s::uuid[], %s, %s)
                RETURNING id
                """,
                (
                    payload.trace_id, tenant_id,
                    payload.query, payload.answer,
                    payload.retrieved_chunk_ids,
                    payload.faithfulness_score,
                    payload.rating + (f": {payload.comment}" if payload.comment else ""),
                ),
            )
            badcase_id = str(cur.fetchone()[0])
            conn.commit()
        return FeedbackResponse(
            accepted=True, persisted_as_badcase=True, id=badcase_id,
        )
    except psycopg.errors.UndefinedTable as e:
        logger.error("rag_eval_badcases table missing — run migrations: %s", e)
        raise HTTPException(
            status_code=503,
            detail="bad-case sink unavailable: rag_eval_badcases not migrated",
        ) from e
    except Exception as e:
        logger.exception("feedback persist failed")
        raise HTTPException(status_code=500, detail=f"persist failed: {e}") from e
