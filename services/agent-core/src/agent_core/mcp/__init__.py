"""MCP (Model Context Protocol) 客户端

把外部 MCP server (子进程或远程 HTTP) 的工具适配为本地 Tool dataclass,
注册进 ToolRegistry,Agent loop 透明调用。

对应文档: docs/04-tools-and-skills.md §3
"""

from agent_core.mcp.client import MCPSubprocessClient

__all__ = ["MCPSubprocessClient"]
