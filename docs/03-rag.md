# L3 · 知识 RAG 层（Pipeline 工程）

> 状态：**讨论中** · v0.2 重写版 · 2026-04-22 · 聚焦"采集 → 生成"完整流水线工程实现

## 0. 本层职责（与相邻层边界）

L3 是 **RAG pipeline 的工程实现层**——只回答"一份文档怎么变成可被检索的 chunk，一个 query 怎么变成带引用的答案"。

| 关注点 | 归属层 | 链接 |
|---|---|---|
| **上下文预算 / 注入位置 / quote-then-answer 模板** | L13 上下文工程 | [13-context-engineering.md](./13-context-engineering.md) |
| **专家经验如何成为 KB 语料（SECI / 知识捕获）** | L15 知识工程 | [15-knowledge-engineering.md](./15-knowledge-engineering.md) |
| **平台选型**（RAGFlow / Onyx / Qdrant / Milvus / pgvector） | L16 OSS 栈决策 | [16-opensource-stack-decision.md](./16-opensource-stack-decision.md) |
| **Faithfulness / 引用幻觉 / 拒答策略** | L18 幻觉处理 | [18-hallucination-handling.md](./18-hallucination-handling.md) |
| **租户级隔离实现**（namespace / VPC / KMS） | L24 多租户 | [24-multi-tenant-isolation.md](./24-multi-tenant-isolation.md) |
| **ACL 同步法律边界 / PII 脱敏义务 / 数据出境** | L25 合规 | [25-data-compliance-and-residency.md](./25-data-compliance-and-residency.md) |
| **联邦 / 跨租户 KB 共享** | L32 联邦知识 | [32-federated-knowledge.md](./32-federated-knowledge.md) |
| **从 trace 提炼 SFT/DPO 数据反哺 embedding/reranker** | L33 持续微调 | [33-continuous-finetuning-loop.md](./33-continuous-finetuning-loop.md) |
| **Ragas / TruLens / Recall@K / Faithfulness 指标定义** | L7 观测与评测 | [07-observability-and-eval.md](./07-observability-and-eval.md) |
| **当前坑（解析占 80% bad case 等）总账** | L10 当前问题与缓解 | [10-current-problems-and-mitigations.md](./10-current-problems-and-mitigations.md) |

**本层只做**：pipeline 13 个环节的工程实现、参数与 SOTA 选型、数据模型、增量策略、成本测算。

---

## 1. 完整 Pipeline（13 阶段）

```
┌─ 离线 ─────────────────────────────────────────────────────────┐
│ ① 采集 → ② 解析 → ③ 清洗 → ④ 切分 → ⑤ 嵌入 → ⑥ 索引          │
│                                  (+ ACL 同步)                  │
└────────────────────────────────────────────────────────────────┘
┌─ 在线 ─────────────────────────────────────────────────────────┐
│ ⑦ 查询改写 → ⑧ 三路混合召回 → ⑨ 重排 → ⑩ 上下文裁剪           │
│  HyDE/Step-back   Vector+BM25+KG   bge-r-v2  budget(L13)       │
│              ↓                                                  │
│ ⑪ 生成 → ⑫ 引用回填 → ⑬ 审核（Faithfulness L18）               │
└────────────────────────────────────────────────────────────────┘
```

阶段 ⑩-⑬ 复用 [L13](./13-context-engineering.md) §6 / [L18](./18-hallucination-handling.md) §3 模板，本文不重复。

---

## 2. ① 采集（Ingestion）

### 2.1 数据源与连接器

| 类别 | 源 | 连接器要点 | ACL 同步 |
|---|---|---|---|
| 文件 | PDF / DOCX / XLSX / PPTX / MD / HTML / 图片 | 上传 + S3/MinIO watch + SFTP | 文件夹权限继承 |
| 知识库 | **Confluence** / **Notion** / **SharePoint** / Lark Wiki / 飞书云文档 | 官方 OAuth + space/page webhook | space/page-level ACL **必须同步** |
| 代码 / 工单 | **GitLab** / GitHub / Jira / Linear | API + webhook | repo/project member |
| 数据库 | Postgres / MySQL / MongoDB / SQL Server | CDC（Debezium）+ 视图导出 | row-level → tag |
| 实时事件 | **Kafka** / Pulsar | consumer group | producer 系统签名 |
| 外部 | 网页 / 行业 API / RSS | crawler + 签名校验 | public-only |

### 2.2 ACL 同步是硬约束

**法律风险**（参 [L25](./25-data-compliance-and-residency.md) §3）：Confluence/SharePoint 抓走却没同步 ACL = 越权检索 = PII/商密泄露 = GDPR/PIPL 责任。

**实现要点**：
- 每个文档采集时**同时拉权限快照**，写入 `acl` 表
- 权限变更 webhook → 异步重建索引 metadata（**不重 embed**，只改 filter tag）
- 删除事件 → 立即软删（见 §13），物理清理 24h 内完成

### 2.3 采集模式

| 模式 | 适用 | 注意 |
|---|---|---|
| 全量初始化 | 首次接入 | 限并发，否则打爆源系统 API |
| 增量（watermark） | 日常 | 用 `updated_at` + 内容 hash 双保险 |
| webhook 实时 | Confluence/Notion | 消息去重 + 重试幂等 |
| Kafka 流式 | 业务事件 | 必须有 dead-letter queue |

---

## 3. ② 解析（Parsing）—— SOTA 工具矩阵 2026

> **解析效果决定 RAG 上限**。我们生产实际 bad case **80% 来自解析**（表格错位、阅读顺序乱、扫描件 OCR 失败），而非模型。

### 3.1 OmniDocBench (2025) 实测对比

| 工具 | 整体 Edit↓ | 中文 PDF | 表格 | 公式 | 部署 | 适用 |
|---|---|---|---|---|---|---|
| **MinerU 2.5** | **0.156** | ★★★★★ | ★★★★ | ★★★★ | 开源 / 1×A10 | **中文政企首选** |
| Marker | 0.281 | ★★★ | ★★★ | ★★★ | 开源 / CPU 可跑 | 通用、速度快 |
| **Docling** (IBM) | 0.298 | ★★★ | ★★★★ | ★★★ | 开源 / Apache | 企业稳态、流水线友好 |
| LlamaParse Premium | 0.231 | ★★★★ | ★★★★ | ★★★ | 商业 API | 海外 SaaS、不能私有化 |
| **Reducto** | 0.198 | ★★★★ | ★★★★★ | ★★★★ | 商业 | 复杂表格 / 财报最强 |
| Unstructured | 0.387 | ★★ | ★★ | ★★ | 开源 + 商业 | 多类型混合、prototype |
| PaddleOCR-VL | 0.245 | ★★★★ | ★★★ | ★★★ | 开源 | 扫描件 / 中文 OCR |
| **Vision LLM**（Qwen2.5-VL-72B / GPT-4o） | 0.18~0.22 | ★★★★ | ★★★★★ | ★★★★ | API / 8×H20 | 复杂图表、贵 |

**选型规则**：
- 中文 PDF 为主 → **MinerU 2.5 + Reducto 兜底复杂表**
- 海外、不私有化 → LlamaParse / Reducto
- 流水线集成、合规审计 → Docling
- 扫描件 → PaddleOCR-VL → 失败兜底 Vision LLM
- 财报 / 合同 / 招标书（表格高密）→ **Reducto / Vision LLM**（贵但值得）

### 3.2 典型挑战与对策

| 挑战 | 对策 |
|---|---|
| 双栏 / 多栏阅读顺序 | MinerU 内置版面分析；自检：句子完整性 + 标点闭合率 |
| 跨页表格 | parser 后处理合并；Reducto 内置 |
| 数学公式 | LaTeX 还原（MinerU / Marker 支持）；保留原图作为 fallback |
| 图表 | Vision LLM 描述 caption + alt-text，与原文绑定 chunk |
| 页眉页脚 / 水印 | 高频 n-gram 噪声过滤 |
| 扫描件低质 | 先 deskew + 增强 → OCR；多模型投票 |

---

## 4. ③ 清洗 / ④ 切分

### 4.1 清洗

- **去重**：document hash + chunk simhash；同源多版本保留最新 + 历史标 `superseded`
- **去噪**：n-gram 频率统计去页眉页脚；正则去 footer 法律声明
- **元数据抽取**：标题 / 时间 / 作者 / 部门 → `chunk.metadata`，**这是过滤金矿**（70% 检索可由元数据预筛收敛）
- **PII 脱敏**：Presidio / 阿里云内容安全（参 [L25](./25-data-compliance-and-residency.md) §6）；策略：**入库前脱敏 OR 入库带 tag 检索时脱敏**——按合规等级选

### 4.2 切分（Chunking）策略对比

| 策略 | 实现 | 优 | 劣 | 适用 |
|---|---|---|---|---|
| 固定窗口 | 按 token / 字符 | 简单 | 切断语义 | baseline |
| 语义切分 | 按标题 / 段落 / 句子边界 | 保留语义 | 长度不均 | **大多数场景默认** |
| 父子块 | 父 1500-2000t，子 200-400t；子检索父注入 | 精度+完整 | 实现复杂 | **生产推荐** |
| 滑动窗口 | overlap 15-20% | 长依赖 | 冗余 | 法律 / 合同 |
| **Late Chunking** (Jina) | 先 embed 全文 token，再分段 pool | 跨段语义保留 | 需要 long-ctx encoder | 长文档 |
| **Contextual Chunking** (Anthropic 2024) | 每 chunk 注入 LLM 生成的 50-100t **文档级上下文摘要** | **failure rate -49%~-67%**（实测） | LLM 调用成本，可用 prompt cache 摊销 | **质量优先场景必上** |
| Agentic Chunking | LLM 决定切点 | 极致质量 | 最贵 | 高价值小语料 |

**经验参数**：
- chunk_size：**400-800 tokens**（中文 800-1500 字）
- overlap：**10-15%**
- 父块：**子块 3-4 倍**
- Contextual chunking 上下文：**50-100 tokens**，由 Haiku/小模型生成 + prompt cache 文档体

---

## 5. ⑤ 嵌入（Embedding）2026 选型

| 模型 | 维度 | 中/英/多语 | MTEB / C-MTEB | 部署 | 价格参考 | 推荐 |
|---|---|---|---|---|---|---|
| **bge-m3** | 1024 | 中/英/多语 | C-MTEB 65+ | 开源 / 1×A10 | 自部署 | **中文私有化默认** |
| **Qwen3-Embedding-8B** | 4096 | 多语 | **MTEB 70.58** | 开源 / 1×A100 | 自部署 | **2026 中文 SOTA**（Matryoshka 可降到 1024） |
| Qwen3-Embedding-4B | 2560 | 多语 | MTEB 69+ | 开源 / 1×A10 | 自部署 | 性价比 |
| bce-embedding-base_v1 | 768 | 中文 | C-MTEB 64+ | 开源 | 自部署 | 网易有道、轻量 |
| **Cohere embed-v4** | 256-1536 (Matryoshka) | 多语 + 多模态 | 多语 SOTA | API | $0.12/1M tok | 海外、多模态原生 |
| **voyage-3-large** | 1024 | 多语 | MTEB 头部 | API | $0.18/1M tok | 海外、长文档 |
| OpenAI text-embedding-3-large | 3072 (可降) | 多语 | 中等 | API | $0.13/1M tok | 海外、生态成熟 |

### 5.1 Matryoshka 节省存储

bge-m3 / Qwen3-Embedding / Cohere v4 / OpenAI v3 都支持 **Matryoshka 表示**——同一向量截断到 256/512/1024 维仍可用。

| 维度 | 1M chunk 存储 (HNSW + payload) | 召回相对损失 |
|---|---|---|
| 4096 | ~30GB | baseline |
| 1024 | **~9GB** | -1~3% |
| 512 | ~5GB | -3~6% |
| 256 | ~3GB | -6~10% |

**生产建议**：训练用全维度，**入库截断到 1024** 通常是最佳折中。

### 5.2 换 embedding 的代价

**换 = 全部重 embed + 重建索引**。1 万 PDF / 500 万 chunk / Qwen3-8B：单 A100 约 **6-10 小时** + GPU 成本约 **¥150-300**。**首选不要轻易换；优先加 reranker**（见 §7）。

---

## 6. ⑥ 索引 + ⑦ 查询改写 + ⑧ 三路混合召回

### 6.1 向量库选型一览（详 [L16](./16-opensource-stack-decision.md) §6）

| 规模 | 默认 | 备注 |
|---|---|---|
| < 1000 万 chunk | **pgvector** | 与业务 DB 同栈、备份/事务一体 |
| 1000 万 - 10 亿 | **Qdrant** | tenant collection 隔离、payload filter 强 |
| > 10 亿 | **Milvus** | 分片 / GPU index |

### 6.2 查询改写（Query Rewriting）

| 技术 | 触发 | 实现 | 何时用 |
|---|---|---|---|
| **HyDE** | 抽象 / 长答案问题 | LLM 先生成假设答案 → embed 检索 | 用户问题短 / 模糊 |
| **Step-Back** | 具体问题 | 抽到上位概念再检索（"特斯拉 2024 Q3 营收" → "特斯拉财务"） | 多跳推理 |
| **Multi-Query** | 召回不足 | 1 问题生成 3-5 变体 → 并发检索 → 合并 | 复杂业务问 |
| **Sub-question** | 多事实组合 | LLM 拆子问 → 各自检索 → 答案合成 | "A 和 B 的差异" |
| **历史融合** | 多轮对话 | LLM 改写为独立问题 + 共指消解 | 客服 / 多轮 |
| **意图分类 + 路由** | 多 KB | 先分类 → 路由到对应 KB / 工具 | 大 KB 场景必上 |

### 6.3 三路混合召回（Hybrid）

```
              Query
                │
   ┌────────────┼────────────────────┐
   ↓            ↓                    ↓
[Vector]    [BM25 / 全文]       [Knowledge Graph]
top 50      top 50              top 20 (实体 / 关系)
   └────────────┼────────────────────┘
                ↓
         RRF (k=60) 融合
                ↓
            top 100 → §7 Reranker
```

**真实数据**（生产 KB ≥ 10 万 chunk，n=200 QA pair）：

| 方案 | NDCG@10 | Recall@10 |
|---|---|---|
| 纯向量 | 0.55 | 0.62 |
| 纯 BM25 | 0.60 | 0.66 |
| 向量 + BM25 (RRF) | 0.71 | 0.81 |
| 向量 + BM25 + Reranker | **0.84** | **0.92** |
| 加 KG（实体密集场景） | +3~8pp | +4~9pp |

**反直觉发现**（行业广泛报告）：在 30%+ 企业语料（缩写多、术语严、产品编号密）上，**BM25 单独比纯向量 +5~24% NDCG@10**。**不要砍掉 BM25**。

---

## 7. ⑨ 重排（Reranker）—— 性价比之王

| 模型 | 部署 | 中/英 | 延迟 (top 100, A10) | 推荐 |
|---|---|---|---|---|
| **bge-reranker-v2-m3** | 开源 / 1×A10 | 中英多语 | ~150ms | **中文私有化首选** |
| bge-reranker-v2-gemma | 开源 / 1×A10 | 多语 | ~200ms | 高质量备选 |
| **Cohere Rerank 3.5** | API | 多语 | ~100ms | 海外、稳定 |
| voyage-rerank-2.5 | API | 多语 | ~120ms | 海外 |
| Jina Reranker v2 | 开源 + API | 多语 | ~130ms | 备选 |
| **LLM-as-reranker** (Sonnet 4.6) | API | 全 | ~600ms / 调用 | 极致质量、贵 |

**Anthropic Contextual Retrieval (2024) 实测**（再次引用，是行业基准）：

| 配置 | failure rate |
|---|---|
| baseline (向量) | 5.7% |
| + BM25 (Hybrid) | 4.5% |
| + Contextual chunking | 2.9% |
| **+ Reranker** | **1.9%** |

从 baseline 5.7% 到 1.9% = **-67% failure**。Reranker 单独贡献了 **-49% → -67%** 段最大跃升。

**经验**：性价比上 **Reranker > 换 embedding > 换 LLM**。所有项目第一性强制配 reranker。

---

## 8. GraphRAG 何时用

| 方案 | 一次性建图成本（500 页） | 质量 vs MS-GraphRAG | 增量友好 | 适用 |
|---|---|---|---|---|
| **Microsoft GraphRAG** | **~$33,000**（GPT-4 大量 LLM 抽实体 + 摘要） | 100% baseline | 差（重建） | 学术 / 不计成本 |
| **LightRAG** | **~$0.50** | **70-90%** | 好 | **生产首选**——1/100 成本 |
| **nano-graphrag** | ~$0.30 | 60-75% | 好 | prototype / 小语料 |
| **GraphRAG-FAST** (社区) | ~$2 | 75-85% | 中 | 中等规模 |

**何时上 GraphRAG**：
- 实体 / 关系密集（医疗病历、法律案例、组织架构、供应链）
- 需要"全局问答"（"过去三年所有涉及 A 公司的合同有什么变化"）
- 多跳推理（"X 是谁的下属的下属"）

**何时不上**：FAQ、客服、纯文档问答——纯 hybrid + reranker 即可，加 graph 收益 < 5%。

---

## 9. ColBERT / Late Interaction 何时用

**模型**：jina-colbert-v2（**89 语言**，含中文）；bge-m3 也内含 ColBERT 模式。

**优势**：token 级 late interaction，长文档 + 复杂查询召回明显优于单向量。

**代价**：存储 **3-10×** 单向量（每 token 一个 128 维向量）。1M chunk 可膨胀到 **100GB+**。

**何时用**：
- 高价值小语料（< 10 万 chunk）—— 储存可承受
- 长文档 + 长查询（法律对比、合同审核）
- 已经穷尽 embed + rerank 还想再涨 2-5pp

**何时不用**：百万级语料、成本敏感、QPS 高。

---

## 10. Self-RAG / CRAG / Agentic RAG

### 10.1 何时多步而不是 one-shot

| 模式 | 触发 | 步骤 |
|---|---|---|
| **Self-RAG** | 模型自评检索质量 | 检索 → critique → 决定是否再检索 / 改写 |
| **CRAG** (Corrective RAG) | 召回低分时 | 低分阈值 → 触发 web search 兜底 |
| **Agentic RAG** | 复杂任务 | LLM 决定何时 / 何处 / 用什么工具检索（参 [L5](./05-agent-core.md) tool loop） |
| **Iterative RAG** | 多跳 | 检索 → 部分答案 → 提炼新 query → 再检索 |

### 10.2 临床实测案例（NEJM AI 2025）

医疗诊断助手：
- 单步 RAG：**幻觉率 10.5%**
- Agentic Self-RAG（多步 + critique）：**5.8%**
- 代价：延迟 +2.3×、成本 +3.1×

**结论**：**高责任场景值得**（医疗 / 法律 / 金融）；**客服 / FAQ 不值得**——延迟和成本不划算。

---

## 11. 多模态 RAG

### 11.1 ColPali / VisRAG

| 方案 | 思路 | 数据 |
|---|---|---|
| **ColPali** | 直接对**页面图像**做 ColBERT-style 检索，跳过 OCR | **ViDoRe leaderboard SOTA**；NDCG@5 比 OCR+text 流程高 14-32pp |
| **VisRAG** | VL 模型同时编码图 + 文 → 端到端检索生成 | 论文报告**召回 +25-39%**（财报、技术文档场景） |
| **传统**：OCR + Vision LLM caption → text 流程 | 兼容现有栈 | 复杂图表丢失多 |

**何时用 ColPali / VisRAG**：财报、产品手册、技术架构图、PPT、扫描档案——**视觉信息 > 文字内容**。

**坑**：存储成本高（每页一组向量）；适合 < 10 万页规模。

---

## 12. 数据模型（核心 SQL）

```sql
-- 知识库
CREATE TABLE knowledge_base (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  name TEXT NOT NULL,
  embedding_model TEXT NOT NULL,        -- e.g. 'qwen3-embedding-8b@1024'
  reranker_model TEXT,
  chunk_strategy JSONB,                 -- {strategy:'parent_child',sizes:{parent:1500,child:300}}
  acl_mode TEXT NOT NULL,               -- 'inherit_from_source' | 'kb_level'
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 文档
CREATE TABLE document (
  id UUID PRIMARY KEY,
  kb_id UUID REFERENCES knowledge_base(id),
  source TEXT NOT NULL,                 -- 'confluence:space/page' | 's3://...'
  external_id TEXT,                     -- 源系统 ID，去重用
  hash TEXT NOT NULL,                   -- 内容 hash，去重 + 增量
  version INT NOT NULL DEFAULT 1,
  status TEXT NOT NULL,                 -- 'pending' | 'parsed' | 'indexed' | 'deleted'
  metadata JSONB,                       -- 标题/作者/部门/时间/标签
  parsed_at TIMESTAMPTZ,
  UNIQUE (kb_id, external_id)
);

-- 切片
CREATE TABLE chunk (
  id UUID PRIMARY KEY,
  doc_id UUID REFERENCES document(id),
  parent_chunk_id UUID,
  ord INT NOT NULL,
  content TEXT NOT NULL,
  contextual_summary TEXT,              -- Anthropic Contextual Chunking 注入
  token_count INT,
  embedding vector(1024),               -- pgvector
  metadata JSONB,
  page_no INT,
  bbox JSONB                            -- 多模态/原文定位
);
CREATE INDEX ON chunk USING hnsw (embedding vector_cosine_ops);

-- ACL
CREATE TABLE acl (
  resource_type TEXT NOT NULL,          -- 'kb' | 'document' | 'chunk'
  resource_id UUID NOT NULL,
  principal_type TEXT NOT NULL,         -- 'user' | 'group' | 'role'
  principal_id TEXT NOT NULL,
  permission TEXT NOT NULL,             -- 'read' | 'write' | 'admin'
  source TEXT,                          -- 同步自哪个源系统
  PRIMARY KEY (resource_type, resource_id, principal_type, principal_id)
);
CREATE INDEX ON acl (principal_id, permission);

-- 检索日志（→ L7 trace + L33 数据飞轮原料）
CREATE TABLE retrieval_log (
  id UUID PRIMARY KEY,
  trace_id TEXT,                        -- 关联 Langfuse
  tenant_id UUID,
  user_id TEXT,
  kb_ids UUID[],
  query_raw TEXT,
  query_rewrites TEXT[],
  hit_chunk_ids UUID[],
  used_chunk_ids UUID[],                -- LLM 真正引用的
  scores JSONB,                         -- {vector:[...], bm25:[...], rerank:[...]}
  latency_ms JSONB,                     -- 各阶段
  created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## 13. 多租户与权限（链 [L24](./24-multi-tenant-isolation.md)）

L24 讲**租户级隔离手段**（namespace / partition / 独立 cluster）；L3 讲 **RAG 检索时的具体实现**——**"Glean 模式" ACL-aware retrieval**：

```
Query + user_id
   ↓
1. 取 user 所属 group / role（缓存 5-15 分钟）
   ↓
2. 路由到 tenant 对应的向量库 namespace（Qdrant collection / Milvus partition）
   ↓
3. 检索时 payload filter:
   filter: { acl.principal_id IN [user_id, *user.groups] AND permission = 'read' }
   ↓                                    ↑
   ↓                ★ 关键：filter 在向量索引层，不是事后过滤
   ↓
4. 返回 top-K（已经过滤）→ 进 reranker
```

**关键纪律**：
- ACL filter **必须发生在向量库层**（payload filter / metadata filter），不是 LLM 生成后才删——否则 token 已经被 LLM 看到 = **泄露既成事实**
- 字段级敏感字段：返回前再过滤一遍
- 每次检索强制写 `retrieval_log`（审计 + L33 数据飞轮）
- ACL 缓存失效策略：用户权限变更 webhook → 立即清缓存

---

## 14. 增量更新策略

| 模式 | 适用 | 实现 |
|---|---|---|
| 全量重建 | 小语料 (<10 万 chunk) / 偶尔更新 | 简单；停服窗口或蓝绿 |
| **增量插入** | 默认 | watermark (`updated_at`) + content hash 双校验；变更触发部分 re-embed |
| **删除标记** | 文档下线 | 软删 (`status='deleted'`) → 检索 filter 排除 → 24h 物理清理 |
| **版本化** | 合规 / 审计 | 历史 version 保留，可点选查询时间点 |
| ACL-only 更新 | 权限变 | **只改 metadata，不重 embed**（成本关键） |
| **embedding 模型升级** | 大版本 / 跨域 | 蓝绿：新库并行写 → ABtest 召回 → 切流 → 删旧 |

---

## 15. 真实成本估算（1 万 PDF / 平均 50 页）

设：1 万 PDF × 50 页 × 平均 1500 token/页 = **7.5 亿 token**；按 chunk_size=600 → **125 万 chunk**。

| 项 | 选型 | 估算 |
|---|---|---|
| 解析（MinerU 2.5） | 自部署 1×A10，约 **0.5 页/秒** | **~280 GPU·小时** ≈ **¥1,400-2,800**（云）/ 自有可忽略 |
| 解析兜底（5% 走 Vision LLM） | Qwen2.5-VL API | ~¥3,000 |
| Contextual chunking 上下文生成 | Haiku + prompt cache | 缓存命中 90% → **~¥800-1,500** |
| Embedding（Qwen3-Embed-8B） | 自部署 1×A100，~3000 chunk/s | **~7 GPU·小时** ≈ **¥150-300** |
| Embedding（OpenAI text-emb-3-large）替代方案 | API $0.13/1M | ~¥4,500-7,000 |
| 向量库存储（pgvector，1024 维 + payload） | - | **~12-20 GB** |
| Reranker（每次 top 100） | bge-reranker-v2-m3 自部署 | ~¥0.0005 / query |
| 单次检索成本（含 LLM 推理另算） | hybrid + rerank + 合规 | **~¥0.002-0.005 / query** |

**结论**：**首次入库一次性 ~¥5K-15K**，运营态边际成本极低。**贵的是解析阶段的 GPU + Vision LLM 兜底**，不是 embedding 也不是检索。

---

## 16. 评测（链 [L7](./07-observability-and-eval.md)）

L7 定义指标 / 工具 / 流程；L3 落地：

- **Golden QA**：**每个 KB 200+ QA pair**，按 KB 版本独立维护
- **离线**：**Ragas**（Faithfulness / Answer Relevance / Context Precision / Context Recall）+ Recall@K / NDCG@10 / MRR
- **回归**：每次 chunk 策略 / embedding / reranker / prompt 改动 → 全量跑 → 任何指标 **-2pp 阻塞合并**（CI/CD 接入）
- **在线**：用户点赞率、转人工率、引用点击率、re-query 率
- **数据飞轮**（→ [L33](./33-continuous-finetuning-loop.md)）：bad case → 标注 → 加入 golden + 训练 reranker

---

## 17. MVP 范围（4 周可出）

| 模块 | 选型 |
|---|---|
| KB | 1 个，支持 PDF / DOCX / MD 上传 |
| 解析 | **MinerU 2.5** + PaddleOCR-VL 兜底扫描件 |
| 切分 | 语义切分（chunk 600 / overlap 80） |
| 嵌入 | **bge-m3** 自部署（1×A10） |
| 向量库 | **pgvector** + ts_vector BM25 |
| 检索 | Vector + BM25 双路 + RRF |
| 重排 | **bge-reranker-v2-m3** 自部署 |
| 改写 | Multi-Query (3 变体) |
| 生成 | quote-then-answer 模板（参 [L13](./13-context-engineering.md) §6） |
| 审核 | Ragas Faithfulness / 引用强制 |
| 评测 | 200 QA / Ragas + 人工抽检 |

**预算**：1×A10 GPU + 4 vCPU 云原生，月成本 ~¥3K-5K。

---

## 18. 真实坑总结

1. **解析占 80% bad case**——投入产出最高的优化点是换/升级 parser，不是换 LLM
2. **Reranker > 换 embedding > 换 LLM**——这是 ROI 顺序，违反就是浪费钱
3. **混合检索几乎必做**——纯向量在 30%+ 企业语料输给 BM25
4. **不要相信"最佳 chunk_size"**——按业务调；同 KB 不同 chunk 策略效果差距可达 30%
5. **权限不能事后补**——schema 第一天就上 ACL；事后补 = 推倒重来
6. **元数据是宝藏**——时间 / 来源 / 部门 filter 比纯语义更准；70% 检索可由 metadata 预筛收敛
7. **ACL filter 必须在向量库层**——LLM 看到再过滤 = 泄露既成事实
8. **增量更新要双保险**——watermark + content hash 都要；只用一个必出错
9. **多模态正在变标配**——财报、产品文档、合同都有图表；ColPali / VisRAG 关注
10. **换 embedding 是最贵的决定**——优先加 reranker / contextual chunking
11. **Contextual Chunking ROI 最高的"新东西"**——Anthropic 数据 -49%~-67%，prompt cache 摊销后成本可控
12. **"GraphRAG = MS-GraphRAG"是误解**——LightRAG 70-90% 质量、1/100 成本

---

## 19. 待决议

- [ ] 是否上 ColPali（取决于客户文档"图表占比"实际情况）
- [ ] GraphRAG 优先级：先 LightRAG POC 再决定是否大规模上
- [ ] Contextual Chunking 是否默认全量上（成本 vs 质量取舍）
- [ ] 联邦 RAG（[L32](./32-federated-knowledge.md)）落地时间
- [ ] 是否做"embedding 模型 A/B 灰度"基础设施
- [ ] Reranker 是否走自训（[L33](./33-continuous-finetuning-loop.md) 数据飞轮）

---

**Cross-refs**：
[L7 Eval](./07-observability-and-eval.md) · [L10 当前问题](./10-current-problems-and-mitigations.md) · [L13 上下文](./13-context-engineering.md) · [L15 知识工程](./15-knowledge-engineering.md) · [L16 OSS 栈](./16-opensource-stack-decision.md) · [L18 幻觉](./18-hallucination-handling.md) · [L24 多租户](./24-multi-tenant-isolation.md) · [L25 合规](./25-data-compliance-and-residency.md) · [L32 联邦知识](./32-federated-knowledge.md) · [L33 持续微调](./33-continuous-finetuning-loop.md)
