# calc-mcp

MCP server (stdio) 提供 `calculator` 工具。

## 工具

| 工具 | 描述 |
|---|---|
| `calculator(expression: str)` | 安全求值数学表达式（Python `math` 模块 + abs/round/min/max/sum） |

## 安全

`eval` 已禁用 `__builtins__`,只允许 `math.*` 白名单函数。
但**如果未来要加危险函数 (file IO / network) 必须沙箱化** (见 docs/16 §5)。
