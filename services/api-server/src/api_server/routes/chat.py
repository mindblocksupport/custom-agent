"""Chat endpoint · OpenAI 兼容 + SSE 流式

对应文档:
- docs/09-access-layer.md §3.2 SSE 流式协议
- docs/12-llm-api-protocols.md §10 统一抽象层
- docs/07-observability-and-eval.md §3 trace 嵌套
- docs/37-rag-implementation-plan.md §8.4 retrieval.start/done events (Day 11)
"""

import json
import re
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from agent_core import AgentConfig, ToolRegistry, run_agent
from gateway import ModelRouter
from schemas import (
    CitationData,
    ChatRequest,
    RetrievalDoneData,
    RetrievalDoneEvent,
    RetrievalStartData,
    RetrievalStartEvent,
)

from api_server.auth import verify_api_key
from api_server.config import settings
from api_server.dependencies import get_registry

router = APIRouter()
_model_router = ModelRouter()

# 解析 search_kb 返回的 wrapped 文本中的 <retrieved_context source="..." page="..." title="...">…</...>
_CTX_OPEN_RE = re.compile(
    r'<retrieved_context\s+source="([^"]+)"(?:\s+page="(\d+)")?(?:\s+title="([^"]*)")?\s*>',
    re.IGNORECASE,
)
_CTX_BLOCK_RE = re.compile(
    r'<retrieved_context\s+([^>]+?)\s*>(.*?)</retrieved_context>',
    re.IGNORECASE | re.DOTALL,
)
_REFUSAL_HINT = "知识库无相关内容"


def _parse_citations_from_search_kb(text: str) -> tuple[list[CitationData], bool]:
    """从 search_kb 的 wrapped 输出文本里抽出 CitationData (best-effort).

    Returns: (citations, refused)
    """
    if not text:
        return [], True
    if _REFUSAL_HINT in text and "<retrieved_context" not in text:
        return [], True
    citations: list[CitationData] = []
    for attrs_raw, snippet in _CTX_BLOCK_RE.findall(text):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', attrs_raw))
        source = attrs.get("source", "")
        # source 形如 doc:<doc_id>#chunk:<chunk_id>
        m = re.match(r'doc:([^#]+)#chunk:(.+)', source)
        if not m:
            continue
        page_raw = attrs.get("page")
        citations.append(
            CitationData(
                doc_id=m.group(1),
                chunk_id=m.group(2),
                source_uri=source,
                title=attrs.get("title") or None,
                page=int(page_raw) if page_raw else None,
                score=0.0,                       # search_kb wrapped 文本里不带 score
                snippet=snippet.strip()[:400],
            )
        )
    return citations, len(citations) == 0


def _agent_config_from_settings() -> AgentConfig:
    """根据全局配置生成单次 agent 运行的限制。"""
    return AgentConfig(
        max_steps=settings.max_steps,
        max_cost_usd=settings.max_cost_usd,
        max_consecutive_tool_errors=settings.max_tool_consecutive_errors,
    )


def _build_observability_metadata(request: ChatRequest) -> dict[str, Any]:
    """组装观测 metadata,贯穿 LLM 调用链。

    Langfuse / LiteLLM 识别这些 key:
        trace_id, trace_name, session_id, user_id, tags, version
    """
    trace_id = str(uuid4()).replace("-", "")
    user_meta: dict[str, Any] = request.metadata or {}

    return {
        "trace_id": trace_id,
        "trace_name": "agent_chat",
        "session_id": str(user_meta.get("session_id", trace_id)),
        "user_id": str(user_meta.get("user_id", "anonymous")),
        "tags": ["agent", "chat"] + list(user_meta.get("tags", [])),
    }


@router.post("/chat/completions")
async def chat_completions(
    request: ChatRequest,
    registry: ToolRegistry = Depends(get_registry),
    api_key: str = Depends(verify_api_key),
):
    """OpenAI Chat Completions 兼容接口 - 支持流式。

    Stream events (SSE):
    - `start`        - 开始 (含 model + max_steps)
    - `token`        - 文本流
    - `tool_call`    - 工具调用发起
    - `tool_result`  - 工具返回
    - `done`         - 完成 (含 steps + cost_usd)
    - `error`        - 错误

    Response headers:
    - `X-Trace-Id`   - Langfuse trace 主键 (排障 + 客诉时引)
    """
    messages = [m.model_dump(exclude_none=True) for m in request.messages]
    # Day 13 ModelRouter: model 缺失或显式 'auto' → 启发式路由 (省 ~50% LLM cost)
    raw_model = request.model
    if not raw_model or raw_model.lower() == "auto":
        decision = _model_router.route(
            messages=messages, tools=None, explicit_model=None,
        )
        model = decision.model
        route_reason = decision.reason
    else:
        model = raw_model
        route_reason = "explicit"
    agent_cfg = _agent_config_from_settings()
    obs_metadata = _build_observability_metadata(request)
    obs_metadata["route_reason"] = route_reason
    obs_metadata.setdefault("tags", []).append(f"route:{route_reason}")

    if request.stream:

        async def event_generator() -> AsyncIterator[dict]:
            # tool_call_id → (started_at_perf, query, k) — 用于配 tool_result
            pending_kb_calls: dict[str, tuple[float, str, int]] = {}
            try:
                async for event in run_agent(
                    messages=messages,
                    model=model,
                    registry=registry,
                    config=agent_cfg,
                    metadata=obs_metadata,
                ):
                    # ---- L37 §8.4: search_kb 的 retrieval.start / done 旁路事件 ----
                    if event.type == "tool_call" and event.data.name == "search_kb":  # type: ignore[union-attr]
                        try:
                            args = json.loads(event.data.arguments or "{}")  # type: ignore[union-attr]
                        except json.JSONDecodeError:
                            args = {}
                        q = str(args.get("query", ""))[:500]
                        k = int(args.get("k", 5))
                        cid = event.data.id or ""  # type: ignore[union-attr]
                        pending_kb_calls[cid] = (time.perf_counter(), q, k)
                        rs = RetrievalStartEvent(
                            data=RetrievalStartData(tool_call_id=cid or None, query=q, k=k)
                        )
                        yield {"event": rs.type, "data": rs.model_dump_json()}

                    elif event.type == "tool_result" and event.data.name == "search_kb":  # type: ignore[union-attr]
                        cid = event.data.id or ""  # type: ignore[union-attr]
                        result_text = event.data.result or ""  # type: ignore[union-attr]
                        started_at, _, _ = pending_kb_calls.pop(cid, (None, "", 0))
                        elapsed_ms = (
                            int((time.perf_counter() - started_at) * 1000)
                            if started_at else None
                        )
                        citations, refused = _parse_citations_from_search_kb(result_text)
                        rd = RetrievalDoneEvent(
                            data=RetrievalDoneData(
                                tool_call_id=cid or None,
                                citations=citations,
                                refused=refused,
                                refusal_reason=("no_match" if refused else None),
                                elapsed_ms=elapsed_ms,
                            )
                        )
                        # 先发 retrieval.done, 再 yield 原始 tool_result (前端两边都看得到)
                        yield {"event": rd.type, "data": rd.model_dump_json()}

                    yield {"event": event.type, "data": event.model_dump_json()}
                yield {"event": "done", "data": "[DONE]"}
            except Exception as e:
                yield {
                    "event": "error",
                    "data": json.dumps({"type": "error", "text": str(e)}),
                }

        return EventSourceResponse(
            event_generator(),
            headers={"X-Trace-Id": obs_metadata["trace_id"]},
        )

    # 非流式:聚合 token
    full_text = ""
    async for event in run_agent(
        messages=messages,
        model=model,
        registry=registry,
        config=agent_cfg,
        metadata=obs_metadata,
    ):
        if event.type == "token":
            full_text += event.text  # type: ignore[union-attr]

    return {
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": full_text},
                "finish_reason": "stop",
            }
        ],
        "trace_id": obs_metadata["trace_id"],
    }
