# time-mcp

MCP server (stdio) 提供 `get_time` 工具。**试点**:验证我们 Agent 平台对 MCP 协议的支持。

## 启动 (调试用)

```bash
uv run --package time-mcp time-mcp
# 等待 stdin 上的 JSON-RPC 请求
```

实际生产由 `api-server` 启动时通过 `MCPSubprocessClient` 拉起子进程。

## 提供的工具

| 工具 | 描述 |
|---|---|
| `get_time(timezone="Asia/Shanghai")` | 返回指定 IANA 时区的当前时间 |

## 后续

参考 docs/04-tools-and-skills.md §3,
拆更多内置工具为独立 MCP server (`calc-mcp` / `web-search-mcp` / 业务系统 MCP server 等)。
