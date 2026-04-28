"""FastAPI 入口 · L9 接入层

对应文档: docs/09-access-layer.md
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from api_server.config import settings
from api_server.cron import run_audit_cleanup_cron
from api_server.db.api_keys import seed_dev_key
from api_server.observability import setup_tracing
from api_server.registry_bootstrap import ToolBootstrap
from api_server.routes import (
    audit, chat, feedback, health, kb, keys, me, sessions, skills, workspaces,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期:
    - 启动:init logging → init ToolBootstrap (含 MCP 子进程) → 挂到 app.state
    - 关闭:teardown bootstrap (杀子进程)
    """
    setup_tracing()
    # Day 1-2 P0 #3:
    # - dev 模式: 自动播种 dev-key 让 frontend "dev-key-change-me" 仍能用
    # - dev 模式: RAG_MCP_JWT_SECRET 未设时生成临时密钥 (生产环境必须显式 set)
    if settings.env == "dev":
        seed_dev_key()
        # v1.5: dev seed default workspace + 2 demo skills (幂等)
        from api_server.seed import seed_default_workspace_and_skills
        seed_default_workspace_and_skills()
        import os as _os
        import secrets as _secrets
        if not _os.environ.get("RAG_MCP_JWT_SECRET"):
            _os.environ["RAG_MCP_JWT_SECRET"] = _secrets.token_urlsafe(32)
            logger.warning(
                "RAG_MCP_JWT_SECRET unset → generated ephemeral dev secret. "
                "Set explicitly in prod (rotate-aware: use _PREV for old secret)."
            )
    bootstrap = ToolBootstrap()
    cron_task: asyncio.Task | None = None
    try:
        await bootstrap.setup()
        app.state.bootstrap = bootstrap
        app.state.registry = bootstrap.registry
        logger.info(f"Active tools: {bootstrap.registry.names()}")
        # 后台 audit retention cron — 默认每 24h 跑一次, 删 365 天前
        # 通过 env 关掉: AUDIT_AUTO_CLEANUP=false
        cron_task = asyncio.create_task(run_audit_cleanup_cron())
        yield
    finally:
        if cron_task is not None:
            cron_task.cancel()
            try:
                await cron_task
            except (asyncio.CancelledError, Exception):
                pass
        await bootstrap.teardown()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Custom Agent Platform · API Server",
        version="0.1.0",
        description=(
            "企业级 Agent 平台 MVP · 详见 docs/00-architecture-overview.md\n\n"
            "服务边界:\n"
            "- L9 接入层 (本服务)\n"
            "- L5 Agent runtime: services/agent-core\n"
            "- L2 LLM Gateway: services/gateway\n"
            "- L4 内置工具: services/tools-builtin (in-process)\n"
            "- L4 MCP 工具: services/tool-servers/* (子进程)"
        ),
        lifespan=lifespan,
    )

    # CORS - dev 模式全放开;生产改具体白名单
    if settings.env == "dev":
        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=".*",
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # 路由注册
    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(chat.router, prefix="/v1", tags=["chat"])
    app.include_router(feedback.router, prefix="/v1", tags=["feedback"])
    app.include_router(sessions.router, prefix="/v1", tags=["sessions"])
    app.include_router(kb.router, prefix="/v1", tags=["kb"])
    app.include_router(workspaces.router, prefix="/v1", tags=["workspaces (v1.5)"])
    app.include_router(skills.router, prefix="/v1", tags=["skills (v1.5)"])
    app.include_router(me.router, prefix="/v1", tags=["me / usage"])
    app.include_router(keys.router, prefix="/v1", tags=["api keys"])
    app.include_router(audit.router, prefix="/v1", tags=["audit"])

    # 静态前端托管 - 默认 dev 模式开启;生产置 SERVE_WEB_LITE=false 改用 Caddy/CDN
    # 详见 infra/Caddyfile
    web_lite = settings.web_lite_path
    if settings.serve_web_lite and web_lite.exists():

        @app.get("/", include_in_schema=False)
        async def root():
            return FileResponse(web_lite)

        @app.get("/chat.html", include_in_schema=False)
        async def chat_page():
            return FileResponse(web_lite)
    else:

        @app.get("/", include_in_schema=False)
        async def root():
            return RedirectResponse("/docs")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_server.main:app", host="0.0.0.0", port=8000, reload=True)
