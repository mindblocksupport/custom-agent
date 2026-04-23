"""可观测性 · L7 (Langfuse)

对应文档: docs/07-observability-and-eval.md / docs/16-opensource-stack-decision.md §4

实现层级:
1. **LLM call 级**: 通过 LiteLLM 内置 callback 自动上报 (gateway 模块负责)
2. **Agent run 级**: 本模块在 chat 路由里建顶层 trace,把 trace_id 透传给 LiteLLM
3. **Tool call 级**: 在 chat 路由里观察 ToolCall/ToolResult 事件,创建子 span (后续)

环境变量:
    LANGFUSE_PUBLIC_KEY   - 启用观测的开关
    LANGFUSE_SECRET_KEY
    LANGFUSE_HOST         - 默认 https://cloud.langfuse.com
"""

import logging
import os
import sys

from api_server.config import settings

logger = logging.getLogger(__name__)


def setup_tracing() -> None:
    """初始化日志 + Langfuse (如果配置了)。

    幂等:可多次调用。
    """
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    main_logger = logging.getLogger("api_server")
    main_logger.info(f"Tracing initialized (env={settings.env})")

    # 把 Langfuse 配置注入 env (LiteLLM callback 会读 env)
    if settings.langfuse_public_key and settings.langfuse_secret_key:
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
        os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
        os.environ["LANGFUSE_HOST"] = settings.langfuse_host
        main_logger.info(f"Langfuse enabled (host={settings.langfuse_host})")
        # 触发 gateway 模块重新检查 env
        try:
            from gateway.client import _maybe_enable_langfuse

            _maybe_enable_langfuse()
        except Exception:
            main_logger.exception("Failed to enable LiteLLM Langfuse callback")
    else:
        main_logger.info(
            "Langfuse not configured (set LANGFUSE_PUBLIC_KEY+SECRET_KEY in .env)"
        )


def is_langfuse_enabled() -> bool:
    return bool(settings.langfuse_public_key and settings.langfuse_secret_key)
