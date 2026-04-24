"""ToolRegistry 启动初始化

设计:
- 进程启动时一次性初始化全局 registry
- 所有工具走 MCP 协议 (子进程, stdio JSON-RPC)
- 通过 FastAPI lifespan 调用 setup() / teardown()
- 路由通过 `Depends(get_registry)` 拿 registry (后续可改成 per-tenant)

后续:
- 从 DB / config 加载 MCP server 列表 (而非硬编码)
- 加 SSE / Streamable HTTP transport (远程 MCP)
- 加重连 + 健康探测
"""

import logging
import os
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass, field

from agent_core import ToolRegistry
from agent_core.mcp import MCPSubprocessClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MCPServerSpec:
    """一个 MCP server 的启动声明。"""

    label: str
    command: list[str]
    requires_acl: bool = False               # Day 2 P0 #3: True 触发 _principal_token 注入
    extra_env: dict[str, str] = field(default_factory=dict)


# MVP 阶段硬编码;生产环境改为从 DB / config / env 加载
MCP_SERVERS: list[MCPServerSpec] = [
    MCPServerSpec(
        label="time-mcp",
        command=[sys.executable, "-m", "time_mcp.server"],
    ),
    MCPServerSpec(
        label="calc-mcp",
        command=[sys.executable, "-m", "calc_mcp.server"],
    ),
    MCPServerSpec(
        label="web-search-mcp",
        command=[sys.executable, "-m", "web_search_mcp.server"],
    ),
    MCPServerSpec(
        label="rag-mcp",
        command=[sys.executable, "-m", "rag_mcp.server"],
        requires_acl=True,                    # 触达租户数据 → 必须 JWT 验签
    ),
]


class ToolBootstrap:
    """全局工具初始化协调器。

    生命周期与 api-server 进程绑定 (FastAPI lifespan):
        bootstrap = ToolBootstrap()
        await bootstrap.setup()
        ...
        await bootstrap.teardown()
    """

    def __init__(self, servers: list[MCPServerSpec] | None = None) -> None:
        self.registry = ToolRegistry()
        self._stack = AsyncExitStack()
        self._servers = servers if servers is not None else MCP_SERVERS

    async def setup(self) -> None:
        for spec in self._servers:
            await self._add_mcp_server(spec)

    async def _add_mcp_server(self, spec: MCPServerSpec) -> None:
        """启动一个 MCP server 子进程并把它的工具注册进 registry。

        失败容忍: 单个 server 起不来不影响其他;打日志继续。
        Day 2 P0 #3: requires_acl 的 server 接收 RAG_MCP_JWT_SECRET (验签用),
        list_tools 返回的所有 Tool 都打 requires_acl=True (Executor 注入 token).
        """
        try:
            child_env = self._build_child_env(spec)
            client = MCPSubprocessClient(
                spec.command, env=child_env, requires_acl=spec.requires_acl,
            )
            await self._stack.enter_async_context(client)
            tools = await client.list_tools()
            for t in tools:
                self.registry.register(t)
            logger.info(
                "MCP[%s] tools registered: %s (requires_acl=%s)",
                spec.label, [t.name for t in tools], spec.requires_acl,
            )
        except Exception:
            logger.exception(
                f"Failed to bring up MCP server '{spec.label}'; continuing without it"
            )

    def _build_child_env(self, spec: MCPServerSpec) -> dict[str, str]:
        """传给子进程的 env. requires_acl 的 server 自动透传 JWT 密钥."""
        env = dict(os.environ)
        env.update(spec.extra_env)
        if spec.requires_acl:
            secret = os.environ.get("RAG_MCP_JWT_SECRET")
            if not secret:
                raise RuntimeError(
                    f"MCP[{spec.label}] requires_acl=True but RAG_MCP_JWT_SECRET unset. "
                    "Generate one: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                )
            env["RAG_MCP_JWT_SECRET"] = secret
            prev = os.environ.get("RAG_MCP_JWT_SECRET_PREV")
            if prev:
                env["RAG_MCP_JWT_SECRET_PREV"] = prev
        return env

    async def teardown(self) -> None:
        await self._stack.aclose()
