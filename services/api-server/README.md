# api-server · L9 接入层

HTTP API + SSE 流式 + chat.html 静态托管。

## 启动

```bash
make backend
# 或
uv run --package api-server uvicorn api_server.main:app --reload --port 8000
```

## Endpoints

| Path | 用途 |
|---|---|
| `GET  /` | 重定向 chat.html (web-lite) |
| `GET  /chat.html` | Lite 前端 (apps/web-lite) |
| `GET  /docs` | OpenAPI Swagger |
| `GET  /health/` | Liveness |
| `GET  /health/ready` | Readiness |
| `POST /v1/chat/completions` | OpenAI 兼容 chat (SSE) |

## 配置

环境变量从 workspace 根的 `.env` 读取。详见 `.env.example`。

## 子模块

| 模块 | 职责 |
|---|---|
| `main.py` | FastAPI 入口 + CORS + 静态托管 |
| `config.py` | Settings (pydantic-settings) |
| `auth.py` | API Key 鉴权 |
| `observability.py` | 日志初始化 (后续接 Langfuse) |
| `registry_bootstrap.py` | 启动时装填 ToolRegistry |
| `routes/chat.py` | `/v1/chat/completions` |
| `routes/health.py` | `/health` |
