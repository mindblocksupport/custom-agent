"""calc-mcp · MCP server (stdio)

启动方式:
    uv run --package calc-mcp calc-mcp
    # 或
    python -m calc_mcp.server

工具:
    - calculator(expression: str) -> str
"""

import math

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("calc-mcp")


# 允许的安全函数白名单 (移除 __builtins__)
_ALLOWED = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
_ALLOWED.update({"abs": abs, "round": round, "min": min, "max": max, "sum": sum})


@mcp.tool()
def calculator(expression: str) -> str:
    """Calculate a mathematical expression.

    Supports +, -, *, /, **, sqrt, sin, cos, tan, log, exp, pi, e,
    and Python math functions. Use for arithmetic, trigonometry, statistics.

    Args:
        expression: Math expression, e.g. '2 + 2 * 3', 'sqrt(16) + sin(pi/2)', 'log(100, 10)'

    Returns:
        Stringified numeric result, or an error message.
    """
    try:
        result = eval(expression, {"__builtins__": {}}, _ALLOWED)  # noqa: S307
        return f"{result}"
    except Exception as e:
        return f"Error evaluating expression: {type(e).__name__}: {e}"


def main() -> None:
    """stdio MCP server entry point。"""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
