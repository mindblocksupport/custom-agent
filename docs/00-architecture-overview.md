# 企业级 Agent 架构总览

> 整个项目的"地图"。每一层 / 每一模块在 `docs/` 下拆出独立文件深入展开。
> 状态：**讨论中** · 版本：v0.5 · 最后更新：2026-04-22

---

## 0. 设计原则

1. **场景优先**：先选 1–2 个真实业务场景驱动架构
2. **可演进**：每层都允许从最简实现开始
3. **可观测**：所有 LLM / 工具调用必须可追溯、可回放
4. **安全合规**：默认最小权限、默认审计、默认脱敏
5. **可治理**：Prompt / 工具 / 模型 / 知识都要有版本与生命周期
6. **不重复造轮子**：成熟开源能用就用
7. **以接 LLM 为主，自研为辅** ★
8. **贯穿"个人经验标准化"的能力** ★
9. **从 Day 1 设计多租户隔离 + 合规** ★
10. **DR / BCM 不是事后补** ★

---

## 1. 文档地图（**36 个文档** + 25 个研究报告）

### 1.1 基础架构层（L1–L9） - 9 层栈 (⚠️ 一稿，待研究重写)

```
┌─────────────────────────────────────────────────────────┐
│  L9 接入层    Web / IDE 插件 / IM Bot / OpenAPI / CLI    │
├─────────────────────────────────────────────────────────┤
│  L8 安全治理  AuthN/Z · 审计 · 脱敏 · 注入防御 · 多租户  │
├─────────────────────────────────────────────────────────┤
│  L7 可观测    Trace · Metrics · Eval · 反馈闭环          │
├─────────────────────────────────────────────────────────┤
│  L6 编排层    多 Agent 协作 · DAG 工作流 · HITL 审批     │
├─────────────────────────────────────────────────────────┤
│  L5 Agent Core  Planner · Memory · Context · State      │
├─────────────────────────────────────────────────────────┤
│  L4 工具/技能   内置工具 · MCP · 企业系统集成 · 沙箱     │
├─────────────────────────────────────────────────────────┤
│  L3 知识 RAG    采集 · 切分 · 向量 · 混合检索 · 重排     │
├─────────────────────────────────────────────────────────┤
│  L2 模型网关    多模型路由 · 限流 · 缓存 · 成本控制      │
├─────────────────────────────────────────────────────────┤
│  L1 基础设施    K8s · GPU · 向量库 · 消息队列 · 存储     │
└─────────────────────────────────────────────────────────┘
```

| 层 | 文档 | 状态 |
|---|---|---|
| L1 | [01-infrastructure.md](01-infrastructure.md) | ⚠️ 一稿 |
| L2 | [02-llm-gateway.md](02-llm-gateway.md) | ⚠️ 一稿 |
| L3 | [03-rag.md](03-rag.md) | ⚠️ 一稿 |
| L4 | [04-tools-and-skills.md](04-tools-and-skills.md) | ⚠️ 一稿 |
| L5 | [05-agent-core.md](05-agent-core.md) | ⚠️ 一稿 |
| L6 | [06-orchestration.md](06-orchestration.md) | ⚠️ 一稿 |
| L7 | [07-observability-and-eval.md](07-observability-and-eval.md) | ⚠️ 一稿 |
| L8 | [08-security-and-governance.md](08-security-and-governance.md) | ⚠️ 一稿 |
| L9 | [09-access-layer.md](09-access-layer.md) | ⚠️ 一稿 |

### 1.2 横切 / 战略模块（L10–L23） - 14 篇 (✅ 全部 deep)

| # | 文档 | 用户点名 |
|---|---|---|
| L10 | [当前 LLM/Agent 真实痛点 & 架构应对](10-current-problems-and-mitigations.md) | |
| L11 | [模型战略：以外部 LLM 为主，自研为辅](11-model-strategy.md) | ★ |
| L12 | [LLM API 交互协议设计](12-llm-api-protocols.md) | ★ |
| L13 | [上下文工程（Context Engineering）](13-context-engineering.md) | ★ |
| L14 | [电脑 / 浏览器 Use 扩展能力](14-computer-and-browser-use.md) | ★ |
| L15 | [知识工程：把个人经验标准化为 AI](15-knowledge-engineering.md) | ★ |
| L16 | [开源栈选型决策（一站式）](16-opensource-stack-decision.md) | ★ |
| L17 | [Prompt 工程 & 管理](17-prompt-engineering.md) | |
| L18 | [幻觉处理深度方案](18-hallucination-handling.md) | ★ |
| L19 | [企业 Agent 竞品 / 厂商 / 市场全景](19-vendor-landscape.md) | |
| L20 | [生产部署经验 / 失败复盘 / 治理结构](20-deployment-and-operations.md) | ★ |
| L21 | [LLM FinOps & 成本管理](21-finops-cost-management.md) | |
| L22 | [人在回路（HITL）设计](22-hitl-design.md) | |
| L23 | [Agent SDLC / 生命周期管理](23-agent-sdlc.md) | |

### 1.3 企业落地必备（L24-L36） - **本批新增 12 篇** (✅)

| # | 文档 | 优先级 |
|---|---|---|
| L24 | [多租户隔离深度](24-multi-tenant-isolation.md) | 🔴 P0 SaaS 必须 |
| L25 | [数据合规 & 数据出境](25-data-compliance-and-residency.md) | 🔴 P0 政企必须 |
| L26 | [灾备 (DR) & 业务连续性 (BCM)](26-disaster-recovery-bcm.md) | 🟡 P1 |
| L27 | [Voice Agent](27-voice-agent.md) | 🟡 P1 $45B 市场 |
| L29 | [客户 90 天 Onboarding 套件](29-customer-onboarding-90day.md) | 🔴 P0 决定续约 |
| L30 | [垂直行业模板](30-vertical-templates.md) | 🟡 P1 GTM 杠杆 |
| L31 | [Edge / 端 AI 能力](31-edge-and-on-device-ai.md) | 🟢 P2 |
| L32 | [联邦知识 / 跨租户共享](32-federated-knowledge.md) | 🟢 P2 |
| L33 | [持续微调闭环 / RLHF / 数据飞轮](33-continuous-finetuning-loop.md) | 🟡 P1 |
| L34 | [A2A 跨 Agent 协作协议](34-a2a-agent-collaboration.md) | 🟢 P2 |
| L35 | [Agent Simulation / 数字孪生平台](35-agent-simulation.md) | 🟡 P1 差异化 |
| L36 | [信创 / 国密 / 主权 AI 全栈](36-xinchuang-and-sovereign-ai.md) | 🔴 P0 政企必须 |

### 1.4 专家审查 + 路线图

| # | 文档 |
|---|---|
| L99 | [专家审查 & 前瞻路线图](99-expert-review-and-roadmap.md) |

---

## 2. 关键决策（v0.5 当前）

| 决策 | 选项 | 我们的判断 |
|---|---|---|
| **模型策略** | 纯 API / 混合 / 纯本地 | **混合：外部 LLM 主 + 窄场景自部署** ★ |
| **场景定位** | 平台型 / 垂直型 | **垂直起家** (建议: 客服 + 销售) |
| **编排范式** | 声明式 / 代码 / 混合 | **LangGraph + Temporal** |
| **数据合规** | 出域 / 不出域 | 默认设计支持**两者** |
| **首选语言** | 单 / 多语言 | **Python (Agent core) + Go (Gateway/后端) + TS (前端)** |
| **OSS Gateway** | LiteLLM / NewAPI / Bifrost | **NewAPI**（中国）/ **LiteLLM**（海外）/ **Bifrost**（高 RPS） |
| **RAG 平台** | RAGFlow / Onyx / Haystack | **fork RAGFlow**（中）/ **Onyx**（西）+ **LightRAG** |
| **观测栈** | Langfuse / Phoenix / OpenLIT | **Langfuse + DeepEval + Promptfoo + OpenLLMetry SDK** |
| **沙箱** | E2B / Daytona / gVisor / Firecracker | **gVisor + 加固 Docker**；untrusted **E2B / Microsandbox** |
| **Workflow** | Temporal / Restate / Hatchet | **Temporal** + **LangGraph** |
| **电脑 Use** | 是 / 否 | **是** ★ |
| **知识工程模块** | 是 / 否 | **是** ★ |
| **HITL** | 简单 / 完整 | **完整**（L22） |
| **FinOps** | 简单熔断 / 完整 | **完整**（L21） |
| **多租户隔离** | 浅 / 深 | **L24 深度（PG RLS + 向量 namespace + KMS）** |
| **DR/BCM** | L1 / L2-L3 / L4 | **L2-L3** + 多 LLM vendor failover |
| **信创路线** | 不做 / 跟客户 / 主推 | **跟首政企客户驱动** (L36) |

---

## 3. 推荐技术栈（v0.5）

| 层 | 选型 |
|---|---|
| Agent core | Python + LangGraph 1.0 + Claude Agent SDK |
| 长任务编排 | Temporal (Python SDK) |
| Web 后端 | Go (Hertz) |
| LLM Gateway | NewAPI / LiteLLM / Bifrost |
| 向量库 | pgvector → Qdrant → Milvus；SaaS 多租户 Weaviate |
| 关系库 | Postgres 16+ (信创: 达梦/人大金仓) |
| 缓存 | Redis Cluster |
| 消息 | Kafka |
| 沙箱 | gVisor + 加固 Docker；untrusted E2B / Microsandbox |
| 观测 | Langfuse + OpenLLMetry + DeepEval + Promptfoo + Garak |
| Guardrails | NeMo + Llama Guard 4 + Granite Guardian + Presidio + 阿里云内容安全 |
| RAG 平台 | fork RAGFlow + LightRAG |
| Memory | mem0 + Zep/Graphiti + Letta |
| 电脑 Use | Anthropic Computer Use + Browser-Use + OmniParser V2 + Firecracker |
| Voice | Vapi / 豆包语音 (集成式) |
| Prompt mgmt | Langfuse Prompts + Mirascope + Anthropic Skills |
| 前端 | Next.js + Vercel AI SDK 6 |
| K8s | Helm + ArgoCD |
| 国密 (信创) | 国密 OpenSSL + 江南天安 HSM |

---

## 4. 落地路线（v0.5）

| 阶段 | 周期 | 目标 | 关键文档 |
|---|---|---|---|
| **战略对齐** | 2 周 | 锁 4 决策；团队读 L10-L23；选 1-2 垂直 | L10-L23 + L99 |
| **MVP** | 4-6 周 | L1-L9 + L11/L12/L13/L16/L18/L21/L22 基础 | L11/12/13/16/18/21/22 |
| **工程化** | 2-3 月 | L15 知识工程 + L7/L8 完整 + L17 + L23 + L24 多租户 + SSO | L15/17/23/24 |
| **规模化** | 3-6 月 | L14 电脑 use + L6 多 Agent + L25 合规 + L26 DR + L29 90d onboarding + L30 垂直模板 | L14/25/26/29/30 |
| **智能化** | 持续 | L27 Voice + L33 微调 + L35 simulation + L36 信创 + L34 A2A + L31 Edge | L27/31/33-36 |

---

## 5. 跨文档导航

### 按战略关切
- 当前 Agent 能做什么 / 在哪翻车 → [L10](10-current-problems-and-mitigations.md)
- 怎么用模型最划算 → [L11](11-model-strategy.md) + [L21](21-finops-cost-management.md)
- 怎么和外部 LLM 通信 → [L12](12-llm-api-protocols.md)
- 怎么管理上下文 / 长 context / Memory → [L13](13-context-engineering.md)
- 怎么让 Agent 操作电脑/网页 → [L14](14-computer-and-browser-use.md) ★
- 怎么把专家经验变成 AI ★ → [L15](15-knowledge-engineering.md)
- 用什么开源 / 为什么用 → [L16](16-opensource-stack-decision.md) ★
- 怎么写 / 管理 Prompt → [L17](17-prompt-engineering.md)
- 怎么解决幻觉 → [L18](18-hallucination-handling.md) ★
- 谁在做这市场怎么打 → [L19](19-vendor-landscape.md)
- 怎么部署 / 治理 / 上线 → [L20](20-deployment-and-operations.md)
- 怎么控制成本 → [L21](21-finops-cost-management.md)
- 怎么设计 HITL → [L22](22-hitl-design.md)
- 怎么做 Agent 的 SDLC → [L23](23-agent-sdlc.md)
- **多租户怎么隔离** → [L24](24-multi-tenant-isolation.md) ★
- **合规 / 数据出境** → [L25](25-data-compliance-and-residency.md) ★
- **DR / BCM** → [L26](26-disaster-recovery-bcm.md)
- **Voice 通道** → [L27](27-voice-agent.md)
- **客户 90 天 onboarding** → [L29](29-customer-onboarding-90day.md) ★
- **垂直模板** → [L30](30-vertical-templates.md)
- **端 AI** → [L31](31-edge-and-on-device-ai.md)
- **行业知识联邦** → [L32](32-federated-knowledge.md)
- **持续微调** → [L33](33-continuous-finetuning-loop.md)
- **A2A 跨 Agent** → [L34](34-a2a-agent-collaboration.md)
- **Simulation 数字孪生** → [L35](35-agent-simulation.md)
- **信创 / 国密** → [L36](36-xinchuang-and-sovereign-ai.md) ★
- **专家审查 + 前瞻** → [L99](99-expert-review-and-roadmap.md)

### 按工程领域
- **基建 / SRE** → L1 + L11 自部署 + L26 DR
- **Backend** → L2 + L4 + L6 + L9 + L12 + L16
- **AI / ML** → L3 + L5 + L11 + L13 + L18 + L33
- **安全** → L8 + L10 (Prompt 注入) + L18 + L24 + L25
- **DevOps / 观测** → L1 + L7 + L20 + L23 + L26
- **产品 / 增长** → L9 + L19 + L29 + L30 + L35
- **合规 / 法务** → L8 + L20 + L25 + L36
- **Customer Success / 销售** → L19 + L21 + L29 + L20 + L35

---

## 6. 真实痛点应对索引（完整版）

| 痛点 | 解决文档 |
|---|---|
| 专家经验离职即蒸发 | L15 |
| 模型 vendor 锁定 | L11/L12 |
| 数据出境合规 | L25 |
| 成本失控 | L21 |
| 遗留系统集成 | L14 |
| 审计不可追溯 | L8/L20/L25 |
| Agent 上线后衰退 | L15/L23/L33 |
| 离线 / 信创 | L36 |
| Voice 渠道 | L27 |
| 真实业务流程对接 | L4/L6/L14 |
| 跨 Agent 协作 | L34 |
| 客户敢不敢给权限 | L18/L22 |
| 怎么衡量 ROI | L19/L21/L29 |
| 失败可回滚 | L23/L26 |
| 新模型迁移 | L23 |
| Edge / 端运行 | L31 |
| Prompt injection | L18 |
| AI on-call | L20/L26 |
| 怎么定价 | L19/L21 |
| 多租户跨泄露 | L24 |
| Region 整挂 | L26 |
| 客户 onboarding 慢 | L29 |
| 行业经验复用 | L30/L32 |
| 客户上线前焦虑 | L35 (simulation) |
| 持续优化 | L33 |

---

## 7. 文档约定

- 每篇文档结构：目标与边界 → 核心概念 → 详细设计 → 选型对比 → 风险与权衡 → MVP 范围 → 待决议
- 状态标签：`讨论中` / `已定稿` / `已实现`
- 重大变更走 ADR (Architecture Decision Record), 存 `docs/adr/`
- 所有数据 / benchmark / 价格必须带日期与来源链接

---

## 8. 当前状态总结

✅ **已完成**：
- **36 个核心文档**（00 + 01-09 + 10-23 + 24-27 + 29-36 + 99）
- **25 个深度研究报告**（agent context 中）

⚠️ **待重写**：
- L1-L9 基础架构层（一稿，需基于研究系统重写）

📋 **可选后续**：
- L37 Green AI / 碳排放
- L38 AI 责任保险
- L39 跨模态 Agent (text + voice + vision + action 统一)
- L40 人机协作模式深度

🚀 **可以动手了**：
基于现有文档体系，工程团队可以正式开工 MVP（参考 §4 落地路线 + §3 推荐技术栈）。
