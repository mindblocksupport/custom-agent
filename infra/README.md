# infra · 基础设施配置

## docker-compose.yml

```bash
docker compose -f infra/docker-compose.yml up -d   # 起 postgres + redis
docker compose -f infra/docker-compose.yml down
```

包含:
- **postgres** 16 (业务 DB,后续放对话历史 / 用户 / 审计)
- **redis** 7 (限流 / 缓存 / 队列)
- **langfuse** v2 (默认注释掉,启用步骤见 yml 内)

## Caddyfile

生产部署参考 - **拆开静态前端托管 vs 业务 API**:

```bash
# 步骤
1. workspace 根的 .env: SERVE_WEB_LITE=false
2. make backend                  # api-server 只做 API
3. caddy run --config infra/Caddyfile  # Caddy 托管前端 + 反代 API
4. 浏览器: http://localhost
```

为什么要拆?
- ⚡ Caddy/Nginx 静态文件**比 Python 快 10-100×**
- 🛡️ api-server 不再 serve 文件,**攻击面缩小**
- 🌍 生产可加 CDN 在 Caddy 之前,**全球加速**
- 🔐 Caddy 自动 Let's Encrypt 证书,api-server 不必碰 HTTPS
- 🚀 api-server 重启时**前端不受影响**

## Dockerfile.api-server

```bash
docker build -f infra/Dockerfile.api-server -t custom-agent-api .
docker run -p 8000:8000 --env-file .env custom-agent-api
```
