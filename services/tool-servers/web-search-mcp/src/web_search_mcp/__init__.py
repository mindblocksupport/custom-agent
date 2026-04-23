"""web-search-mcp · MCP server (stdio)

提供 web_search 工具(MVP 是 stub),通过 MCP 协议暴露给 Agent 平台。

后续接入真实 search backend:
- Tavily (https://tavily.com): 专为 LLM 设计的搜索 API,$0.005/query
- SerpAPI (https://serpapi.com): 全 SERP 抓取
- Bing Search API
- 自建 SearXNG (开源元搜索)
"""
