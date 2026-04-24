.PHONY: install dev backend frontend infra test lint format clean help

help: ## 显示所有命令
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## 安装所有 workspace 包 + dev 依赖
	@echo "==> Installing Python workspace (uv)..."
	uv sync --all-packages
	@echo "==> Installing frontend (npm) [optional]..."
	@if [ -d apps/web-console ] && [ -f apps/web-console/package.json ]; then \
		cd apps/web-console && npm install --silent || echo "(frontend skipped)"; \
	fi
	@echo "==> Done. Try 'make backend'."

backend: ## 启动 api-server (http://localhost:8000) - 启动时拉起所有 MCP 子进程
	uv run --package api-server uvicorn api_server.main:app \
		--reload --port 8000 --host 0.0.0.0 \
		--reload-dir services/api-server/src \
		--reload-dir services/agent-core/src \
		--reload-dir services/gateway/src \
		--reload-dir packages/schemas/src

mcp-time: ## 单独跑 time-mcp server (调试用)
	uv run --package time-mcp time-mcp

mcp-calc: ## 单独跑 calc-mcp server (调试用)
	uv run --package calc-mcp calc-mcp

mcp-search: ## 单独跑 web-search-mcp server (调试用)
	uv run --package web-search-mcp web-search-mcp

# ===== SDK =====
sdk-py-test: ## Python SDK 测试
	uv run --package custom-agent-sdk pytest packages/sdk-python/tests -q

sdk-py-example: ## 跑 Python SDK quickstart (需 backend 在 8000)
	CUSTOM_AGENT_API_KEY=$${API_KEY:-dev-key-change-me} \
		uv run python packages/sdk-python/examples/quickstart.py

sdk-ts-install: ## 装 TypeScript SDK 依赖
	cd packages/sdk-typescript && npm install

sdk-ts-test: ## TypeScript SDK 测试
	cd packages/sdk-typescript && npm test

sdk-ts-build: ## 编译 TypeScript SDK 到 dist/
	cd packages/sdk-typescript && npm run build

sdk-ts-example: ## 跑 TypeScript SDK quickstart (需 backend 在 8000)
	cd packages/sdk-typescript && \
		CUSTOM_AGENT_API_KEY=$${API_KEY:-dev-key-change-me} \
		npm run example

frontend: ## 启动 Next.js 控制台 (http://localhost:3000)
	cd apps/web-console && npm run dev

frontend-install: ## 装 web-console 依赖
	cd apps/web-console && npm install

frontend-build: ## 构建生产版本
	cd apps/web-console && npm run build

frontend-typecheck: ## 仅类型检查
	cd apps/web-console && npm run typecheck

dev: ## 同时启动前后端 (需要 GNU make 4+)
	@$(MAKE) -j2 backend frontend

# ============================================================
# 一键启动 (推荐!)
# ============================================================
up: ## 一键: 起 docker + infra + 跑迁移 + 装依赖 + 启前后端 (Ctrl-C 全部停)
	@docker info >/dev/null 2>&1 || { \
	  echo "==> docker 未启动, 自动拉起..."; \
	  if [ -d "/Applications/OrbStack.app" ]; then open -a OrbStack; \
	  elif [ -d "/Applications/Docker.app" ]; then open -a Docker; \
	  elif command -v colima >/dev/null 2>&1; then colima start; \
	  else echo "❌ 没找到 Docker Desktop / OrbStack / colima, 装一个再来"; exit 1; \
	  fi; \
	  echo "==> 等 docker daemon 就绪 (最多 90s)..."; \
	  for i in $$(seq 1 90); do docker info >/dev/null 2>&1 && break; sleep 1; printf "."; done; echo ""; \
	  docker info >/dev/null 2>&1 || { echo "❌ docker 起不来, 手动开一下"; exit 1; }; \
	  echo "==> docker ready"; \
	}
	@$(MAKE) infra
	@echo "==> waiting for postgres..."
	@until docker compose -f infra/docker-compose.yml exec -T postgres pg_isready -U agent >/dev/null 2>&1; do sleep 1; done
	@$(MAKE) migrate
	@echo "==> syncing python deps..."
	@uv sync --all-packages --extra pdf >/dev/null
	@echo "==> installing frontend deps if missing..."
	@if [ ! -d apps/web-console/node_modules ]; then cd apps/web-console && npm install --silent; fi
	@echo "==> 清理可能残留的旧进程..."
	@for port in 8000 3000; do \
	  pids=$$(lsof -ti:$$port 2>/dev/null); \
	  if [ -n "$$pids" ]; then \
	    echo "  killing pid(s) on :$$port: $$pids"; \
	    kill -9 $$pids 2>/dev/null || true; \
	  fi; \
	done
	-@sleep 1
	@echo ""
	@echo "==============================================="
	@echo "  Backend:  http://localhost:8000  (docs: /docs)"
	@echo "  Frontend: http://localhost:3000"
	@echo "  PG:       :5432  Redis: :6379"
	@echo "  API key:  dev-key-change-me"
	@echo "==============================================="
	@$(MAKE) -j2 backend frontend

down: ## 停止整个工程 (前后端进程 + docker)
	@for port in 8000 3000; do \
	  pids=$$(lsof -ti:$$port 2>/dev/null); \
	  if [ -n "$$pids" ]; then \
	    echo "  killing pid(s) on :$$port: $$pids"; \
	    kill -9 $$pids 2>/dev/null || true; \
	  fi; \
	done
	@docker compose -f infra/docker-compose.yml down
	@echo "==> stopped"

migrate: ## 跑所有 migration (幂等, 已存在的表跳过)
	@for f in infra/migrations/*.sql; do \
	  echo "  applying $$(basename $$f)"; \
	  docker compose -f infra/docker-compose.yml exec -T postgres \
	    psql -U agent -d agent -q -f /docker-entrypoint-initdb.d/$$(basename $$f) >/dev/null 2>&1 || true; \
	done
	@echo "==> migrations applied"

smoke: ## 端到端 smoke: 上传 README + 检索 + 打印 hits (要 backend 跑着)
	@echo "==> uploading README.md..."
	@JOB=$$(curl -sS -X POST http://localhost:8000/v1/kb/upload \
	  -H "Authorization: Bearer dev-key-change-me" \
	  -F "file=@README.md" -F "collection=default" | jq -r '.job_id') && \
	  echo "  job: $$JOB" && \
	  echo "==> waiting for ingest..." && \
	  for i in 1 2 3 4 5 6 7 8 9 10; do \
	    S=$$(curl -sS http://localhost:8000/v1/kb/jobs/$$JOB \
	      -H "Authorization: Bearer dev-key-change-me" | jq -r '.status'); \
	    echo "  status: $$S"; [ "$$S" = "done" ] && break; sleep 2; \
	  done
	@echo "==> test-search:"
	@curl -sS -X POST http://localhost:8000/v1/kb/test-search \
	  -H "Authorization: Bearer dev-key-change-me" \
	  -H "Content-Type: application/json" \
	  -d '{"query":"this project default LLM","k":3}' | jq

# ============================================================
# 拆开来用 (调试时用)
# ============================================================
infra: ## 启动基础设施 (Postgres + Redis), 首次自动跑 RAG 迁移
	docker compose -f infra/docker-compose.yml up -d
	@echo "==> Postgres on :5432 (pgvector), Redis on :6379"
	@echo "==> 首次启动 docker-entrypoint 自动跑 infra/migrations/*.sql"

infra-down: ## 停止基础设施
	docker compose -f infra/docker-compose.yml down

infra-reset: ## ⚠️ 删除 PG 数据卷 + 重启 (会重新跑迁移)
	docker compose -f infra/docker-compose.yml down -v
	docker compose -f infra/docker-compose.yml up -d
	@echo "==> volumes wiped, migrations re-applied"

# ===== RAG (Day 9) =====
rag-init: ## 手动重跑 RAG 迁移 (PG 已起着时用) — 等价 make migrate
	@$(MAKE) migrate

rag-status: ## 显示 rag-core 配置
	uv run --package rag-core rag status

rag-ingest: ## ingest 单文件: make rag-ingest FILE=README.md
	uv run --package rag-core rag ingest $(FILE)

rag-query: ## 检索: make rag-query Q="rag-core 怎么洗数据"
	uv run --package rag-core rag query "$(Q)"

rag-demo: ## Day 9 端到端: ingest README + 查问题 (要求 infra 已起)
	@echo "==> rag-demo · 用 hash backend (无需 GPU)"
	uv run --package rag-core rag ingest README.md
	uv run --package rag-core rag query "这个项目是干什么的"

rag-test: ## rag-core 单元测试 (chunking + hash embedding, 无需 DB)
	uv run --package rag-core pytest packages/rag-core/tests -q

rag-eval: ## Day 10 eval (in-memory, A/B dense vs bm25 vs hybrid vs +rerank)
	uv run --package rag-core python eval/run.py

rag-eval-strict: ## Day 14 CI 卡口 (违阈 exit 1, 写 JSON 报告)
	uv run --with pyyaml --package rag-core python eval/run.py \
		--strict --profile ci --json-out eval/results.json

rag-eval-nightly: ## Day 14 nightly (真模型 + 严苛阈值; 需 RAG_EMBED_BACKEND=qwen3 etc.)
	uv run --with pyyaml --package rag-core python eval/run.py \
		--strict --profile nightly --json-out eval/results.json

rag-review: ## Day 14 人工 review CLI (改 generated → reviewed.jsonl)
	uv run --package rag-core python eval/review.py \
		--in eval/qa_generated.jsonl --out eval/qa_reviewed.jsonl --max 50

test: ## 跑所有 workspace 包的测试
	uv run pytest -q

test-pkg: ## 跑指定 package 的测试: make test-pkg PKG=agent-core
	uv run --package $(PKG) pytest -q

lint: ## 全工程代码检查
	uv run ruff check . && uv run ruff format --check .

format: ## 代码格式化
	uv run ruff format . && uv run ruff check --fix .

license-scan: ## ⚠️ 扫描依赖 license, 见到 AGPL/GPL 直接红灯 (L37 §8.9)
	uv run --with pip-licenses pip-licenses --format=plain --fail-on="AGPL-3.0;AGPL-3.0+;GNU Affero General Public License v3;GNU Affero General Public License v3 or later"

tree: ## 显示工程结构
	@find . -type d \
		\( -name node_modules -o -name .next -o -name __pycache__ -o -name .venv -o -name .pytest_cache -o -name .ruff_cache \) \
		-prune -o -type f -print | grep -v "^\./\." | sort

clean: ## 清理生成物
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .venv apps/web-console/node_modules apps/web-console/.next
