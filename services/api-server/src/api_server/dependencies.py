"""FastAPI 依赖注入

- get_registry: 从 app.state 拿 ToolRegistry (单例;后续 per-tenant 拓展点)
"""

from fastapi import HTTPException, Request

from agent_core import ToolRegistry


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
