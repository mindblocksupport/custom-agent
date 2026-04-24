"""Chat endpoint · OpenAI 兼容 + SSE 流式

对应文档:
- docs/09-access-layer.md §3.2 SSE 流式协议
- docs/12-llm-api-protocols.md §10 统一抽象层
- docs/07-observability-and-eval.md §3 trace 嵌套
- docs/37-rag-implementation-plan.md §8.4 retrieval.start/done events (Day 11)
"""

import asyncio
import json
import logging
import re
import time
from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
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

from api_server.acl import Principal, sign_principal_token
from api_server.auth import verify_api_key
from api_server.config import settings
from api_server.db import chat as chat_db
from api_server.db import skills as skill_db
from api_server.db import workspaces as ws_db
from api_server.dependencies import get_registry
from api_server.title_generator import maybe_schedule_title_generation

logger = logging.getLogger(__name__)
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


def _last_user_text(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            c = m.get("content")
            return c if isinstance(c, str) else str(c or "")
    return ""


async def _resolve_workspace_skill(
    request: ChatRequest, principal: Principal,
) -> tuple[ws_db.WorkspaceRow | None, skill_db.SkillRow | None]:
    """v1.5: 加载 workspace + skill (按优先级).

    优先级 (高 → 低):
    1. session.workspace_id (会话锁定; 不信前端的 workspace_id 切换)
    2. request.skill_id → skill.workspace_id
    3. request.workspace_id

    Skill 仍可逐请求换 (用户中途切技能).
    """
    workspace = None
    skill = None
    effective_workspace_id = None

    # 1. 已存在 session → 用 session 锁定的 workspace
    if request.session_id is not None:
        try:
            session_row = await asyncio.to_thread(
                chat_db.get_session,
                session_id=request.session_id, tenant_id=principal.tenant_id,
            )
            if session_row and session_row.workspace_id:
                effective_workspace_id = session_row.workspace_id
        except Exception as e:
            logger.warning("session resolve failed: %s", e)

    try:
        # 2. skill 参数优先 (skill 自带 workspace_id)
        if request.skill_id is not None:
            skill = await asyncio.to_thread(
                skill_db.get,
                skill_id=request.skill_id, tenant_id=principal.tenant_id,
            )
            if skill is None:
                raise HTTPException(404, "skill not found")
            # 如果 session 已锁 workspace, skill 必须属同一个 workspace
            if effective_workspace_id and skill.workspace_id != effective_workspace_id:
                raise HTTPException(
                    400,
                    f"skill belongs to different workspace than session "
                    f"({skill.workspace_id} vs {effective_workspace_id})",
                )
            effective_workspace_id = skill.workspace_id
        # 3. 否则用 request.workspace_id (仅当 session 还没锁定)
        elif effective_workspace_id is None and request.workspace_id is not None:
            effective_workspace_id = request.workspace_id

        if effective_workspace_id is not None:
            workspace = await asyncio.to_thread(
                ws_db.get,
                workspace_id=effective_workspace_id, tenant_id=principal.tenant_id,
            )
            if workspace is None and request.workspace_id is not None:
                # 仅当用户显式传了 workspace_id 才报 404
                raise HTTPException(404, "workspace not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("workspace/skill resolve failed: %s", e)
    return workspace, skill


async def _ensure_session(
    request: ChatRequest, principal: Principal,
    workspace: ws_db.WorkspaceRow | None = None,
    skill: skill_db.SkillRow | None = None,
) -> UUID | None:
    """Day 4 P0 #7 + v1.5: 解析 / 创建 session.

    - 显式 session_id → 校验属本 tenant + 未删
    - 否则 → 创建空 session (含 workspace_id + skill_id)
    - DB 不可用 → 返回 None (chat 继续, 不挂掉)
    """
    try:
        if request.session_id is not None:
            row = await asyncio.to_thread(
                chat_db.get_session,
                session_id=request.session_id, tenant_id=principal.tenant_id,
            )
            if row is None:
                raise HTTPException(404, "session not found")
            return row.id
        first_user = _last_user_text([m.model_dump() for m in request.messages])
        seed_title = first_user.strip()[:30] or "新会话"
        sid = await asyncio.to_thread(
            chat_db.create_session,
            tenant_id=principal.tenant_id,
            actor_id=principal.actor_id,
            title=seed_title,
            workspace_id=workspace.id if workspace else None,
            skill_id=skill.id if skill else None,
        )
        return sid
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("session ensure failed (%s); chat continues w/o persist", e)
        return None


def _apply_skill_to_messages(
    messages: list[dict], skill: skill_db.SkillRow | None,
) -> list[dict]:
    """v1.5: 把 skill.system_prompt 作为 system 消息插到对话最前面."""
    if not skill or not skill.system_prompt.strip():
        return messages
    # 防重复注入: 已存在 system 消息且内容相同则跳过
    if messages and messages[0].get("role") == "system":
        if skill.system_prompt in (messages[0].get("content") or ""):
            return messages
    return [{"role": "system", "content": skill.system_prompt}] + messages


def _build_effective_registry(
    base: ToolRegistry,
    workspace: ws_db.WorkspaceRow | None,
    skill: skill_db.SkillRow | None,
) -> tuple[ToolRegistry, list[str] | None]:
    """v1.5: 按 skill > workspace 优先级过滤工具白名单.

    返回 (effective_registry, applied_names_or_None).
    优先级:
        skill.allowed_tools 非空 → 用 skill 的
        否则 workspace.allowed_tools 非空 → 用 workspace 的
        否则 → 不过滤 (返回 base)

    LLM 看不到被过滤掉的工具 (get_schemas 只列 effective).
    Executor 拒绝调用未注册的工具 (KeyError → tool_result.error).
    """
    allowed: list[str] = []
    if skill and skill.allowed_tools:
        allowed = list(skill.allowed_tools)
    elif workspace and workspace.allowed_tools:
        allowed = list(workspace.allowed_tools)
    if not allowed:
        return base, None
    filtered = ToolRegistry()
    applied: list[str] = []
    for name in allowed:
        try:
            filtered.register(base.get(name))
            applied.append(name)
        except KeyError:
            logger.warning(
                "tool '%s' allowed by skill/workspace but not registered", name,
            )
    return filtered, applied


async def _persist_user_msg(
    *, session_id: UUID | None, principal: Principal,
    request: ChatRequest, trace_id: str,
) -> None:
    if session_id is None:
        return
    last_user = _last_user_text([m.model_dump() for m in request.messages])
    if not last_user:
        return
    try:
        await asyncio.to_thread(
            chat_db.append_message,
            session_id=session_id, tenant_id=principal.tenant_id,
            role="user", content=last_user, trace_id=trace_id,
        )
    except Exception as e:
        logger.warning("persist user msg failed: %s", e)


async def _persist_assistant_msg(
    *, session_id: UUID | None, principal: Principal,
    content: str, tool_calls: list[dict] | None,
    trace_id: str, model: str,
    cost_usd: float, input_tokens: int, output_tokens: int,
    metadata_extra: dict,
) -> None:
    if session_id is None:
        return
    try:
        await asyncio.to_thread(
            chat_db.append_message,
            session_id=session_id, tenant_id=principal.tenant_id,
            role="assistant",
            content=content,
            tool_calls=tool_calls,
            trace_id=trace_id,
            model=model,
            cost_usd=cost_usd,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            metadata=metadata_extra,
        )
    except Exception as e:
        logger.warning("persist assistant msg failed: %s", e)


@router.post("/chat/completions")
async def chat_completions(
    request: ChatRequest,
    registry: ToolRegistry = Depends(get_registry),
    principal: Principal = Depends(verify_api_key),
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

    # v1.5 沉淀层: workspace + skill 解析 + system_prompt 注入 + 工具白名单过滤
    workspace, skill = await _resolve_workspace_skill(request, principal)
    messages = _apply_skill_to_messages(messages, skill)
    effective_registry, applied_tools = _build_effective_registry(
        registry, workspace, skill,
    )

    # Day 13 ModelRouter: model 缺失或显式 'auto' → 启发式路由 (省 ~50% LLM cost)
    # v1.5: 优先级 = 请求显式 > skill > workspace.default_model > router auto
    raw_model = request.model
    if (not raw_model or raw_model.lower() == "auto") and workspace and workspace.default_model and workspace.default_model != "auto":
        model = workspace.default_model
        route_reason = "workspace_default"
    elif not raw_model or raw_model.lower() == "auto":
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
    if workspace:
        obs_metadata["workspace_id"] = str(workspace.id)
        obs_metadata["workspace_name"] = workspace.name
    if skill:
        obs_metadata["skill_id"] = str(skill.id)
        obs_metadata["skill_name"] = f"{skill.name} v{skill.version}"
    if applied_tools is not None:
        obs_metadata["allowed_tools"] = applied_tools
    obs_metadata["route_reason"] = route_reason
    obs_metadata.setdefault("tags", []).append(f"route:{route_reason}")

    # v1.5: 计算默认 collections (skill > workspace > 空) → 注入 JWT, 让 search_kb 默认按它过滤
    default_collections: list[str] = []
    if skill and skill.default_collections:
        default_collections = list(skill.default_collections)
    elif workspace and workspace.default_collection:
        default_collections = [workspace.default_collection]
    if default_collections:
        obs_metadata["default_collections"] = default_collections

    # 构造 per-request token_provider (闭包带 workspace/skill 上下文)
    def token_provider() -> str:
        return sign_principal_token(
            principal, default_collections=default_collections,
        )

    # Day 4 P0 #7 + v1.5: 解析/建 session (带 workspace + skill), 持久化 user msg
    session_id = await _ensure_session(request, principal, workspace, skill)
    if session_id is not None:
        obs_metadata["session_id"] = str(session_id)
    await _persist_user_msg(
        session_id=session_id, principal=principal,
        request=request, trace_id=obs_metadata["trace_id"],
    )

    if request.stream:

        async def event_generator() -> AsyncIterator[dict]:
            # tool_call_id → (started_at_perf, query, k) — 用于配 tool_result
            pending_kb_calls: dict[str, tuple[float, str, int]] = {}
            # Day 4 P0 #7: 边流边攒, [DONE] 时一次写 assistant msg
            assistant_text_buf: list[str] = []
            assistant_tool_calls: list[dict] = []
            final_done_data: dict | None = None
            try:
                async for event in run_agent(
                    messages=messages,
                    model=model,
                    registry=effective_registry,
                    config=agent_cfg,
                    metadata=obs_metadata,
                    token_provider=token_provider,
                ):
                    # ---- Day 4 P0 #7: 持久化攒数据 ----
                    if event.type == "token":
                        assistant_text_buf.append(event.text)  # type: ignore[union-attr]
                    elif event.type == "tool_call":
                        d = event.data  # type: ignore[union-attr]
                        assistant_tool_calls.append({
                            "id": d.id, "type": "function",
                            "function": {"name": d.name, "arguments": d.arguments},
                        })
                    elif event.type == "done":
                        final_done_data = event.data.model_dump()  # type: ignore[union-attr]
                    # ----
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
                # Day 4 P0 #7: [DONE] 之前一次性写 assistant msg
                await _persist_assistant_msg(
                    session_id=session_id, principal=principal,
                    content="".join(assistant_text_buf),
                    tool_calls=assistant_tool_calls or None,
                    trace_id=obs_metadata["trace_id"], model=model,
                    cost_usd=float(final_done_data.get("cost_usd", 0)) if final_done_data else 0.0,
                    input_tokens=int(final_done_data.get("input_tokens", 0)) if final_done_data else 0,
                    output_tokens=int(final_done_data.get("output_tokens", 0)) if final_done_data else 0,
                    metadata_extra={"route_reason": route_reason},
                )
                # Day 5 P0 #7: 首轮自动起标题 (后台异步, 前端下次 list 时刷新)
                if session_id is not None and request.session_id is None:
                    maybe_schedule_title_generation(
                        session_id=session_id, tenant_id=principal.tenant_id,
                        user_text=_last_user_text(messages),
                        assistant_text="".join(assistant_text_buf),
                        is_first_turn=True,
                    )
                yield {"event": "done", "data": "[DONE]"}
            except Exception as e:
                # 落 error msg 兜底, 让会话历史完整 (不静默丢)
                await _persist_assistant_msg(
                    session_id=session_id, principal=principal,
                    content="".join(assistant_text_buf) or "(error)",
                    tool_calls=assistant_tool_calls or None,
                    trace_id=obs_metadata["trace_id"], model=model,
                    cost_usd=0.0, input_tokens=0, output_tokens=0,
                    metadata_extra={"route_reason": route_reason,
                                    "error": f"{type(e).__name__}: {e}"},
                )
                yield {
                    "event": "error",
                    "data": json.dumps({"type": "error", "text": str(e)}),
                }

        return EventSourceResponse(
            event_generator(),
            headers={
                "X-Trace-Id": obs_metadata["trace_id"],
                "X-Route-Reason": route_reason,
                "X-Model": model,
                "X-Session-Id": str(session_id) if session_id else "",
                "Access-Control-Expose-Headers":
                    "X-Trace-Id, X-Route-Reason, X-Model, X-Session-Id",
            },
        )

    # 非流式:聚合 token
    full_text = ""
    nonstream_done: dict | None = None
    nonstream_tool_calls: list[dict] = []
    async for event in run_agent(
        messages=messages,
        model=model,
        registry=effective_registry,
        config=agent_cfg,
        metadata=obs_metadata,
        token_provider=token_provider,
    ):
        if event.type == "token":
            full_text += event.text  # type: ignore[union-attr]
        elif event.type == "tool_call":
            d = event.data  # type: ignore[union-attr]
            nonstream_tool_calls.append({
                "id": d.id, "type": "function",
                "function": {"name": d.name, "arguments": d.arguments},
            })
        elif event.type == "done":
            nonstream_done = event.data.model_dump()  # type: ignore[union-attr]

    await _persist_assistant_msg(
        session_id=session_id, principal=principal,
        content=full_text, tool_calls=nonstream_tool_calls or None,
        trace_id=obs_metadata["trace_id"], model=model,
        cost_usd=float(nonstream_done.get("cost_usd", 0)) if nonstream_done else 0.0,
        input_tokens=int(nonstream_done.get("input_tokens", 0)) if nonstream_done else 0,
        output_tokens=int(nonstream_done.get("output_tokens", 0)) if nonstream_done else 0,
        metadata_extra={"route_reason": route_reason},
    )
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
        "session_id": str(session_id) if session_id else None,
    }
