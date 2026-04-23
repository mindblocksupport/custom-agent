"""time-mcp · MCP server (stdio)

启动方式:
    # 直接 (workspace 内已注册 console script):
    uv run --package time-mcp time-mcp

    # 或 python 模块:
    python -m time_mcp.server

工具列表:
    - get_time(timezone: str = "Asia/Shanghai") -> str
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("time-mcp")


@mcp.tool()
def get_time(timezone: str = "Asia/Shanghai") -> str:
    """Get the current date and time in a given timezone.

    Use whenever the user asks about 'today', 'now', current date/time, day of week.

    Args:
        timezone: IANA timezone like 'Asia/Shanghai', 'America/New_York', 'UTC', 'Europe/London'

    Returns:
        Formatted datetime string with timezone abbreviation and weekday.
    """
    try:
        now = datetime.now(ZoneInfo(timezone))
        return now.strftime("%Y-%m-%d %H:%M:%S %Z (%A)")
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}. Use IANA tz like 'Asia/Shanghai'."


def main() -> None:
    """stdio MCP server entry point。"""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
