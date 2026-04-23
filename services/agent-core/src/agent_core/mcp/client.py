"""MCP stdio 子进程客户端

设计:
- 每个 MCP server = 一个长驻子进程,通过 stdio JSON-RPC 通信
- MCPSubprocessClient 是 async context manager,生命周期与 api-server 进程绑定
- list_tools() 把远端工具描述包装成本地 Tool dataclass,直接注册到 ToolRegistry
- 调用时透明转发到子进程

后续:
- 加 SSE / Streamable HTTP transport (远程 MCP)
- 加重连 + 健康探测
- 加 OAuth 2.1 (按 docs/04 §3.3)
- 加 sandbox (按 docs/04 §9 + L16 §5)
"""

from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent_core.tools.protocol import Tool


class MCPSubprocessClient:
    """连接到一个 MCP server (stdio 子进程)。

    用法:
        async with MCPSubprocessClient(["python", "-m", "time_mcp.server"]) as client:
            tools = await client.list_tools()  # → list[Tool]
            for t in tools:
                registry.register(t)
    """

    def __init__(
        self,
        command: list[str],
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        if not command:
            raise ValueError("command must be a non-empty list")
        self.command = command
        self.cwd = cwd
        self.env = env
        self._stack = AsyncExitStack()
        self._session: ClientSession | None = None

    async def __aenter__(self) -> "MCPSubprocessClient":
        params = StdioServerParameters(
            command=self.command[0],
            args=list(self.command[1:]),
            cwd=self.cwd,
            env=self.env,
        )
        read, write = await self._stack.enter_async_context(stdio_client(params))
        session = ClientSession(read, write)
        self._session = await self._stack.enter_async_context(session)
        await session.initialize()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self._stack.aclose()
        self._session = None

    @property
    def session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError("MCPSubprocessClient not entered (use 'async with')")
        return self._session

    async def list_tools(self) -> list[Tool]:
        """列出 server 提供的工具,转成本地 Tool dataclass。"""
        result = await self.session.list_tools()
        return [self._wrap(t) for t in result.tools]

    def _wrap(self, mcp_tool: Any) -> Tool:
        """把 MCP tool descriptor → Tool dataclass。"""
        name: str = mcp_tool.name
        description: str = mcp_tool.description or ""
        parameters: dict[str, Any] = mcp_tool.inputSchema or {
            "type": "object",
            "properties": {},
        }

        async def execute(**kwargs: Any) -> str:
            result = await self.session.call_tool(name, arguments=kwargs)
            # MCP 返回 list[TextContent | ImageContent | EmbeddedResource]
            # MVP: 拼接所有 text content
            parts: list[str] = []
            for c in result.content:
                text = getattr(c, "text", None)
                if text is not None:
                    parts.append(text)
                else:
                    parts.append(str(c))
            return "\n".join(parts) if parts else ""

        return Tool(
            name=name,
            description=description,
            parameters=parameters,
            execute=execute,
        )
