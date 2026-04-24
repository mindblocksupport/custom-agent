"""Session 标题自动生成 (Day 5 P0 #7).

策略:
- 首轮 chat 完成后, 异步发一个独立 LLM 请求提一个 5 字标题
- 用 cheap model (DeepSeek-Chat, ~$0.0001/次)
- 标题写回 chat_sessions.title; 前端下次拉 /v1/sessions/{id} 时刷新
- 失败不重试 (有 seed_title 兜底)

为什么用 background task 而非 SSE event:
- chat 流已经 yield [DONE] 后再 LLM 调用太晚 (流早结束)
- 用 asyncio.create_task 后台跑, 前端通过下次拉 session 自动看到
"""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from gateway import llm_complete_stream

from api_server.db import chat as chat_db

logger = logging.getLogger(__name__)

TITLE_MODEL = "deepseek/deepseek-chat"
TITLE_MAX_TOKENS = 16
TITLE_PROMPT_TEMPLATE = (
    "请用 5-12 个汉字概括下面这段对话的主题, 直接输出标题, 不要标点不要解释:\n\n"
    "用户问: {user}\n"
    "助手答: {assistant}\n\n"
    "标题:"
)


async def generate_and_save_title(
    *, session_id: UUID, tenant_id: UUID,
    user_text: str, assistant_text: str,
    model: str = TITLE_MODEL,
) -> str | None:
    """LLM 起标题 + 写 DB. 返回 title 或 None (失败)."""
    if not user_text.strip():
        return None
    try:
        prompt = TITLE_PROMPT_TEMPLATE.format(
            user=user_text[:200],
            assistant=(assistant_text or "")[:300],
        )
        chunks: list[str] = []
        async for chunk in llm_complete_stream(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            metadata={"trace_name": "title_gen"},
            max_tokens=TITLE_MAX_TOKENS,
            temperature=0.3,
        ):
            if chunk.get("type") == "text":
                chunks.append(chunk["delta"])
        title = "".join(chunks).strip().splitlines()[0] if chunks else ""
        # strip 引号 / 特殊符号 / 太长截断
        title = title.strip("\"'「」『』 ")[:30]
        if not title:
            return None
        await asyncio.to_thread(
            chat_db.update_session_title,
            session_id=session_id, tenant_id=tenant_id, title=title,
        )
        logger.info("title generated for session %s: %r", session_id, title)
        return title
    except Exception as e:
        logger.warning("title generation failed for %s: %s", session_id, e)
        return None


def maybe_schedule_title_generation(
    *, session_id: UUID, tenant_id: UUID,
    user_text: str, assistant_text: str,
    is_first_turn: bool,
) -> None:
    """首轮才触发. 调用方 (chat.py) 在 persist 后调."""
    if not is_first_turn:
        return
    if not user_text.strip():
        return
    asyncio.create_task(generate_and_save_title(
        session_id=session_id, tenant_id=tenant_id,
        user_text=user_text, assistant_text=assistant_text,
    ))
