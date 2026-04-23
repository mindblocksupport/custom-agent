"""API Server · L9 接入层

负责:
- HTTP / SSE / OpenAPI 兼容
- API Key 鉴权 (L8)
- 加载内置工具到 ToolRegistry
- 调用 agent_core.run_agent()
- 包装 SSE 输出
"""

__version__ = "0.1.0"
