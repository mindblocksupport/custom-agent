# rag-mcp

MCP server 暴露 `search_kb` 工具。Day 9 占位骨架, Day 11 接入 api-server registry。

## 启动 (调试)
```bash
uv run --package rag-mcp rag-mcp
```

## ACL 注入 (关键)
- `tenant_id` 来自 env `RAG_MCP_TENANT_ID` (api-server spawn 时注入)
- `principals` 来自 env `RAG_MCP_PRINCIPALS` (逗号分隔)
- agent 在 tool args 中**不能**传这两字段; `filters` 中的系统字段会被 strip

Day 11 改造: 把 tenant_id/actor_id 改为 MCP context per-call 注入 (需要 api-server 配合改 spawn 协议)。
