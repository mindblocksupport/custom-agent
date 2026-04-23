# Custom Agent · 企业级 Agent 平台

> MVP v0.2 · 2026-04-22 · **monorepo** + uv workspace

## 工程结构

```
custom_agent/
├── docs/                       # 36 个架构文档
│
├── services/                   # 各业务服务 (独立 package, 独立部署)
│   ├── api-server/             # L9 接入层 (HTTP/SSE)
│   ├── agent-core/             # L5 Agent 运行时 (ReAct + 工具 + 护栏)
│   ├── gateway/                # L2 LLM Gateway (LiteLLM 包装)
│   └── tools-builtin/          # L4 内置工具集
│
├── packages/                   # 跨服务共享
│   └── schemas/                # Pydantic 数据契约
│
├── apps/                       # 用户前端
│   ├── web-lite/               # 单文件 chat.html (无 build)
│   └── web-console/            # Next.js 控制台 (后续)
│
├── infra/                      # 基础设施
│   ├── docker-compose.yml      # Postgres + Redis (后续启用)
│   └── Dockerfile.api-server
│
├── pyproject.toml              # workspace 根 (uv)
├── Makefile                    # make install/backend/test/...
├── .env / .env.example
└── README.md (本文件)
```

## 5 分钟跑通

```bash
# 1. 装依赖
make install

# 2. 配置 (至少一个 LLM key)
cp .env.example .env
# 编辑 .env,填 DEEPSEEK_API_KEY 或 OPENAI_API_KEY 或 ANTHROPIC_API_KEY

# 3. 启动
make backend

# 4. 浏览器打开
open http://localhost:8000
```

## 服务依赖图

```
              ┌─────────────────┐
              │   api-server    │  ← L9 接入 (FastAPI + SSE)
              └────┬──────┬─────┘
                   │      │
       ┌───────────┘      └───────────┐
       ▼                              ▼
┌────────────┐             ┌──────────────────┐
│agent-core  │             │  tools-builtin   │  ← L4 内置工具
│ (L5 ReAct) │ ──────►     │  (注册到 registry)│
└────┬───────┘             └────────┬─────────┘
     │                              │
     │      ┌───────┐               │
     ├─────►│gateway│  ← L2 (LiteLLM)
     │      └───┬───┘               │
     │          │                   │
     ▼          ▼                   ▼
  ┌─────────────────────────────────┐
  │         schemas (共享数据契约)    │
  └─────────────────────────────────┘
                │
                ▼
       外部 LLM (DeepSeek/Claude/GPT/...)
```

## 各层 OSS 选型

| 层 | 当前 | 后续 (按 docs/16) |
|---|---|---|
| L2 LLM Gateway | **LiteLLM** ✅ | + 缓存 / 路由 / failover |
| L3 RAG | ❌ | RAGFlow + Qdrant + bge-m3 |
| L4 工具 | 自研 + 3 内置 | + MCP SDK + 沙箱 |
| L5 Agent runtime | 手写 ReAct | **LangGraph 1.0** |
| L6 编排 / 长任务 | ❌ | Temporal |
| L7 观测 | log only | **Langfuse + OpenLLMetry** |
| L8 安全 | API Key | SSO + RBAC + Casbin |
| L13 Memory | ❌ | mem0 / Letta / Zep |
| Eval | ❌ | Promptfoo + DeepEval |
| Guardrails | ❌ | NeMo Guardrails + Llama Guard 4 |

## 常用命令

```bash
make help                # 列所有命令
make install             # 装所有依赖
make backend             # 启动 api-server
make frontend            # 启动 Next.js (后续)
make infra               # docker-compose 起 Postgres+Redis
make test                # 跑所有测试
make test-pkg PKG=agent-core   # 跑单个 package 的测试
make lint / format       # 代码检查 / 格式化
make tree                # 显示工程结构
make clean               # 清理生成物
```

## 单个服务独立开发

```bash
# 只装 agent-core 及其依赖
uv sync --package agent-core

# 跑 agent-core 的测试
uv run --package agent-core pytest

# 在 agent-core 里加包
cd services/agent-core
uv add some-lib
```

## 下一步演进 (按 ROI 排序)

1. **接 Langfuse 观测** (30 min) — 每次调用 / 每个 token / 每分钱可视化
2. **用 LangGraph 替手写 ReAct** (1 day) — 加 checkpointer / HITL / 子 Agent
3. **接 mem0 + Postgres** (1 day) — 对话持久化 + 用户记忆
4. **加 RAG** (半天) — 接你公司文档
5. **工具走 MCP** (1 day) — 标准化、可热插拔

## 文档导航

先读 [`docs/00-architecture-overview.md`](docs/00-architecture-overview.md),里面有 36 个文档的完整地图。
