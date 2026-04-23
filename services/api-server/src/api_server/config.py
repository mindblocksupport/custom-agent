"""配置 · 集中管理所有环境变量

对应文档: docs/11-model-strategy.md / docs/21-finops-cost-management.md
"""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# 找到 workspace 根目录(往上找 .env)
_WORKSPACE_ROOT: Path | None = None


def _find_workspace_root() -> Path:
    """从当前文件向上找,直到找到含 pyproject.toml 且声明 [tool.uv.workspace] 的目录。"""
    global _WORKSPACE_ROOT
    if _WORKSPACE_ROOT is not None:
        return _WORKSPACE_ROOT
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        py = parent / "pyproject.toml"
        if py.exists() and "tool.uv.workspace" in py.read_text(encoding="utf-8"):
            _WORKSPACE_ROOT = parent
            return parent
    # fallback: parent[5] = workspace root by structure
    _WORKSPACE_ROOT = here.parents[5]
    return _WORKSPACE_ROOT


WORKSPACE_ROOT = _find_workspace_root()


class Settings(BaseSettings):
    """API Server 配置。.env 在 workspace 根。"""

    model_config = SettingsConfigDict(
        env_file=str(WORKSPACE_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ===== App =====
    env: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # ===== Auth (MVP: 单一 API Key;后续 SSO/OIDC) =====
    api_key: str = "dev-key-change-me"

    # ===== LLM (L11 模型战略) =====
    default_model: str = "deepseek/deepseek-chat"
    fallback_models: list[str] = []

    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    deepseek_api_key: str | None = None
    gemini_api_key: str | None = None
    dashscope_api_key: str | None = None  # 通义千问
    moonshot_api_key: str | None = None
    zai_api_key: str | None = None  # 智谱 GLM

    # ===== Agent 防失控 (L5 §5 五道闸门) =====
    max_steps: int = 15
    max_cost_usd: float = 0.5
    max_tool_consecutive_errors: int = 3

    # ===== Persistence (后续启用) =====
    database_url: str | None = None
    redis_url: str | None = None

    # ===== Observability (L7 - Langfuse 后续接入) =====
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "http://localhost:3001"

    # ===== Web Lite (apps/web-lite/chat.html) =====
    # 默认 True (MVP 方便) ;生产环境置 False, 用 Caddy/Nginx/CDN 独立托管 (见 infra/Caddyfile)
    serve_web_lite: bool = True
    web_lite_path: Path = WORKSPACE_ROOT / "apps" / "web-lite" / "chat.html"

    def setup_litellm_env(self) -> None:
        """把 API key 注入环境变量供 LiteLLM 自动识别。"""
        import os

        for var, val in [
            ("ANTHROPIC_API_KEY", self.anthropic_api_key),
            ("OPENAI_API_KEY", self.openai_api_key),
            ("DEEPSEEK_API_KEY", self.deepseek_api_key),
            ("GEMINI_API_KEY", self.gemini_api_key),
            ("DASHSCOPE_API_KEY", self.dashscope_api_key),
            ("MOONSHOT_API_KEY", self.moonshot_api_key),
            ("ZAI_API_KEY", self.zai_api_key),
        ]:
            if val:
                os.environ[var] = val


settings = Settings()
settings.setup_litellm_env()
