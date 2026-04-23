"""FastAPI 入口 · L9 接入层

对应文档: docs/09-access-layer.md
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from api_server.config import settings
from api_server.observability import setup_tracing
from api_server.registry_bootstrap import ToolBootstrap
from api_server.routes import chat, feedback, health

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期:
    - 启动:init logging → init ToolBootstrap (含 MCP 子进程) → 挂到 app.state
    - 关闭:teardown bootstrap (杀子进程)
    """
    setup_tracing()
    bootstrap = ToolBootstrap()
    try:
        await bootstrap.setup()
        app.state.bootstrap = bootstrap
        app.state.registry = bootstrap.registry
        logger.info(f"Active tools: {bootstrap.registry.names()}")
        yield
    finally:
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
