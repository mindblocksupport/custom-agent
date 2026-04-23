# L18 · 幻觉处理深度方案

> 状态：**讨论中** · v0.1 · 2026-04-22 · 基于 Vectara HHEM / SimpleQA / FActScore / HaluLens 等

## 0. 为什么独立成章
**幻觉是合规命门**：医疗 / 法务 / 金融场景，幻觉 = 法律责任。Tech & Media Law 2025: 17-34% AI-assisted 法务 workflow 有责任风险曝光。**Air Canada 案 (2024-02)**: BC 法庭判航空公司**对 chatbot 幻觉负责**——这是不可逆判例。

## 1. 幻觉分类（按根因）

| 类型 | 描述 | 主要措施层 |
|---|---|---|
| **Factual (parametric)** | 模型用预训练知识乱说 | RAG 接入 |
| **Contextual / Faithfulness** | 忽略或反说检索内容 | Prompt + reranker + 引用强制 |
| **Instruction-following drift** | 违反 system prompt 约束 | Constrained decoding + critic |
| **Tool-result hallucination** | 编造 / 扭曲工具输出 | Schema 校验 + hash-pin |
| **Multi-step planning error** | 多步推理级联错 | Step verification + critic |
| **Citation fabrication** | 编引用——**法律暴露最严重** | 强制 quote-then-answer |

## 2. 真实 Benchmark 现状（2026-04）

| Benchmark | 现状 | 含义 |
|---|---|---|
| **Vectara HHEM (易，摘要)** | Gemini-2.0-Flash **0.7%**, GPT-4o 1.5%, Claude Sonnet 4.4%, **Claude Opus 10.1%** | reasoning 模型在 grounded 摘要上**幻觉更高**——反直觉 |
| **Vectara HHEM (难，长文)** | GPT-5 / Sonnet 4.5 / Grok-4 都 >10% | 长文档情况严峻 |
| **SimpleQA (无 tool)** | GPT-5-main **47% 幻觉率**, GPT-4.5 37.1%, Gemini 2.0 Flash 29.9% 准确 | 无 grounding 全军覆没 |
| **SimpleQA + web search** | GPT-4o-search 90%, GPT-5 Thinking + browse **95.1%** | grounding 是银弹 |
| **GPT-5 vs o3 内部 eval** | 5-8× 少 factual error with thinking | 推理时间 ROI |

**关键洞见**：**reasoning model 在 grounded 摘要任务上更易幻觉**——Vectara 假设是"过度思考"漂离 source。**架构师不要无脑选最大模型**，grounded 任务考虑非推理模型。

## 3. 缓解技术（生产实证）

### 3.1 Grounding + 强制引用 ★ 最高 ROI
- 报告 60-80% 降幻觉
- **Anthropic Citations API** 客户案例：源幻觉 **10% → 0%**
- 引用必须**写入生成 prompt**，不是事后装饰

### 3.2 Constrained Decoding
- OpenAI Structured Outputs (2024-08) / Gemini response_schema (2024-05) / Anthropic constrained decoding (2025-11)
- FSM-based token mask 保证 schema 合法
- **注意**：syntactic 合法 ≠ semantic 正确，模型仍可在合法 schema 内幻觉

### 3.3 Self-consistency / 多采样投票
- N 次采样 + majority vote
- 推理任务最有效；**最近变种**：跨**不同模型 family** 投票稀释 model-specific 模式

### 3.4 Chain-of-Verification (CoVe)
- Dhuliawala et al. (Meta, ACL 2024)
- draft → 起草独立 verification 问题 → 隔离回答 → 修正
- closed-book QA F1 **+23%**

### 3.5 Verifier / Critic Agent
- 单独模型在送给用户前 judge 答案 vs 检索 context
- **Datadog / Arthur** 都 ship LLM-as-judge stack
- **vLLM HaluGate (2025-12)** token-level 实时检测
- **Sierra**：每条生产对话**并行**跑 supervisory agent，in-flight 快检 + 事后慢审

### 3.6 知识图融合
- 权威事实从 KG 拉，作为 constraint 注入
- **FalkorDB** 报告 90% 降 vs 纯 RAG, sub-50ms

### 3.7 RLHF / DPO / 对比微调
- F-DPO (factuality-aware DPO with label-flipping)
- CHAIR-DPO
- Decoupling Contrastive Decoding (CVPR/ICLR 2025)
- 用 factuality 排序的 preference pair（不是 helpfulness）

### 3.8 置信度校准 & 弃权
- OpenAI GPT-5 system card "safe-completions" —— 不拒绝，bounded 帮助 + 校准的 uncertainty signal
- Anthropic prompt 指南**显式**告诉模型"you are allowed to say I don't know" —— **实测降幻觉**

## 4. Agent-specific 问题

### 4.1 Tool-result 幻觉
- 模型编工具输出里没有的字段，或"记得"之前没真返的工具结果
- **防御**：
  - 工具输出回流时 schema 校验
  - **Hash-pin 工具结果**入对话，要求 Agent 在推理前**逐字引用**
  - 论文：Tool Receipts (arXiv 2603.10060)

### 4.2 多步规划级联错
- 单步 95% 可靠 → 20 步流程 36%
- 2025 NeurIPS 7 个 SOTA 多 Agent 系统失败率 **41-86.7%**
- **防御**：(a) 缩短计划 (b) 步间 verifier checkpoint (c) 能写代码就别用 LLM
- Sierra "simulations"：合成对话寻找级联路径，部署前发现

### 4.3 Lost-in-middle
- 2025 跟进 (arXiv 2511.13900): RoPE 衰减仍伤现代长 context 模型
- **生产修法**：cross-encoder rerank, 把 top evidence 放头**和**尾, "pause-tuning" token, 信心低时 agentic re-query

### 4.4 Memory 污染
- **MemoryGraft (2025-12)** 持久危害 long-term memory
- Palo Alto Unit 42 indirect prompt injection 类似
- **防御**：把 memory 当 untrusted input；provenance 标签；signed write；TTL

## 5. 各厂商如何做（公开）

- **Anthropic** — Citations API，"allow Claude to say I don't know"，>20K token 文档强制 direct-quote-first 模式
- **OpenAI** — GPT-5 safe-completions；browsing-grounded 答案在 regulated 域 factual error <1%
- **Glean** — RAG over permissioned 企业统一 index，KG context，line-by-line citations，**AI Evaluator** 打分 groundedness/recall/relevance
- **Perplexity** — 引用作一等公民输出，retrieval 编排在生成前；citation fabrication < 1 vs 竞品
- **Sierra** — 多 supervisor 架构，对话内软干预，事后审，simulation-based 部署前 QA
- **Notion** — RAG-based grounding 通过 Notion-page memory 架构；sub-processor 合同保证训练数据

## 6. 合规角度——为什么这是生死线

| 行业 | 幻觉成本 |
|---|---|
| 医疗 | 误诊责任、HIPAA 合规 |
| 法务 | Air Canada 类判例、Daubert 可信度 |
| 金融 | Basel/Solvency 可审计；监管罚款 |
| 政府 / 公共服务 | NYC MyCity 教训：违法建议 |

2025 报告：法务工作流 17-34% 责任曝光，监管行业合规风险增 **~25%**，GenAI 责任保险市场出现。

## 7. 各层架构清单（**直接可落地**）

### Retrieval 层
- ✅ Hybrid (BM25 + dense) + cross-encoder rerank
- ✅ Top-k evidence 放 prompt 头**和**尾
- ✅ 检索时**就**做权限 filter（不是生成后）

### Prompt 层
- ✅ 显式允许"I don't know"
- ✅ 长 source 强制 quote-then-answer
- ✅ Schema 化输出走 constrained decoding（不要自由 JSON parse）

### Model 层
- ✅ Grounded 摘要默认**非推理模型**；规划 / 数学才路由到推理
- ✅ 高 stake 域 ensemble（跨 2 厂商 consortium voting）

### Tool 层
- ✅ 工具输出回流时 schema 校验
- ✅ Hash-pin 工具结果入对话；verifier 在 hash 上校验任何 claim
- ✅ 幂等可逆设计；每个破坏性 action 走 confirm

### Agent 控制层
- ✅ Verifier/critic agent 并行跑（pre-stream + post-turn）
- ✅ 长 form 生成走 CoVe 验证
- ✅ Plan 长度 cap；步间 checkpoint；能 deterministic code 就别用 LLM

### Memory 层
- ✅ 每条 fact 带 provenance 标签
- ✅ Signed write；read 视为 untrusted input
- ✅ TTL 默认；显式提升到长期

### 观测 / 合规层
- ✅ Per-turn 记录 retrieval set / prompt / 原始 output / 引用 / verifier 判定
- ✅ LLM-as-judge groundedness 评分（采样降本）
- ✅ Verifier 信心 < 阈值 → HITL 升级
- ✅ 周期 Vectara-HHEM 风内部 eval 镜像生产流量

## 8. 实施优先级

| 优先级 | 措施 | 预期降幻觉 |
|---|---|---|
| **P0** | 强制 quote-then-answer + 引用元数据 | 60-80% (Anthropic 客户案例) |
| **P0** | "I don't know is allowed" + 弃权 | 显著 |
| **P0** | Hybrid retrieval + reranker | 召回基础 |
| **P0** | Tool result schema 校验 + hash-pin | 工具幻觉 |
| **P1** | Constrained decoding (JSON schema) | schema 100% 合法 |
| **P1** | Verifier agent 并行 (LLM-as-judge) | 抓出 80% bad case |
| **P1** | Self-consistency (3-5 sample) for 高 stake | 推理任务 |
| **P2** | CoVe for 长 form | +23% F1 |
| **P2** | KG fusion for 实体密集 | 90% 降 (FalkorDB) |
| **P3** | F-DPO 微调 | 长期持续 |

## 9. 监控 KPI

| 指标 | 目标 |
|---|---|
| Citation 覆盖率 | >95% claim 有引用 |
| Faithfulness 评分 (Ragas) | >0.85 |
| Hallucination rate (HHEM-style) | <3% (摘要) / <8% (长 form) |
| 弃权率 | 5-15% (太低 = 在编；太高 = 没用) |
| Verifier flag 率 | <5% |
| HITL 升级率 | <2% |

## 10. 真实坑总结
1. **大模型不一定降幻觉** —— grounded 摘要场景反而升
2. **schema 合法 ≠ 内容真** —— constrained decoding 不是银弹
3. **Citation 是工具不是装饰** —— 必须在生成 prompt 里强制
4. **多模型 ensemble 比单模型** —— consortium voting
5. **Tool result 幻觉被严重低估** —— hash-pin 是关键
6. **Reasoning model 选用要慎** —— Vectara 数据反直觉
7. **memory 污染会"自我强化"** —— provenance + TTL
8. **Verifier 自己也会幻觉** —— 多 judge ensemble + 人工校准
