"""FastAPI 依赖注入

- get_registry: 从 app.state 拿 ToolRegistry
- get_token_provider: 给当前 Principal 现签 JWT (Day 2 P0 #3)
"""

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request

from agent_core import ToolRegistry

from api_server.acl import Principal, sign_principal_token
from api_server.auth import verify_api_key


def get_registry(request: Request) -> ToolRegistry:
    """从 app.state 取共享 ToolRegistry。

    后续多租户:
        tenant_id = request.state.tenant_id
        return per_tenant_registry(tenant_id)
    """
    registry: ToolRegistry | None = getattr(request.app.state, "registry", None)
    if registry is None:
        raise HTTPException(503, "ToolRegistry not initialized")
    return registry


def get_token_provider(
    principal: Principal = Depends(verify_api_key),
) -> Callable[[], str]:
    """返回 () -> JWT 的 lambda. 每次调用现签一个新 token (60s TTL).

    给 agent_core.run_agent 的 token_provider 参数, Executor 在调 requires_acl
    工具时自动注入. LLM/agent 永远看不到 token (schema 已剥, 流式事件用原 args).
    """
    return lambda: sign_principal_token(principal)
