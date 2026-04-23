# web-search-mcp

MCP server (stdio) 提供 `web_search` 工具。

## 工具

| 工具 | 描述 |
|---|---|
| `web_search(query: str)` | Web 搜索;按 `SEARCH_BACKEND` 路由到 stub / tavily / serpapi |

## 配置 (`.env` 中)

```bash
# 默认 stub
SEARCH_BACKEND=stub

# 用 Tavily (推荐 - 专为 LLM 设计, $0.005/query)
SEARCH_BACKEND=tavily
TAVILY_API_KEY=tvly-xxxx

# 或 SerpAPI (传统全 SERP)
SEARCH_BACKEND=serpapi
SERPAPI_API_KEY=xxxx
```

## 后续

- 加 cache (相同 query 24h 复用)
- 加 SearXNG 自建后端 (数据不出域)
- 加 site:domain 过滤 / 时间过滤
- 接深度爬取 (Firecrawl / Reader API)
