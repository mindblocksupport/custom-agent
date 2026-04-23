"""健康检查 endpoints"""

from fastapi import APIRouter

from api_server import __version__

router = APIRouter()


@router.get("/")
async def health() -> dict:
    """Liveness check."""
    return {"status": "ok", "version": __version__}


@router.get("/ready")
async def ready() -> dict:
    """Readiness check - 后续加 DB/Redis/LLM Gateway 探测。"""
    # TODO: probe DB / Redis / a small LLM call
    return {"status": "ready"}
