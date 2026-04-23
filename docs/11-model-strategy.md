# L11 · 模型战略：以外部 LLM 为主，自研为辅

> 状态：**讨论中** · v0.1 · 2026-04-22 · 基于 OpenRouter / NotDiamond / RouteLLM / Notion / Glean / Sierra 等公开实践

## 0. 战略原则
**默认用外部前沿 LLM 做推理底座；自研 / 开源模型只在窄场景作为补充**——成本、合规、延迟、专门化。

理由：
1. 前沿能力**每 6-9 月翻倍**——追不上
2. 自部署通用大模型**几乎不划算**：日 token < 200 万时 API 完胜
3. 但**窄任务**（embedding / rerank / 分类 / PII）自部署比 API **便宜 10-100×**

## 1. 模型矩阵 2026-04（USD per 1M tokens）

| 模型 | 输入 | 输出 | 缓存输入 | 强项 |
|---|---|---|---|---|
| **Claude Opus 4.7** | $5 | $25 | ~$0.50 | Agent + 代码 SOTA (SWE-bench 87.6%) |
| **Claude Sonnet 4.6** | $3 | $15 | ~$0.30 | $/质量之王 |
| **Claude Haiku 4.5** | $1 | $5 | ~$0.10 | 快、1M context |
| **GPT-5.4** | $2.50 | $15 | -75% | 推理 + 工具调用 |
| **GPT-5.4-mini** | $0.75 | $4.50 | -75% | 中端 |
| **GPT-5.4-nano** | $0.20 | $1.25 | -75% | 高量低端 |
| **OpenAI o3** | $2.00 | $8.00 | -75% | 数学 / 科学纯推理 |
| **Gemini 2.5 Pro** | $1.25 / $2.50 (>200k) | $10 / $15 | 10% | 长上下文 + 多模态 |
| **Gemini 2.5 Flash** | $0.30 | $2.50 | 10% | 高量通用 |
| **Gemini 3.1 Flash-Lite** | $0.25 | $1.50 | - | 最便宜的 frontier-tier |
| **DeepSeek V3.2** | $0.28 | $0.42 | -50% off-peak | 最便宜的国产严肃模型 |
| **DeepSeek R1** | $0.55 | $2.19 | -75% off-peak | 最便宜的推理模型 |
| **Qwen3-235B Instruct** | $0.70 | $2.80 | - | 中文 + 工具强 |
| **Qwen3-235B Thinking** | $0.70 | $8.40 | - | 推理变体 |
| **Qwen3-32B / 7B** | 自部署 | - | - | edge / 微调底座 |
| **Kimi K2.5** | $0.60 | $2.50 | - | 长上下文 + 中文 |
| **GLM-4.5/4.6** | $0.60 | $2.20 | - | **BFCL v3 第一 (76.7%)**——工具调用王者 |
| **豆包 1.5 Pro** | ~¥0.8/¥2 | - | - | 国内合规、火山云内 |
| **Mistral Large 3** | $2.00 | $6.00 | - | 欧盟主权 |
| **Mistral Medium 3 / Small 4** | $0.40 / $0.15 | $2 / $0.60 | - | 中端 / 边缘 |

## 2. 能力 Benchmark 矩阵（2026-04）

| Bench | 第一 | 分数 | 备注 |
|---|---|---|---|
| GPQA Diamond | Opus 4.7 | 94.2% | 研究生科学 |
| SWE-bench Verified | Opus 4.7 | 87.6% | 真实 Github bug |
| LiveCodeBench Pro | Gemini 3.1 Pro | 2887 Elo | 防污染 |
| AIME 2025 | o3 / GPT-5.4 | ~95% | 纯数学 |
| **BFCL v3** | **GLM-4.5** | 76.7% | **工具调用——开源胜闭源** |
| τ-bench | Claude Mythos | 89.2% | 多轮企业工具 |
| RULER 1M | Gemini 2.5 Pro / Opus 4.6 | ~91% | 长上下文召回 |
| MRCRv2 1M | GPT-5.4 | 97 | 多 needle |
| CMMLU / C-Eval | Qwen3-235B / GLM-4.5 | 顶 | 中文 |

## 3. 路由策略（生产）

```
请求
│
├─ ① 合规 / residency 检查
│     ├─ 中国 → Doubao / Qwen3-235B (境内)
│     ├─ EU GDPR → Mistral Large 3 / Claude on Vertex EU
│     ├─ 离网 → 自部署 Llama 4 / Qwen3-32B → STOP
│     └─ 默认 → 继续
│
├─ ② 任务类型分类器 (1ms, 自部署 DeBERTa)
│     ├─ Embedding?         → bge-m3 (自部署)
│     ├─ Reranking?         → bge-reranker-v2-m3 (自部署)
│     ├─ PII / moderation?  → Presidio + Llama-Guard-4 (自部署)
│     ├─ 代码补全(IDE)?      → Qwen2.5-Coder-7B (自部署 edge)
│     ├─ 工具调用密集?       → GLM-4.5 或 Sonnet 4.6 (BFCL 领先)
│     ├─ 长文档 (>200k)?     → Gemini 2.5 Pro
│     ├─ 难推理?             → o3 / Opus 4.7 / DeepSeek R1
│     ├─ 中文 native?        → Qwen3-235B / GLM-4.5
│     └─ 通用 chat           → 继续
│
├─ ③ 语义缓存查找 (Bifrost / GPTCache)
│     └─ 命中 (>0.92 sim) → 返回 → STOP
│
├─ ④ 配额检查
│     ├─ 超预算? → 降级 tier 或拒绝
│     └─ OK     → 继续
│
├─ ⑤ Tier 内级联
│     ├─ T0/T1: 试 Haiku 4.5/Flash → 置信度
│     │           ├─ 高置信 → 返回
│     │           └─ 低置信  → 升级到 Sonnet 4.6
│     ├─ T2:    Sonnet 4.6 默认; Opus 按 flag
│     └─ T3:    Opus 4.7 + 全 audit log
│
├─ ⑥ 供应商 failover
│     └─ primary → secondary region → 跨厂商 → 开源
│
└─ ⑦ 事后: log token / 延迟 / 评分 → eval pipeline
```

## 4. Tier 分层（按用户 / 部门 / 场景）

| Tier | 用户 | 默认模型 | 允许升级 | 日预算 |
|---|---|---|---|---|
| T0 试用 | 外部评估 | Haiku 4.5 / Flash / DeepSeek V3.2 | 无 | $0.50/用户 |
| T1 标准 | 大多数员工 | Sonnet 4.6 + Haiku 级联 | 至 Sonnet | $5/用户 |
| T2 重度 | 工程 / 分析师 | Sonnet 4.6 默认, Opus 按需 | Opus 4.7, o3 | $50/用户 |
| T3 关键 | 法务 / 高管 / 合规 | Opus 4.7 + audit | 任何 | $200/用户 |
| T-中国 | 中国地区 | Doubao 1.5 Pro / Qwen3 / GLM-4.5 | 仅 VPC 内 | per dept |
| T-EU | EU GDPR | Mistral Large 3 / Sonnet (EU 区) | 仅 EU residency | per dept |
| T-Air-gap | 涉密 | 自部署 Llama 4 / Qwen3-32B | 无外部 | flat |

## 5. 何时自部署（盈亏平衡）

| 对比对象 | 盈亏点 |
|---|---|
| 前沿 API (GPT-4.1 级) | **2-3M token/天** ≈ $7.5K-15K/月 API → 8×H100 ($36K/月) 12 月摊销 |
| 最便宜开源 API (DeepSeek V3.2) | **15-20M token/天**，24-36 月才回本 |
| 云 GPU 租 (A100 $1.04/h) | 窄模型 ~30 万 token/天即划算 |
| 70B 自部署 (8×H100) 实际全成本 | $15-20K/月 |

**自部署条件（满足任一）**：
1. 单类模型持续 >2M token/天
2. 数据不能离场（涉密、医疗 PHI、监管金融）
3. 延迟预算 <50ms p50（API 仅 RTT 就 ≥150ms）
4. 微调模型在窄任务上比通用前沿 +5pp 以上
5. 多年确定性版本（监管行业）

## 6. 必须自部署的能力（无论是否用外部 LLM）

| 能力 | 推荐自部署 | API 替代 | 为什么自部署赢 |
|---|---|---|---|
| Embedding | **bge-m3** on A100 | OpenAI text-embedding-3-large $0.13/1M | 50% 利用率下 $0.01/1M——**便宜 10-100×**，月 7B token 以上明显 |
| Reranking | **bge-reranker-v2-m3** | Cohere Rerank 3 $1/1k | GPU 跑满免费，5-15ms vs 150ms |
| Intent classification | DeBERTa-v3 / Qwen3-7B 微调 | Haiku 4.5 | 200× 更便宜，亚 10ms |
| PII 检测 | Presidio + 自训 NER | API moderation | 数据不出场；零 per-token 成本 |
| Content moderation | Llama-Guard-4 / 微调 BERT | OpenAI Moderation (免费) | 免费 OK——除非 residency 强制 |
| 代码补全 (IDE) | Qwen2.5-Coder-7B / Codestral | Cursor/Copilot API | <50ms 延迟硬要求 |
| 域专用 (医/法) | Llama 4 / Qwen3-32B 微调 | Opus 4.7 | 专业词汇 + audit + 合规 |

## 7. Failover 级联模式

```
Primary: Sonnet 4.6 (us-east)
  └─ on 5xx / rate-limit / >3s TTFB →
       Secondary: Sonnet 4.6 via Bedrock (us-west)
         └─ on failure →
              Tertiary: GPT-5.4 (Azure OpenAI)
                └─ on failure →
                     Last-resort: DeepSeek V3.2
                       └─ on failure → 缓存响应或优雅降级
```
- 每 30s 健康探测
- 电路保险：连续 5 次失败 → 60s 冷却
- Idempotency key 防重试时双扣

## 8. 成本控制栈

1. **Prompt cache**（Anthropic 90%, OpenAI/Gemini 75-90%）—— >1k token system prompt 必做
2. **语义缓存**（GPTCache / Bifrost / Portkey）：FAQ 命中率 60-70%，10× 省钱 + 100× 省延迟
3. **预算上限**：per-user / per-dept / per-API-key，软阈值 80% 降档，硬阈值 100% 阻断
4. **Batch API**（OpenAI / Anthropic）：非实时打 5 折（夜间汇总、embedding 回填）
5. **错峰路由**（DeepSeek）：16:30-00:30 GMT 最高 -75%，定时任务排到这
6. **Token 感知截断**：对话历史按 1024-block 边界裁
7. **Output 预算**：max_tokens 按任务类——代码 2k，对话 500，分类 50

## 9. 真实企业架构参考

- **Notion**：Auto 模型路由 75% 流量；多供应商（Anthropic / OpenAI / Google）；自动 eval pipeline 按 cost / capability / 秒打分；高量窄任务降到开源
- **Glean**：Universal Model Key 跨 Azure OpenAI / Vertex / Bedrock；客户选 LLM 而数据留客户云；每 tenant 微调 embedding
- **Sierra**：Planner LLM + Executor LLM + Supervisor LLM 分别选；RAG 在前；推理框架在模型之外
- **Klarna**：客服整合到 OpenAI 之后内部其他任务仍多供应商；激进 prompt cache + retrieval

## 10. Vendor 锁定缓解（不可妥协）

- **每次调用走 gateway 层**（LiteLLM-compatible OpenAI schema 是事实通用语）
- Prompt 存**供应商无关 DSL**（Jinja 模板，模型相关只在叶子节点）
- **每夜 eval harness** 跨 ≥3 供应商跑同一 benchmark；leader 变化告警
- 多云合同：Anthropic 直接 + Bedrock + Vertex；OpenAI 直接 + Azure
- 始终保有 **1 个开源模型生产就绪**——任何供应商可一键切

## 11. MVP 范围
- 接 3 模型：Claude Sonnet 4.6（海外）+ Qwen3-32B + DeepSeek V3.2（国内）
- 基础规则路由 + 语义缓存
- per-tenant 日预算 + 限流
- Token / 成本入 Postgres
- LiteLLM 起步
- 自部署 bge-m3 + bge-reranker（必备）

## 12. 待决议
- [ ] 默认主 / 备模型矩阵
- [ ] 是否引入 learned router (RouteLLM 风格)
- [ ] 自部署优先级（embedding 必做，其他按业务量）
- [ ] 计费颗粒度（按 token / 按次 / 按订阅 / outcome-based）
