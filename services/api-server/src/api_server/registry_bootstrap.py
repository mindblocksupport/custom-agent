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
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass

from agent_core import ToolRegistry
from agent_core.mcp import MCPSubprocessClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MCPServerSpec:
    """一个 MCP server 的启动声明。"""

    label: str
    command: list[str]


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
        """
        try:
            client = MCPSubprocessClient(spec.command)
            await self._stack.enter_async_context(client)
            tools = await client.list_tools()
            for t in tools:
                self.registry.register(t)
            logger.info(f"MCP[{spec.label}] tools registered: {[t.name for t in tools]}")
        except Exception:
            logger.exception(
                f"Failed to bring up MCP server '{spec.label}'; continuing without it"
            )

    async def teardown(self) -> None:
        await self._stack.aclose()
