"""LiteLLM 包装 · 统一流式接口 + Langfuse 观测 + cost/usage 计费

对应文档:
    docs/02-llm-gateway.md
    docs/16-opensource-stack-decision.md §1
    docs/07-observability-and-eval.md §5
    docs/21-finops-cost-management.md
"""

import logging
import os
from collections.abc import AsyncIterator
from typing import Any

import litellm

logger = logging.getLogger(__name__)

# LiteLLM 全局配置
litellm.drop_params = True
litellm.set_verbose = False
litellm.suppress_debug_info = True


def _maybe_enable_langfuse() -> None:
    """如检测到 Langfuse 环境变量,启用 LiteLLM Langfuse callback。

    幂等:多次调用不会重复添加 callback。
    """
    pk = os.getenv("LANGFUSE_PUBLIC_KEY")
    sk = os.getenv("LANGFUSE_SECRET_KEY")
    if not (pk and sk):
        return
    if "langfuse" in (litellm.success_callback or []):
        return
    litellm.success_callback = list(litellm.success_callback or []) + ["langfuse"]
    litellm.failure_callback = list(litellm.failure_callback or []) + ["langfuse"]
    logger.info(
        "Langfuse LiteLLM callback enabled (host=%s)",
        os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )


_maybe_enable_langfuse()


def _calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """用 LiteLLM 内置价格表算单次调用 USD 成本。

    LiteLLM 的 model_cost 库覆盖 100+ 主流模型(含 DeepSeek/Qwen/Claude/OpenAI 等);
    找不到时返回 0.0(免费/未知模型),不抛异常,不影响业务流。
    """
    try:
        prompt_cost, completion_cost = litellm.cost_per_token(
            model=model,
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
        )
        return float(prompt_cost) + float(completion_cost)
    except Exception:
        return 0.0


async def llm_complete_stream(
    messages: list[dict[str, Any]],
    model: str,
    tools: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> AsyncIterator[dict[str, Any]]:
    """统一流式接口 —— 支持任意 LiteLLM 兼容供应商。

    Args:
        messages: OpenAI 兼容消息历史
        model: LiteLLM 模型 ID
        tools: 工具 schema 列表
        metadata: 透传给 LiteLLM/Langfuse (trace_id/session_id/...)
        **kwargs: 其他 LiteLLM 参数

    Yields:
        {"type": "text",      "delta": str}                                - 文本流
        {"type": "tool_call", "data": dict}                                - 工具调用 (累积完成)
        {"type": "usage",     "cost": float,                               - 末尾用量
                              "input_tokens": int,
                              "output_tokens": int,
                              "total_tokens": int}
    """
    _maybe_enable_langfuse()

    # 强制启 include_usage,LiteLLM 在流末尾会 emit 一个 usage chunk
    stream_options = dict(kwargs.pop("stream_options", {}) or {})
    stream_options.setdefault("include_usage", True)

    response = await litellm.acompletion(
        model=model,
        messages=messages,
        tools=tools or None,
        stream=True,
        stream_options=stream_options,
        metadata=metadata or {},
        **kwargs,
    )

    pending_tool_calls: dict[int, dict[str, Any]] = {}
    final_usage: Any | None = None

    async for chunk in response:
        # 流末 usage chunk 通常 choices=[];把 usage 单独捕获
        usage = getattr(chunk, "usage", None)
        if usage is not None:
            final_usage = usage

        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta

        # 文本内容
        if getattr(delta, "content", None):
            yield {"type": "text", "delta": delta.content}

        # 工具调用 - 累积分块的 partial JSON
        if getattr(delta, "tool_calls", None):
            for tc in delta.tool_calls:
                idx = tc.index or 0
                if idx not in pending_tool_calls:
                    pending_tool_calls[idx] = {
                        "id": tc.id or f"call_{idx}",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    }
                if tc.function:
                    if tc.function.name:
                        pending_tool_calls[idx]["function"]["name"] += tc.function.name
                    if tc.function.arguments:
                        pending_tool_calls[idx]["function"]["arguments"] += tc.function.arguments

    # 累积完成的 tool calls
    for tc in pending_tool_calls.values():
        yield {"type": "tool_call", "data": tc}

    # 末尾 usage event
    if final_usage is not None:
        input_tokens = int(getattr(final_usage, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(final_usage, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(final_usage, "total_tokens", input_tokens + output_tokens) or 0)
        yield {
            "type": "usage",
            "cost": _calc_cost(model, input_tokens, output_tokens),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
        }
