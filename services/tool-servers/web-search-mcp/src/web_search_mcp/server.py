"""web-search-mcp · MCP server (stdio)

启动方式:
    uv run --package web-search-mcp web-search-mcp
    # 或
    python -m web_search_mcp.server

工具:
    - web_search(query: str) -> str

环境变量:
    SEARCH_BACKEND   = stub (默认) | tavily | serpapi
    TAVILY_API_KEY   = if backend=tavily
    SERPAPI_API_KEY  = if backend=serpapi
"""

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("web-search-mcp")

_BACKEND = os.getenv("SEARCH_BACKEND", "stub").lower()


async def _stub(query: str) -> str:
    return (
        f"[Stub] Web search for: '{query}'\n\n"
        "Web search is not configured. Set SEARCH_BACKEND=tavily and TAVILY_API_KEY in .env "
        "(or SERPAPI_API_KEY).\n\n"
        "MVP: Tell the user you can't search the web yet."
    )


async def _tavily(query: str) -> str:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "Error: TAVILY_API_KEY not set"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": 5,
                    "include_answer": True,
                },
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json()
        out = []
        if ans := data.get("answer"):
            out.append(f"Answer: {ans}")
        for i, hit in enumerate(data.get("results", [])[:5], 1):
            out.append(f"\n[{i}] {hit.get('title', '')}\n  {hit.get('url', '')}\n  {hit.get('content', '')[:200]}")
        return "\n".join(out) if out else "No results."
    except Exception as e:
        return f"Tavily error: {type(e).__name__}: {e}"


async def _serpapi(query: str) -> str:
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        return "Error: SERPAPI_API_KEY not set"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                "https://serpapi.com/search.json",
                params={"q": query, "api_key": api_key, "num": 5},
            )
            r.raise_for_status()
            data: dict[str, Any] = r.json()
        out = []
        for i, hit in enumerate(data.get("organic_results", [])[:5], 1):
            out.append(f"[{i}] {hit.get('title', '')}\n  {hit.get('link', '')}\n  {hit.get('snippet', '')}")
        return "\n\n".join(out) if out else "No results."
    except Exception as e:
        return f"SerpAPI error: {type(e).__name__}: {e}"


@mcp.tool()
async def web_search(query: str) -> str:
    """Search the web for current information.

    Use ONLY for questions about events after your training cutoff,
    or for verifying facts that change frequently.

    Args:
        query: Concise, specific search query

    Returns:
        Search results (titles + URLs + snippets), or stub if not configured.
    """
    if _BACKEND == "tavily":
        return await _tavily(query)
    elif _BACKEND == "serpapi":
        return await _serpapi(query)
    else:
        return await _stub(query)


def main() -> None:
    """stdio MCP server entry point。"""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
