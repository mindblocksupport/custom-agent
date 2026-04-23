# rag-core

RAG 核心库 (L37 plan v1.1)。包含切分 / embedding / pgvector 存储 / 检索 / ingest pipeline / CLI。

## 快速开始

### 1. 起 pg + 跑迁移
```bash
make infra                # 起 postgres (pgvector 镜像)
                          # docker-entrypoint-initdb.d 自动跑 001_rag.sql
```
若 PG 已起着且需要手动重跑迁移:
```bash
docker compose -f infra/docker-compose.yml exec postgres \
  psql -U agent -d agent -f /docker-entrypoint-initdb.d/001_rag.sql
```

### 2. 装库
```bash
uv sync --all-packages              # 默认 hash backend, 不下模型
# 或: uv sync --all-packages --extra embed   # 装 sentence-transformers + torch
```

### 3. CLI
```bash
uv run rag status                                       # 看配置
uv run rag ingest README.md                             # 单文件 ingest
uv run rag query "rag-core 怎么洗数据"                  # 检索 top-5
```

切换到真 Qwen3:
```bash
RAG_EMBED_BACKEND=qwen3 uv run rag ingest README.md
```

## 模块
| 路径 | 职责 |
|---|---|
| `chunking/` | recursive (Day 9) → parent_child + contextual (Day 12) |
| `embedding/` | hash (CI) / qwen3 (生产) |
| `storage/pgvector_store.py` | upsert (含增量) + ACL-aware dense_search |
| `retrieval/` | dense (Day 9) → bm25 + RRF (Day 10) |
| `ingest/pipeline.py` | file → parse → chunk → embed → store |
| `cli/main.py` | `rag ingest / query / status` |

## ACL 铁律 (L37 §8.2)
- `tenant_id` / `principals` 由 caller 在调用时传, **不允许 agent 在 search_kb 工具参数里传**
- pgvector_store 在 SQL 层强制 `tenant_id = ?` AND `acl && principals`
- rag-mcp server (Day 11) 从 MCP context 注入这两个字段
