# L16 · 开源栈选型决策（一站式）

> 状态：**讨论中** · v0.1 · 2026-04-22 · 整合 8 个研究报告 · 每个组件回答"为什么可以适配我们"

## 0. 总览推荐栈

```
┌──────────────────────────────────────────────────────────────────┐
│ 用户接入: Next.js + Vercel AI SDK 6 / Mastra (TS)                │
├──────────────────────────────────────────────────────────────────┤
│ 应用层 (Go): tenancy / RBAC / billing / 审计                     │
├──────────────────────────────────────────────────────────────────┤
│ Agent runtime (Python): LangGraph 1.0 + Claude Agent SDK         │
│ 长任务: Temporal (Python SDK)                                     │
├──────────────────────────────────────────────────────────────────┤
│ Gateway: NewAPI (国内) / LiteLLM (国际) → Bifrost (高 RPS)       │
├──────────────────────────────────────────────────────────────────┤
│ RAG 平台: fork RAGFlow (中) / Onyx (西) + LightRAG (graph)       │
├──────────────────────────────────────────────────────────────────┤
│ 向量库: pgvector (<10M) → Qdrant (10M-1B) → Milvus (1B+)         │
├──────────────────────────────────────────────────────────────────┤
│ Memory: Mem0 (人格化) + Zep/Graphiti (时序) + Letta (长期)        │
├──────────────────────────────────────────────────────────────────┤
│ 沙箱: gVisor + 加固 Docker (默认) → E2B/Microsandbox (untrusted) │
├──────────────────────────────────────────────────────────────────┤
│ 观测: Langfuse + OpenLLMetry SDK + DeepEval + Promptfoo + Garak  │
├──────────────────────────────────────────────────────────────────┤
│ Guardrails: NeMo Guardrails (orchestrator) + Llama Guard 4       │
│            + Granite Guardian 3.2 + Presidio + 阿里云内容安全     │
├──────────────────────────────────────────────────────────────────┤
│ Eval: Ragas (RAG) + DeepEval (CI) + Inspect AI (Agent) + Garak    │
├──────────────────────────────────────────────────────────────────┤
│ Prompt mgmt: Langfuse Prompts + Mirascope + Anthropic Skills 标准│
└──────────────────────────────────────────────────────────────────┘
```

## 1. LLM Gateway

| 选型 | License | 优势 | 中国友好 | 适用 | 决策 |
|---|---|---|---|---|---|
| **NewAPI** (QuantumNous fork OneAPI) | AGPLv3 + 商业 | Go 高性能，原生 DeepSeek/Qwen/Zhipu/Doubao/Moonshot/Hunyuan/Baichuan/MiniMax 支持，**中文 admin UI**，cache billing 准确，OIDC/LinuxDO/钉钉飞书 SSO，跨格式转换 (任意→OpenAI/Claude/Gemini) | ★★★★★ | 中国客户 | **MVP** |
| **LiteLLM** | MIT 核心 + 商业 enterprise/ | 140+ provider 最广，44k 星，社区最大；Python | ★★★★ | 国际客户 | 海外备选 |
| **Bifrost** (maximhq) | Apache 2.0 + 企业 | Go 性能：5k RPS @ 11μs 开销，比 LiteLLM 快 50× | ★★★ | 高 RPS 升级 | 性能瓶颈时迁 |
| **Helicone Router** | Apache 2.0 | Rust 高性能 | ★★★ | - | ⛔ **2026-03 Mintlify 收购，已 maintenance only** |
| **Portkey** | MIT (2026-03 全开源) | TS Hono；50+ guardrails | ★★ | TS 团队 | 备选 |
| **Envoy AI Gateway** | Apache 2.0 (CNCF) | K8s native，Istio 集成 | ★★★ | 大型 K8s 客户 | 升级方向 |

**为什么 NewAPI 适配我们**：中国客户 95% 想要的功能开箱即有 (Chinese SSO + DeepSeek cache billing + RMB 计费)；单 Go 二进制 / Docker；许可证 AGPLv3 对 SaaS 用法没问题（除非你要把 gateway 自身作为产品再分发）。

## 2. RAG 平台

| 选型 | License | 优势 | 中国友好 | 决策 |
|---|---|---|---|---|
| **RAGFlow** (infiniflow) | Apache 2.0 | 78k 星；DeepDoc 解析中文 PDF/扫描/表格行业最强；agent + workflow；原生 Qwen/DeepSeek/Aliyun OSS/gVisor 沙箱；Quart + Redis Streams + ES/Infinity | ★★★★★ | **fork 作为基座（中国）** |
| **Onyx (Danswer)** | MIT (CE) | **100+ connector**，SSO/RBAC/SCIM，**document-permission mirroring**（独家） | ★★★ | **西方客户首选** |
| **Haystack 2.x** | Apache 2.0 | 框架稳定，DAG pipeline 成熟 | ★★ | 框架级集成 |
| **R2R (SciPhi)** | Apache 2.0 | 后端干净，GraphRAG 内建，FastAPI | ★★★ | 后端起步 |
| **LightRAG** | MIT | 图模式 70-90% 质量 / **1/100 GraphRAG 成本** ($0.50, 3min for 500 页) | ★★★★ | **集成作为图检索模式** |
| **Microsoft GraphRAG** | MIT | 最高图质量 | ★★ | 仅参考 / 太贵 |
| **Dify** | Apache 2.0 + 多租户限制 | LLMOps 平台 80k 星 | ★★★★★ | ⛔ **多租户 SaaS 许可陷阱** —— 不能作 SaaS 基座 |
| **FastGPT** | Apache 2.0 + 限制 | Coze-like，27k 星 | ★★★★★ | ⛔ 多租户 SaaS 限制 |
| **MaxKB** | **GPL-3.0** | 1Panel 生态强 | ★★★★★ | ⛔ 强 copyleft，闭源产品基座绝对避 |
| **Khoj** | **AGPL-3.0** | 个人 AI 助手 | ★★ | ⛔ 网络使用条款陷阱 |
| **Verba** | BSD-3 | Weaviate 配套 | ★★ | ⛔ Weaviate 已用 Elysia 取代 |
| **Vanna AI** | MIT | text-to-SQL | ★★ | ⛔ **2026-03-29 已 archive** |
| **Onyx / RAGFlow / R2R** 三选一 | - | 都 MIT/Apache 2.0 没坑 | - | **fork 一个+ LightRAG 集成** |

**为什么 RAGFlow + LightRAG 组合**：中文 PDF/扫描/表格解析行业最强（DeepDoc）+ graph mode 70-90% 质量 1/100 GraphRAG 成本。Apache 2.0 + Apache 2.0 都干净。

## 3. 向量库

| 规模 | 选型 | 理由 |
|---|---|---|
| **<10M 单租户** | **Qdrant** (独立) 或 **pgvector** (复用 PG) | Qdrant 2ms p99，filter 最强；pgvector 复用 PG ops |
| **10M-1B** | **Qdrant** (filter 重) 或 **Milvus** (写入吞吐 / GPU) | Qdrant Tiered Multitenancy 适合 SaaS；Milvus NVIDIA/Salesforce/eBay 验证 |
| **1B+** | **Milvus** (自部署) / **Vespa** (复杂排序 / ColBERT) / **Turbopuffer** (闭源 hosted, 95% 省钱) | Milvus 是 1B+ 自部署唯一可选 |
| **多租户 SaaS (1k-1M tenant)** | **Weaviate** ★ | 50k tenants/node, 1M tenants/20-node cluster, lazy load, cold-tier offload |
| **已用 Postgres** | **pgvectorscale** (Tiger) | StreamingDiskANN：50M Cohere-768d 上 471 QPS @ 99% recall，**11.4× 比 Qdrant 快** |
| **已用 ES** | **OpenSearch 3.0+** | GPU 加速 9× |
| **embedded** | **LanceDB** | 0 ops 嵌入，<$200/月 |
| **多模态** | **Marqo** (built on Vespa) | 内建 CLIP/E5 |
| **图 + 向量** | **TigerVector** (TigerGraph 4.2+) | SIGMOD 2025 击败 Neo4j/Neptune/Milvus |

**避免**：Redis Stack >50M（RAM 经济崩）；Faiss (库不是 DB)；Vanna AI (archived)；Chroma OSS >10M (单节点)。

## 4. 观测 (Observability)

| 选型 | License | 优势 | 决策 |
|---|---|---|---|
| **Langfuse** ★ | MIT 核心 + EE | 25k 星, 23M monthly install, 6M docker pull；Postgres + ClickHouse + Redis + S3；最完整 (trace + prompt + eval + dataset + cost + annotation)；ClickHouse 2026-01 收购 | **MVP + 客户私有部署** |
| **OpenLLMetry SDK** (Traceloop) | Apache 2.0 | **OTel GenAI 标准事实库**，Py/TS/Go/Ruby | **作为 SDK 必装** |
| **Phoenix** (Arize) | **ELv2** | OpenInference + OTel native | ELv2 客户敏感时备选 |
| **OpenLIT** | Apache 2.0 | 纯 OTel，ClickHouse | Apache-only 客户备选 |
| **Helicone** | Apache 2.0 | - | ⛔ Mintlify 收购后 maintenance |
| **Lunary** | Apache 2.0 | - | ⛔ 2025-12 GitHub 404 治理风险 |
| **AgentOps** | MIT SDK | Agent replay 强 | 多 Agent trace 补强 |

**为什么 Langfuse + OpenLLMetry + DeepEval 组合**：OSS-only 可客户私有部署；OTel 标准化让客户可自带后端；MIT 无许可陷阱；功能最全；能在中国 Aliyun ACK 自部署。

## 5. 沙箱（代码执行）

| 信任级别 | 选型 |
|---|---|
| **Trusted (内部 dev co-pilot)** | gVisor + 加固 Docker (rootless, 只读 rootfs, dropped caps, seccomp, --network none) |
| **Untrusted (公共 / 客户 prompt)** | **E2B** (Apache 2.0 核, Firecracker, 88% F100 用) 或 **Microsandbox** (libkrun, 自部署) |
| **K8s native** | **Kata Containers** (Apache 2.0, 真 guest kernel) |
| **GPU workloads** | **Modal** (managed, A100/H100) 或 **Kata + NVIDIA Confidential Containers** (TDX/SEV-SNP + H100 attestation) |
| **高密度 ms 启** | **WasmEdge / Wasmer** |
| **永远避免** | **vm2** (CVE-2026-22709 CVSS 9.8 sandbox escape)；纯 Open Interpreter (无沙箱) |

**为什么 E2B/Microsandbox + gVisor 组合**：Firecracker 独立 guest kernel 防 runC CVE 类 (2025-11 CVE-2025-31133/52565/52881)；gVisor 在密度场景便宜；都 Apache 2.0；可中国自部署。

## 6. Workflow / 长任务

| 任务长度 | 选型 |
|---|---|
| **<5 min Agent 步** | **LangGraph** 单机 checkpointer (Postgres) 即可 |
| **5min-1day** | **Temporal** ★ (MIT, 19k 星, polyglot, OpenAI Agents SDK + Temporal **GA 2026-03**) |
| **HITL 几天** | **Temporal** 必须 (durable timers + signals + 2026 **Worker Versioning GA** 解决"运行中的 workflow 怎么改代码") |
| **轻量替代** | **Hatchet** (MIT, 单 Postgres, 10k+ 自部署/月) 或 **Restate** (BSL, 嵌入 RocksDB) |
| **TS only** | **Trigger.dev v3** (Bun workers，最佳 DX) 或 **Inngest** (event-driven 最干净) |
| **K8s batch** | **Argo Workflows** (Apache, CNCF) |
| **避免** | CrewAI Flows (无 checkpointing)；Airflow (粒度错)；n8n (Sustainable Use License 不能嵌入产品) |

**最佳模式**：**LangGraph (推理) + Temporal (durability)** —— Grid Dynamics / OpenAI Agents SDK 集成 / 2026 Q1 主流企业落地都收敛在此。

## 7. Memory

| 选型 | License | 强项 |
|---|---|---|
| **mem0** | Apache 2.0 (核) | 快速人格化，**91% lower P95**, 90% 少 token vs full-context |
| **Letta (MemGPT)** | Apache 2.0 | LLM-as-OS 虚拟 context paging；适合 stateful autonomous |
| **Zep / Graphiti** | Apache 2.0 | 双时间知识图，**94.8% DMR**, +18.5% LongMemEval, 300ms P95 |
| **LangMem** (LangChain) | MIT | LangGraph 原生 |
| **Cognee** | - | 14 retrieval mode |
| **GraphRAG / FalkorDB** | MIT/BSL | 高 quality 图记忆 |

**推荐组合**：**mem0** (用户偏好快查) + **Zep/Graphiti** (时序事实, GDPR 友好) + **Letta** (长期 stateful, 仅当 memory 是产品 feature 时)。

## 8. Guardrails

详见 L8 + 此处摘要：

| 用途 | 选型 |
|---|---|
| **Orchestration** | **NeMo Guardrails** (Apache 2.0, Colang DSL) |
| **PII** | **Microsoft Presidio** (MIT) + 自定义 CN 识别器 |
| **Prompt injection** | **Llama Guard 4** (community license) + **Microsoft Prompt Shields** (Azure) 双 stack |
| **Harm + RAG groundedness** | **IBM Granite Guardian 3.2** (Apache 2.0, 5B + LoRA) |
| **Schema / citation** | **Guardrails AI** (Apache 2.0) |
| **Red team / 扫描** | **Garak** (NVIDIA, 150+ probes) + **PyRIT** (Microsoft) |
| **中国合规** | **阿里云内容安全 PLUS** + 自建敏感词 + 微调小 Qwen |

**避免**：Rebuff (2025-05 archived)。

## 9. Eval

| 用途 | 选型 |
|---|---|
| **Prompt 单测 (CI)** | **Promptfoo** (MIT) + **DeepEval** (Apache 2.0, pytest 形) |
| **RAG eval** | **Ragas** (Apache 2.0) + **Patronus Lynx-8B** (高保真领域) |
| **Agent eval** | **Inspect AI** (UK AISI, MIT) ★ + 200+ pre-built bench (SWE/GAIA/Cybench) |
| **Red team** | **Garak** (深) + **Promptfoo red-team** (CI) |
| **生产在线** | **Langfuse** (OTel + 在线评测) 或 **Athina** (turnkey) |

## 10. Prompt 管理

| 用途 | 选型 |
|---|---|
| **MVP (git-stored)** | Jinja2 模板 in repo + Promptfoo CI eval |
| **规模 (prompt CMS)** | **Langfuse Prompts** (MIT, label-based deploy) |
| **Typed Python** | **Mirascope** (MIT, decorator) |
| **Auto-optimization** | **DSPy** (MIT, MIPROv2/GEPA, 10-30 min, $20-50 per compile) |
| **Skill 打包标准** | **Anthropic Skills** (开标准 2025-12, 已被 OpenAI/MS/Cursor/GitHub/Atlassian 采纳) |

## 11. 全栈许可证检查表（避免后期暴雷）

✅ **可放心 (MIT/Apache 2.0)**：LangGraph, Temporal (MIT), Hatchet, Inngest, Trigger.dev, Restate SDKs, Anthropic Skills 标准, RAGFlow, Onyx CE, Haystack, R2R, LightRAG, Qdrant, Milvus, Weaviate, Chroma, pgvector, LanceDB, Marqo, Vespa, mem0, Letta, Zep, LangMem, Langfuse 核心, OpenLLMetry, OpenLIT, AgentOps, NeMo Guardrails, Guardrails AI, Granite Guardian, Presidio, Garak, PyRIT, ModelScan, Ragas, DeepEval, Promptfoo, OpenAI Evals, lm-eval-harness, Inspect AI, Phoenix Apache 部分, NewAPI 主代码, OneAPI, Bifrost 核, Browser-Use, Stagehand, OmniParser, UI-TARS, AutoGLM 开源, gVisor, Firecracker, Kata, Microsandbox, E2B 核

⚠️ **小心 (BSL / Elastic / Sustainable Use)**：Restate server (BSL), Phoenix (ELv2 - 不能 SaaS hosting), n8n (Sustainable - 不能嵌入产品), Mastra (Elastic-2.0)

⛔ **避免 (Copyleft / 多租户限制 / 已 archived / 治理风险)**：Khoj AGPL, MaxKB GPL, Daytona AGPL 核, Skyvern AGPL, Dify 多租户限制, FastGPT 多租户限制, Helicone (maintenance), Lunary (404 incident), Rebuff (archived), Vanna AI (archived), Verba (sunset), vm2 (CVE)

## 12. 决策矩阵：场景 → 推荐栈

| 场景 | Gateway | RAG | Vector | Workflow | Memory | Sandbox | Obs |
|---|---|---|---|---|---|---|---|
| 中国企业 SaaS | NewAPI | RAGFlow + LightRAG | Qdrant + pgvector | Temporal + LangGraph | mem0 + Zep | gVisor + E2B | Langfuse |
| 西方企业 SaaS | LiteLLM | Onyx + LightRAG | Qdrant + pgvector | Temporal + LangGraph | mem0 + Zep | gVisor + E2B | Langfuse |
| 政企离网 | NewAPI | RAGFlow | Milvus | Temporal | mem0 | Microsandbox | Langfuse 自部署 |
| 高 RPS 平台 | Bifrost | RAGFlow | Milvus | Temporal | Zep | Kata | Langfuse + ClickHouse |
| 金融监管 | NewAPI + Bifrost | Onyx | Milvus | Temporal | Zep | Kata Confidential | Langfuse + audit log 强化 |

## 13. 不要做的（教训总结）

1. ❌ **自建 LLM Gateway** —— LiteLLM 140+ provider 你追不上
2. ❌ **完全自建 RAG 平台** —— 文档解析行业 80% 工作量在这，复用 RAGFlow / Onyx
3. ❌ **vm2 任何 untrusted 路径** —— CVE 历史
4. ❌ **Khoj / MaxKB / FastGPT / Dify 作 SaaS 基座** —— license trap
5. ❌ **Lunary / Helicone / Rebuff / Vanna / Verba 新部署** —— 已死或风险
6. ❌ **CrewAI Flows 作生产 durable layer** —— 无 checkpoint
7. ❌ **跨 LLM 厂商手写适配** —— 用 LiteLLM/NewAPI 抽象
8. ❌ **自建 prompt CMS** —— Langfuse 完全够
9. ❌ **不用 OpenLLMetry SDK** —— OTel GenAI 已是事实标准

## 14. 总结：每一个组件"为什么适配我们"

| 组件 | 适配理由 |
|---|---|
| LangGraph | MIT, 400+ 生产用户 (Uber/JPM/Klarna), explicit state machine 可审计 |
| Temporal | MIT, polyglot, OpenAI Agents SDK 官方集成, Worker Versioning 解决长 workflow 升级痛点 |
| NewAPI | 中国生态量身打造，DeepSeek/Qwen 原生 + cache billing + 中文 UI |
| RAGFlow | DeepDoc 中文文档解析行业最强，Apache 2.0，78k 星活跃 |
| Qdrant | Rust 安全 + 最佳 filter perf + Tiered Multitenancy = SaaS friendly |
| Langfuse | MIT 核心，可客户私有，OTel native，覆盖 trace+prompt+eval+cost 全栈 |
| Anthropic Skills | 开标准已被 OpenAI/MS/Cursor 采纳，progressive disclosure 优雅 |
| E2B | Firecracker 独立 kernel = 防 runC CVE 类，88% F100 验证 |
| Llama Guard 4 + Granite Guardian | 多模型 ensemble (recall 0.95 → 0.99) + Apache/community 许可 |
| Browser-Use | MIT, 79k 星, native Anthropic computer_use API 集成 |

## 15. 实施清单
- [ ] 锁定栈版本（每组件 pin major.minor）
- [ ] 内部 Helm chart 把 11 个组件打包
- [ ] 客户私有化交付包（含离线镜像仓库）
- [ ] 定期升级流程（季度 minor，半年 major）
- [ ] License 合规自动扫描（Snyk / FOSSA）
- [ ] 替换路径文档（每组件至少 1 备选）
