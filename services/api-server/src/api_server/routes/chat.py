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
from gateway import ModelRouter, is_vision_capable
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
    """从最近一条 user 消息抽出纯文本 (用于 title-gen / persistence)."""
    for m in reversed(messages):
        if m.get("role") == "user":
            return _content_to_text(m.get("content"))
    return ""


def _content_to_text(content: Any) -> str:
    """把 multimodal content array 拍平成纯文本 (DB persistence + title gen).

    image_url 部分用 [image] 占位; text 部分原样保留.
    schema: list[{"type": "text"|"image_url", ...}]
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for p in content:
            if not isinstance(p, dict):
                continue
            t = p.get("type")
            if t == "text":
                parts.append(str(p.get("text", "")))
            elif t == "image_url":
                # [image] 标记 + (可选) URL 短摘要 (避免 DB 里塞 base64)
                url = (p.get("image_url") or {}).get("url", "")
                if url.startswith("data:"):
                    parts.append("[image:base64]")
                elif url:
                    parts.append(f"[image:{url[:60]}]")
                else:
                    parts.append("[image]")
            else:
                parts.append(f"[{t}]")
        return "\n".join(p for p in parts if p)
    return str(content)


def _count_image_parts(content: Any) -> int:
    if not isinstance(content, list):
        return 0
    return sum(
        1 for p in content
        if isinstance(p, dict) and p.get("type") == "image_url"
    )


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


_SKILL_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def _render_skill_prompt(template: str, vars_: dict[str, str]) -> str:
    """Mustache 子集 — 仅 {{ name }}. 缺失变量保留原文 (前端会提示)."""
    if not vars_:
        return template

    def sub(m: re.Match[str]) -> str:
        key = m.group(1)
        return vars_.get(key, m.group(0))
    return _SKILL_VAR_RE.sub(sub, template)


def _apply_skill_to_messages(
    messages: list[dict], skill: skill_db.SkillRow | None,
    skill_vars: dict[str, str] | None = None,
) -> list[dict]:
    """v1.5: 把 skill.system_prompt 作为 system 消息插到对话最前面.

    skill_vars: 渲染 {{ var }} 模板; 用 client 传过来的值替换.
    """
    if not skill or not skill.system_prompt.strip():
        return messages
    rendered = _render_skill_prompt(skill.system_prompt, skill_vars or {})
    # 防重复注入: 已存在 system 消息且内容相同则跳过
    if messages and messages[0].get("role") == "system":
        if rendered in (messages[0].get("content") or ""):
            return messages
    return [{"role": "system", "content": rendered}] + messages


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
    msgs = [m.model_dump() for m in request.messages]
    last_user_msg = next(
        (m for m in reversed(msgs) if m.get("role") == "user"), None,
    )
    if not last_user_msg:
        return
    raw_content = last_user_msg.get("content")
    last_user = _content_to_text(raw_content)
    if not last_user:
        return
    n_images = _count_image_parts(raw_content)
    metadata: dict[str, Any] = {}
    if n_images > 0:
        metadata["multimodal"] = {"n_images": n_images}
    try:
        await asyncio.to_thread(
            chat_db.append_message,
            session_id=session_id, tenant_id=principal.tenant_id,
            role="user", content=last_user, trace_id=trace_id,
            metadata=metadata or None,
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
    messages = _apply_skill_to_messages(messages, skill, request.skill_vars)
    effective_registry, applied_tools = _build_effective_registry(
        registry, workspace, skill,
    )

    # 预算检查 (双层): actor budget (member 维度) → workspace budget (整体)
    # - >= 100% → 402 拦截 + audit
    # - >= 80% → 不拦截, X-Budget-Warning header 软警告
    budget_warning_header: str | None = None
    if workspace is not None:
        # 1. actor 维度 (workspace_member.budget_*) — 优先, 因为更具体
        actor_budget = await asyncio.to_thread(
            ws_db.fetch_actor_budget_usage,
            workspace_id=workspace.id,
            tenant_id=principal.tenant_id,
            actor_id=principal.actor_id,
        )
        if actor_budget and actor_budget.any_exceeded:
            scope_zh = "actor 日预算" if actor_budget.daily_exceeded else "actor 月预算"
            limit = (
                actor_budget.budget_daily_usd if actor_budget.daily_exceeded
                else actor_budget.budget_monthly_usd
            )
            used = (
                actor_budget.today_cost_usd if actor_budget.daily_exceeded
                else actor_budget.month_cost_usd
            )
            from api_server.db import audit as audit_db
            audit_db.insert(
                tenant_id=principal.tenant_id, actor_id=principal.actor_id,
                action="actor.budget_exceeded",
                resource_type="workspace_member",
                resource_id=f"{workspace.id}::{principal.actor_id}",
                detail={
                    "scope": "daily" if actor_budget.daily_exceeded else "monthly",
                    "limit_usd": limit,
                    "used_usd": used,
                    "model_about_to_call": request.model or "auto",
                },
            )
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "actor_budget_exceeded",
                    "scope": "daily" if actor_budget.daily_exceeded else "monthly",
                    "message": (
                        f"你的 {scope_zh} 已超 (${used:.4f} / ${limit:.2f}). "
                        "请联系 workspace owner 调高你的限额。"
                    ),
                    "limit_usd": limit,
                    "used_usd": used,
                },
            )

        # 2. workspace 整体维度
        budget = await asyncio.to_thread(
            ws_db.fetch_budget_usage,
            workspace_id=workspace.id, tenant_id=principal.tenant_id,
        )
        if budget and budget.any_exceeded:
            scope_zh = "日预算" if budget.daily_exceeded else "月预算"
            limit = (
                budget.budget_daily_usd if budget.daily_exceeded
                else budget.budget_monthly_usd
            )
            used = (
                budget.today_cost_usd if budget.daily_exceeded
                else budget.month_cost_usd
            )
            from api_server.db import audit as audit_db
            audit_db.insert(
                tenant_id=principal.tenant_id, actor_id=principal.actor_id,
                action="workspace.budget_exceeded",
                resource_type="workspace", resource_id=str(workspace.id),
                detail={
                    "scope": "daily" if budget.daily_exceeded else "monthly",
                    "limit_usd": limit,
                    "used_usd": used,
                    "model_about_to_call": request.model or "auto",
                },
            )
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "budget_exceeded",
                    "scope": "daily" if budget.daily_exceeded else "monthly",
                    "message": (
                        f"工作空间「{workspace.name}」{scope_zh}已超 "
                        f"(${used:.4f} / ${limit:.2f}). "
                        "请在「工作空间设置」调高预算或等下一周期。"
                    ),
                    "limit_usd": limit,
                    "used_usd": used,
                },
            )
        elif budget:
            # 软警告: workspace 任一维度 >= 80% 即提示, 不拦截
            warns: list[str] = []
            if (
                budget.budget_daily_usd is not None
                and budget.budget_daily_usd > 0
                and budget.today_cost_usd / budget.budget_daily_usd >= 0.8
            ):
                pct = budget.today_cost_usd / budget.budget_daily_usd * 100
                warns.append(
                    f"ws_daily={pct:.0f}%(${budget.today_cost_usd:.4f}/${budget.budget_daily_usd:.2f})"
                )
            if (
                budget.budget_monthly_usd is not None
                and budget.budget_monthly_usd > 0
                and budget.month_cost_usd / budget.budget_monthly_usd >= 0.8
            ):
                pct = budget.month_cost_usd / budget.budget_monthly_usd * 100
                warns.append(
                    f"ws_monthly={pct:.0f}%(${budget.month_cost_usd:.4f}/${budget.budget_monthly_usd:.2f})"
                )
            # 也加 actor 软警告 (如果设了 budget 但没超)
            if actor_budget and not actor_budget.any_exceeded:
                if (
                    actor_budget.budget_daily_usd is not None
                    and actor_budget.budget_daily_usd > 0
                    and actor_budget.today_cost_usd / actor_budget.budget_daily_usd >= 0.8
                ):
                    pct = actor_budget.today_cost_usd / actor_budget.budget_daily_usd * 100
                    warns.append(f"actor_daily={pct:.0f}%")
                if (
                    actor_budget.budget_monthly_usd is not None
                    and actor_budget.budget_monthly_usd > 0
                    and actor_budget.month_cost_usd / actor_budget.budget_monthly_usd >= 0.8
                ):
                    pct = actor_budget.month_cost_usd / actor_budget.budget_monthly_usd * 100
                    warns.append(f"actor_monthly={pct:.0f}%")
            if warns:
                budget_warning_header = "; ".join(warns)

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

    # workspace.allowed_models 白名单 enforce (空 = 不限)
    if workspace and workspace.allowed_models:
        if model not in workspace.allowed_models:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "model_not_allowed",
                    "message": (
                        f"模型 '{model}' 不在工作空间「{workspace.name}」白名单内. "
                        f"允许的模型: {', '.join(workspace.allowed_models)}"
                    ),
                    "model": model,
                    "allowed": workspace.allowed_models,
                },
            )

    # 多模态检查: 任意 user 消息含 image_url? 若 model 不支持 vision —
    # 显式指定 → 报 400; auto / workspace_default / router → 自动 promote 到默认 vision 模型
    has_image = any(
        m.get("role") == "user" and _count_image_parts(m.get("content")) > 0
        for m in messages
    )
    if has_image and not is_vision_capable(model):
        if route_reason == "explicit":
            raise HTTPException(
                400,
                f"模型 '{model}' 不支持图片输入. 切到 vision-capable 模型 "
                "(claude-sonnet-4-x / gpt-4o / gemini-1.5+ / qwen-vl 等), "
                "或移除附件.",
            )
        # 自动升级到 reasoning model (默认 sonnet, 已 vision)
        model = _model_router.reasoning
        route_reason = f"vision_auto_promote_from_{route_reason}"
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

        sse_headers = {
            "X-Trace-Id": obs_metadata["trace_id"],
            "X-Route-Reason": route_reason,
            "X-Model": model,
            "X-Session-Id": str(session_id) if session_id else "",
            "Access-Control-Expose-Headers":
                "X-Trace-Id, X-Route-Reason, X-Model, X-Session-Id, X-Budget-Warning",
        }
        if budget_warning_header:
            sse_headers["X-Budget-Warning"] = budget_warning_header
        return EventSourceResponse(event_generator(), headers=sse_headers)

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
    from fastapi.responses import JSONResponse
    call_cost = float(nonstream_done.get("cost_usd", 0)) if nonstream_done else 0.0
    body_dict = {
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
        "cost_usd": call_cost,
    }
    headers = {
        "X-Trace-Id": obs_metadata["trace_id"],
        "X-Route-Reason": route_reason,
        "X-Model": model,
        # 本次调用 cost (仅 non-stream; stream 走 SSE done event)
        "X-Cost-This-Call": f"{call_cost:.6f}",
        "Access-Control-Expose-Headers":
            "X-Trace-Id, X-Route-Reason, X-Model, X-Session-Id, "
            "X-Budget-Warning, X-Cost-This-Call",
    }
    if budget_warning_header:
        headers["X-Budget-Warning"] = budget_warning_header
    return JSONResponse(content=body_dict, headers=headers)
