# L7 · 可观测性 & 评测（Observability & Eval）

> 状态：**讨论中** · 版本 v0.2（重写版）· 2026-04-22
> 定位：企业级 Agent 平台「**可观测性如何被工程化地接入平台**」的工程层，承上启下连接 L18 / L21 / L22 / L23 / L25 / L33 / L35。

---

## 1. 本层职责（Scope）

> **没有可观测的 Agent，不可上线**。L7 的存在是为了让一切 Agent 行为可追溯、可解释、可改进。

L7 是「**可观测性数据的产生 / 采集 / 存储 / 查询 / 告警**」工程基础设施层，提供以下三大支柱 + 三大附加能力：

| 支柱 | 关键产出 | 主负责文档 |
|---|---|---|
| **Tracing 追踪** | trace tree、span attribute、跨服务上下文 | L7（本层） |
| **Metrics 指标** | 系统/LLM/Agent/业务 四层指标 | L7 + [L21](./21-cost-and-finops.md) |
| **Logs 日志** | 结构化日志 + 关联 trace_id | L7 + [L25](./25-audit-and-compliance.md) |
| **Eval 评测** | 离线 / 在线 / 实时质量信号 | L7 + [L18](./18-hallucination-and-safety.md) + [L23](./23-agent-sdlc-and-ci-eval.md) + [L35](./35-simulation-and-eval.md) |
| **Feedback 反馈** | 显式/隐式信号 → 待分析队列 | L7 + [L33](./33-data-flywheel-and-finetuning.md) |
| **Cost 成本** | 全链路 token / 调用费 → trace 关联 | L7 + [L21](./21-cost-and-finops.md) |

**关键边界划分（避免重复）**：

| 议题 | L7 负责 | 其它层负责 |
|---|---|---|
| 工具栈选型对比 | 引用 | [L16](./16-oss-stack.md) |
| 幻觉 / 安全攻击评测 | 提供数据 | [L18](./18-hallucination-and-safety.md) + Garak |
| FinOps 预算 / 配额 | 暴露 cost span | [L21](./21-cost-and-finops.md) |
| HITL 队列健康指标 | 暴露 hitl span | [L22](./22-hitl-and-approval.md) |
| CI 流水线评测门禁 | 暴露 eval API | [L23](./23-agent-sdlc-and-ci-eval.md) |
| 审计日志合规留存 | 提供 trace 原始数据 | [L25](./25-audit-and-compliance.md) |
| SFT / DPO 数据生产 | 提供 trace + feedback | [L33](./33-data-flywheel-and-finetuning.md) |
| 仿真用户交互评测 | 接收 trace | [L35](./35-simulation-and-eval.md) |

**商业价值**：客户敢续费的前提（数据驱动 ROI）、加速迭代（看得见才能改）、风险可控（坏 case 提前发现）、合规要求（金融/医疗必须可审计回放）。

---

## 2. OpenTelemetry GenAI Semantic Conventions 2026

2026 年 OTel 的 **GenAI Semantic Conventions v1.0**（即 `gen_ai.*` 命名空间）已 GA 稳定，是企业 Agent 可观测性的事实标准。**所有 L7 实现必须以 OTel GenAI 为基线**，再用 Langfuse / Phoenix 等做高级聚合。

### 2.1 核心 span 类型

| Span 名称 | 触发场景 | 必填属性 |
|---|---|---|
| `gen_ai.chat` | LLM Chat Completion 调用 | `gen_ai.system`, `gen_ai.request.model`, `gen_ai.response.id`, `gen_ai.usage.*` |
| `gen_ai.embeddings` | Embedding 调用 | 同上 + `gen_ai.request.input_tokens` |
| `gen_ai.tool.execute` | 工具/Function Call 执行 | `gen_ai.tool.name`, `gen_ai.tool.call_id` |
| `gen_ai.agent.invoke` | Agent 入口/子 Agent 调用 | `gen_ai.agent.name`, `gen_ai.agent.id` |
| `gen_ai.rag.retrieve` | RAG 检索（自定义扩展） | `gen_ai.rag.query`, `gen_ai.rag.top_k` |

### 2.2 标准属性（节选）

| 属性 | 类型 | 含义 |
|---|---|---|
| `gen_ai.system` | string | `anthropic` / `openai` / `vllm` / `qwen` |
| `gen_ai.request.model` | string | `claude-opus-4-7` / `gpt-5o-mini` 等 |
| `gen_ai.request.temperature` | double | 采样温度 |
| `gen_ai.request.max_tokens` | int | 上限 |
| `gen_ai.response.id` | string | 模型返回的 response_id（重要！客诉对账） |
| `gen_ai.response.finish_reasons` | string[] | `stop` / `length` / `tool_calls` |
| `gen_ai.usage.input_tokens` | int | 输入 token |
| `gen_ai.usage.output_tokens` | int | 输出 token |
| `gen_ai.usage.cached_tokens` | int | prompt cache 命中数（2026 标准化） |
| `gen_ai.usage.cost_usd` | double | 折算美元成本（自定义扩展） |
| `gen_ai.conversation.id` | string | 业务会话 ID（=tracing 里的 session_id） |
| `gen_ai.tool.name` | string | 工具名 |
| `gen_ai.tool.call_id` | string | 工具调用唯一 ID（与 LLM 返回 ID 关联） |

### 2.3 平台扩展属性（约定）

> OTel 标准之外，平台自定义命名空间统一以 `agent.*` 开头，方便与上游兼容。

| 属性 | 含义 |
|---|---|
| `agent.tenant_id` | 租户隔离 |
| `agent.scenario` | 业务场景（客服/销售/财务/...） |
| `agent.step_index` | Agent 内第几步 |
| `agent.hitl.required` | 是否触发 HITL |
| `agent.hitl.approver` | 审批人 |
| `agent.feedback.id` | 关联的反馈 ID |
| `agent.cost.tenant_bucket` | FinOps 计费桶（→ [L21](./21-cost-and-finops.md)） |

---

## 3. Trace 嵌套结构（完整示例）

> 一次「**请帮我查 12345 订单状态并发邮件给客户**」请求 = 一棵 Trace 树。

```
Trace  trace_id=tr_01HW...  session_id=s_77  user_id=u_42  tenant=acme
└─ Span  agent.invoke         name=customer_support_agent          0–4180ms
   ├─ Span  memory.retrieve   name=long_term_memory                0–35ms
   │        └─ Span  vector.search   k=8 hits=8 score=0.81
   ├─ Span  gen_ai.chat       name=LLM.plan       model=claude-opus-4-7   35–820ms
   │        attrs: usage.input=2104  usage.output=312  cached=1800  cost=$0.012
   │        output: "I need to call get_order then send_email"
   ├─ Span  gen_ai.tool.execute   name=get_order  call_id=t_01      820–1240ms
   │        ├─ Span  http.client    GET /orders/12345             820–1180ms
   │        └─ Span  db.query       SELECT * FROM orders          1180–1240ms
   ├─ Span  gen_ai.rag.retrieve   query="退款政策"                  1240–1520ms
   │        ├─ Span  embedding     model=bge-m3                   1240–1320ms
   │        ├─ Span  vector.search top_k=20                       1320–1430ms
   │        └─ Span  rerank        model=bge-reranker-v2-m3        1430–1520ms
   ├─ Span  gen_ai.chat       name=LLM.generate   model=claude-opus-4-7   1520–3920ms
   │        attrs: usage.input=4210  usage.output=580  cost=$0.028
   │        output: "Email draft: ..."
   ├─ Span  agent.hitl        approver=tier2_cs   wait_ms=120000  3920–4040ms (异步)
   ├─ Span  gen_ai.tool.execute   name=send_email   call_id=t_02   4040–4150ms
   └─ Span  audit.log         action=email_sent  pii_redacted=true  4150–4180ms
```

**关键约定**：
- `trace_id` 贯穿整个 session，**所有日志、metrics、feedback 都必须带 trace_id**。
- 异步流程（HITL、后台工具）用 `span.link` 串接，避免阻塞主 trace。
- 每个 LLM span **必须**记录完整 input/output（脱敏后），客诉时这是唯一证据。

---

## 4. 必须追踪的 Span 清单

| 类型 | 必填字段 | 备注 |
|---|---|---|
| **LLM call** | model / input / output / input_tokens / output_tokens / cached_tokens / cost / latency / finish_reason | 全量保留 ≥ 30 天 |
| **Tool call** | name / params（脱敏）/ result / latency / status / retry_count | 失败 100% 保留 |
| **RAG retrieve** | query / top_k / hits（id+score）/ rerank_score / chunks | 用于 [L3](./03-rag-and-knowledge.md) 复盘 |
| **Agent thought** | step_index / thought / chosen_action / reflection | ReAct/Plan-Execute 内部状态 |
| **HITL** | trigger_rule / approver / decision / wait_ms / sla_breached | → [L22](./22-hitl-and-approval.md) |
| **User feedback** | feedback_type / value / comment / linked_span_id | 显式 + 隐式 |
| **Audit** | actor / action / resource / outcome / ip | → [L25](./25-audit-and-compliance.md) |
| **Cost** | tenant_id / model / tokens / unit_price / total_usd | → [L21](./21-cost-and-finops.md) |

---

## 5. 观测工具选型（详细见 [L16](./16-oss-stack.md)）

> L16 已对完整 OSS 栈做选型。本层只锚定 L7 范围内的「**主轴**」。

| 角色 | 工具 | 理由 | 替代 |
|---|---|---|---|
| **主 Trace UI / 后台** | **Langfuse**（自部署） | Agent 原生、UI 业内最佳、Eval/Dataset/Prompt 一体化 | Phoenix |
| **采集 SDK** | **OpenLLMetry**（Traceloop） | 完全遵循 OTel GenAI 规范，自动 instrumentation 30+ LLM/框架 | OpenInference |
| **离线 Eval 框架** | **DeepEval** | pytest 风格、20+ 内置 metric、CI 友好 | Ragas（RAG）/ TruLens |
| **Prompt 回归测试** | **Promptfoo** | 跨模型 A/B、YAML 配置、CI 集成 | OpenAI Evals |
| **安全/红队 Eval** | **Garak**（→ [L18](./18-hallucination-and-safety.md)） | 50+ 攻击 probe，注入/越狱/PII 泄漏 | PyRIT |
| **指标 / 告警** | **Prometheus + Grafana** | 现成基建，OTel Metrics 直出 | VictoriaMetrics |
| **日志聚合** | **Loki / Elasticsearch** | trace_id 关联检索 | OpenSearch |
| **大数据存储** | **ClickHouse**（trace/span）+ **S3/OSS**（归档） | 千亿行 span 秒级聚合 | Doris |

**默认架构**：业务代码 → OpenLLMetry SDK → OTel Collector → 双写（Langfuse + ClickHouse + Prometheus）。

---

## 6. 采样策略（避免数据爆炸）

| 流量类型 | 采样率 | 理由 |
|---|---|---|
| 失败请求（status=error） | **100%** | 必须复盘 |
| 高耗时（latency > P99） | **100%** | 性能问题必查 |
| 用户点踩 / 转人工 | **100%** | 反馈来源 |
| 高价值用户（VIP / 大客户） | **100%** | 商业风险 |
| 关键业务场景（支付/合同/医疗） | **100%** | 合规要求 |
| 普通正常请求 | **1%–10%** | 防爆炸 |
| 健康检查 / 自动化测试 | **0%**（标记后丢弃） | 噪音 |

**实现要点**：在 OTel SDK 用 **head sampling + tail sampling** 组合 —— head 阶段先全采，tail 阶段在 Collector 根据 status/latency 决定保留。

---

## 7. 数据保留策略

| 阶段 | 时长 | 存储 | 用途 |
|---|---|---|---|
| **热** | 30 天 | Postgres / ClickHouse | 在线 UI 查询、告警、Dashboard |
| **温** | 90 天 | 对象存储 Parquet（按天分区） | 离线分析、Eval 数据集生成、SFT 数据挖掘 |
| **冷** | 6 月 – 5 年（按合规） | S3 Glacier / OSS 归档 | 客诉回放、审计、合规 |

**合规对照表**（→ [L25](./25-audit-and-compliance.md)）：

| 行业 | 最低保留期 | 法规依据 |
|---|---|---|
| 金融（银行/证券） | 5 年 | 银保监 / 证监会留痕 |
| 医疗（HIPAA） | 6 年 | HIPAA Security Rule |
| 政务 | 3 年 | 等保 2.0 三级 |
| 通用 SaaS | 6–12 月 | GDPR/PIPL 合理最小 |

**PII 处理**：所有 trace 入库前过 PII 脱敏管道（手机/邮箱/身份证/银行卡/姓名）；原文加密保留 7 天供客诉，之后销毁。

---

## 8. Metrics 分层

### 8.1 系统层（基础 SRE）

| 指标 | 定义 | SLO 参考 |
|---|---|---|
| latency P50 / P95 / P99 | 首字节 / 完整响应 | P95 ≤ 3s（chat） |
| QPS / TPS | 每秒请求 / 事务 | 容量规划 |
| error rate | 4xx / 5xx / tool_err / llm_err 分类 | < 0.5% |
| 资源 | CPU / RAM / GPU 利用率 | < 70% |

### 8.2 LLM 层

| 指标 | 用途 |
|---|---|
| input / output / cached tokens | 容量、cache 优化 |
| cost（按模型/租户/场景） | → [L21](./21-cost-and-finops.md) |
| 模型分布 | 哪些模型实际在用 |
| **prompt cache 命中率** | 2026 关键省钱指标 |
| 限流命中率 | provider quota / 自建限流 |

### 8.3 Agent 业务核心（**最关键的一层**）

| 指标 | 定义 | 业内基线 |
|---|---|---|
| **任务完成率 ★** | 用户意图被一次性完成的比例 | 60–85% |
| 平均步数 | Agent 完成任务的平均工具调用数 | 3–8 |
| 工具成功率（按工具） | tool 返回非 error 的比例 | > 95% |
| 工具命中率 | 任务中实际调用工具的比例（vs 仅闲聊） | 30–70% |
| **死循环率** | 单 trace 内同一 tool/思路重复 ≥ N 次 | < 0.5% |
| HITL 触发率 | 自动 → 人工的比例 | → [L22](./22-hitl-and-approval.md) |
| HITL 等待时间 | 触发到批复 P50/P95 | → [L22](./22-hitl-and-approval.md) |

### 8.4 用户层

| 指标 | 用途 |
|---|---|
| DAU / MAU / WAU | 活跃度 |
| 平均会话长度 | 粘性 |
| 满意度（点赞率 / NPS / CSAT） | 主观质量 |
| 留存（D1 / D7 / D30） | 产品健康 |
| 转人工率 | 客服场景关键 |

### 8.5 业务终极（按场景定制）

| 场景 | 终极指标 |
|---|---|
| 客服 | **一次解决率（FCR）**、CSAT、转人工率、单 case 成本 |
| 销售 | **线索转化率**、客单价、报价准确率 |
| 财务 | **自动化率**、错单率、人工 review 时长 |
| 研发 | **PR 合入率**、bug 修复时长、CI 通过率 |
| HR | 流程平均时长、员工满意度 |
| 法务 | 合同审查正确率、风险点召回率 |

---

## 9. Eval 体系

> 详细：单元/任务/端到端 三层切分思路与 [L23](./23-agent-sdlc-and-ci-eval.md) 的 CI 流程互补；安全/幻觉细节走 [L18](./18-hallucination-and-safety.md)；用户级仿真走 [L35](./35-simulation-and-eval.md)。

### 9.1 三层切分

| 层级 | 评估对象 | 工具 |
|---|---|---|
| **单元** | 单个 prompt / 单个 tool 输出 | DeepEval / Promptfoo / pytest |
| **任务** | 单个 Agent 完整任务 | DeepEval Agent metrics、自建 Runner |
| **端到端** | 多 Agent + 用户视角 | [L35](./35-simulation-and-eval.md) 仿真 + 真实用户 |

### 9.2 时机：离线 vs 在线

| 模式 | 数据源 | 时机 |
|---|---|---|
| **离线** | golden set / 边界 case / 生产采样 / 对抗样本 | PR / nightly / pre-release |
| **在线 shadow** | 实时流量副本（不返用户） | 灰度新模型/prompt |
| **在线 A/B** | 小流量实验 | 量化模型/prompt 收益 |
| **实时异常** | 流式扫描每条响应 | 守门员（→ [L18](./18-hallucination-and-safety.md)） |

### 9.3 评测方法对比

| 方法 | 适用 | 优势 | 劣势 |
|---|---|---|---|
| **规则**（regex / schema / exact match） | 结构化输出、JSON、SQL | 准、便宜、可重复 | 仅结构化 |
| **统计**（BLEU / ROUGE / BERTScore） | 翻译、摘要 | 客观 | 与人感知差距大 |
| **LLM-as-Judge** | 开放问答、多轮、推理 | 灵活 | 不稳定、成本高 |
| **人工标注** | 金标准、新场景 | 最准 | 慢、贵 |
| **业务指标** | 上线后衡量 | 终极标准 | 反馈周期长 |

### 9.4 LLM-as-Judge 实操要点

1. **裁判模型选强**：`claude-opus-4-7` / `gpt-5o`，避免「同模型自评」偏差。
2. **结构化 rubric**：每个维度 1–5 分 + 评分理由 + few-shot 示例。
3. **多次平均**：N=3 取平均，方差 > 1 触发人工 review。
4. **与人工对齐**：每月抽样 100 条人工复评，计算 judge-human Cohen's κ，要求 ≥ 0.6；不达标重写 rubric。
5. **盲评**：A/B 时不告诉 judge 哪个是新版本。
6. **温度=0**，固定 seed。

---

## 10. RAG 专项 Eval（详见 [L3](./03-rag-and-knowledge.md)）

> 工具：**Ragas** 主，TruLens 备。集成在 DeepEval 里也可用。

| 维度 | 含义 | 触发改进点 |
|---|---|---|
| **Faithfulness** | 答案是否被检索到的上下文支持（不杜撰） | 拆段策略、prompt 强化引用 |
| **Answer Relevance** | 答案是否切题 | prompt 重写 / query 改写 |
| **Context Precision** | top-k 中相关 chunk 的位次 | rerank、index 质量 |
| **Context Recall** | 应该被检索到的相关 chunk 是否被检索到 | 拆段策略、embedding 模型升级 |
| **Noise Sensitivity** | 噪音 chunk 是否影响答案 | 上下文压缩、过滤 |

---

## 11. Agent 专项 Eval

| Benchmark | 评估什么 | 借鉴价值 |
|---|---|---|
| **AgentBench** | 跨 8 类环境的通用 Agent 能力 | 通用基线 |
| **SWE-bench / SWE-bench Verified** | 真实 GitHub issue 修复 | 研发场景 |
| **GAIA** | 真实世界多步推理 | 通用助手 |
| **τ-bench** | 多轮工具调用 + 用户交互（航空/零售） | 客服/交易场景 |
| **OSWorld** | 真机操作系统/桌面 Agent | RPA / 桌面助手 |
| **WebArena / VisualWebArena** | 浏览器 Agent | 网页自动化 |
| **自建任务集** | 业务场景 50–500 case | **必须有，公开 benchmark 替代不了业务** |

**评估深度**：
- **结果级**：最终输出对不对（核心）。
- **步骤级**：每一步工具选得对不对、参数对不对、思路是否冗余。
- **效率级**：步数、token、时延、成本。

---

## 12. Feedback Loop（反馈闭环）

```
显式 feedback (👍/👎/评分/文字)  ┐
                                  ├──→ 关联 trace_id ──→ 待分析队列
隐式信号 (会话短/复制/追问/转人工) ┘                          │
                                                              ↓
                                                   人工标注 + LLM 自动分类
                                                              │
                                            ┌─────────────┬───┴────┬───────────────┐
                                            ↓             ↓        ↓               ↓
                                       Prompt 优化    Tool 修复  KB 补充    SFT/DPO 候选
                                                                            ↓
                                                                  → L33 数据飞轮
```

| 反馈类型 | 信号 | 采集时机 |
|---|---|---|
| **显式** | 👍/👎、星级、文字评论 | 消息级 + 会话级 |
| **隐式正向** | 用户复制结果、点击链接、停留长 | 前端埋点 |
| **隐式负向** | 立即追问 / 重发 / 转人工 / 关闭会话 | 行为分析 |

**关键工程**：
- 每条 feedback **必须**关联到具体 `span_id`（不是 trace 顶层），定位到「错在哪一步」。
- 待分析队列容量超阈值告警，避免堆积。
- LLM 自动分类（提示问题 / 工具问题 / 知识缺失 / 模型能力 / 用户操作误解）作为初筛，人工只 review 高置信样本。
- 高质量正反馈 trace + 修复后的负反馈 trace → 进入 [L33](./33-data-flywheel-and-finetuning.md) 微调候选池。

---

## 13. 告警

### 13.1 维度

| 维度 | 示例规则 |
|---|---|
| **可用性** | error_rate > 1% 持续 5 分钟；P99 latency > 10s |
| **质量** | 点踩率 > 5% / 任务完成率周环比下降 ≥ 10% / hallucination 检测命中率突增 |
| **成本** | 日成本 > 阈值；单租户成本异常（→ [L21](./21-cost-and-finops.md)） |
| **安全** | 注入命中、越权访问、PII 泄漏（→ [L18](./18-hallucination-and-safety.md) + [L25](./25-audit-and-compliance.md)） |
| **业务** | 转人工率突增、客户投诉、HITL 队列堆积（→ [L22](./22-hitl-and-approval.md)） |

### 13.2 分级

| 级别 | 含义 | 响应 SLA | 通道 |
|---|---|---|---|
| **P0** | 服务不可用 / 大规模数据问题 | ≤ 5 min | PagerDuty 电话 + 全员钉钉 |
| **P1** | 质量明显下降 / 单租户重大故障 | ≤ 1 h | PagerDuty + 值班群 |
| **P2** | 成本异常 / 趋势恶化 | 工作时间响应 | 钉钉/飞书机器人 |
| **P3** | 优化建议 | 周报 | 邮件 |

### 13.3 告警工程化

- 所有告警**必须带 trace_id 链接**到 Langfuse，2 秒打开现场。
- 抑制策略：相同 fingerprint 5 分钟内合并；夜间低优自动延后。
- 月度复盘：告警数量、误报率、MTTR。

---

## 14. Dashboard 设计

| 受众 | 内容 | 刷新 |
|---|---|---|
| **实时大屏** | QPS / 延迟 / 错误率 / 实时成本 / 异常事件流 / 当前 HITL 队列 | 5s |
| **业务报表（日/周/月）** | 任务完成率趋势 / 成本趋势 / 满意度 / 按租户钻取 | 小时 |
| **个人 / 团队** | 我的对话 / 我消耗的 tokens / 我的反馈 / 团队 ROI | 实时 |
| **运维 SRE** | SLO 燃尽图 / Top 慢查询 / 错误 Top 10 | 1m |
| **算法/产品** | Eval 趋势 / 模型对比 / Prompt 版本对比 | 触发 |

---

## 15. 数据 Schema 示例

```sql
-- 一次用户请求
CREATE TABLE trace (
  id              TEXT PRIMARY KEY,
  session_id      TEXT NOT NULL,
  user_id         TEXT NOT NULL,
  tenant_id       TEXT NOT NULL,
  scenario        TEXT,
  start_at        TIMESTAMPTZ NOT NULL,
  end_at          TIMESTAMPTZ,
  total_input_tokens   BIGINT,
  total_output_tokens  BIGINT,
  total_cost_usd       NUMERIC(10,6),
  status          TEXT,                  -- ok/error/timeout
  error           TEXT,
  metadata        JSONB
);

-- 一个 Span（嵌套）
CREATE TABLE span (
  id              TEXT PRIMARY KEY,
  trace_id        TEXT NOT NULL REFERENCES trace(id),
  parent_span_id  TEXT,
  name            TEXT NOT NULL,         -- gen_ai.chat / gen_ai.tool.execute / ...
  kind            TEXT NOT NULL,         -- llm / tool / rag / agent / hitl / audit
  start_at        TIMESTAMPTZ NOT NULL,
  end_at          TIMESTAMPTZ,
  duration_ms     INT,
  input           JSONB,                 -- 已脱敏
  output          JSONB,                 -- 已脱敏
  attributes      JSONB,                 -- gen_ai.* + agent.*
  status          TEXT,
  error           TEXT
);

CREATE INDEX idx_span_trace ON span(trace_id);
CREATE INDEX idx_span_kind_start ON span(kind, start_at);

-- 用户反馈
CREATE TABLE feedback (
  id              TEXT PRIMARY KEY,
  trace_id        TEXT NOT NULL,
  span_id         TEXT,                  -- 精准到某一步
  user_id         TEXT,
  type            TEXT,                  -- like/dislike/score/comment/implicit_*
  value           NUMERIC,
  comment         TEXT,
  source          TEXT,                  -- explicit/implicit
  created_at      TIMESTAMPTZ DEFAULT now()
);

-- 评测记录
CREATE TABLE eval_run (
  id              TEXT PRIMARY KEY,
  dataset_id      TEXT,
  dataset_version TEXT,
  agent_version   TEXT,
  prompt_version  TEXT,
  model           TEXT,
  metrics_json    JSONB,                 -- {accuracy: 0.83, faithfulness: 0.91, ...}
  samples_count   INT,
  trigger         TEXT,                  -- ci/manual/scheduled
  triggered_by    TEXT,
  created_at      TIMESTAMPTZ DEFAULT now()
);
```

> 大数据场景下，建议 trace/span 用 ClickHouse 列存（按 `tenant_id, toYYYYMMDD(start_at)` 分区），保留 30–90 天热数据；归档走 Parquet → S3。

---

## 16. MVP 范围（4 周交付）

| 周 | 交付物 |
|---|---|
| W1 | Langfuse 自部署（Docker Compose）+ OpenLLMetry SDK 接入 1 个 Agent |
| W2 | 完整 trace（LLM/工具/RAG/Agent step）+ Postgres 持久化 + 基础 Dashboard |
| W3 | Prometheus + Grafana 接入系统/LLM/Agent 4 类核心 metrics + 显式点赞点踩 |
| W4 | 50 条 golden set + DeepEval CI 跑通 + 钉钉告警机器人（P0/P1） |

**MVP 之后立即排期**：PII 脱敏管道、Tail sampling、ClickHouse 切换、Promptfoo 接入。

---

## 17. 真实坑总结

| # | 坑 | 缓解方案 |
|---|---|---|
| 1 | **数据量爆炸**：10K DAU = 数百万 span / 天，Postgres 撑不住 | 必须 tail sampling + ClickHouse + 90 天归档 |
| 2 | **trace 含 PII**：手机/身份证/银行卡明文存储 = 合规事故 | 入库前过脱敏管道；原文加密 7 天必删 |
| 3 | **LLM-as-Judge 不稳定**：同 case 不同次评分能差 20% | N=3 平均 + 方差报警 + 月度人工对齐 |
| 4 | **Eval 集易过拟合**：跑了 3 个月发现改 prompt 只为通过 Eval | 持续加 case（生产采样 + 红队 + 客诉），版本化数据集 |
| 5 | **业务 vs 模型指标背离**：模型 Eval 涨了 10%，业务转化没动甚至降 | 优先业务指标；Eval 只是必要不充分条件 |
| 6 | **告警疲劳**：阈值乱设 → 一天几百告警 → 没人看 | 分级 + 抑制 + 月度复盘误报率；只允许 P0 电话 |
| 7 | **历史 trace = 客户投诉证据**：客户说「上周三 Agent 给我发错单」时，没 trace 就是赔钱 | 关键场景 100% + 长保留；trace_id 嵌入用户 UI 用于客服查询 |
| 8 | **OTel 版本兼容**：2024–2025 期间 `gen_ai.*` 字段名几次大改 | 锁定 OpenLLMetry 版本；升级前跑回归 |
| 9 | **prompt cache 不计费透明**：开发同学以为缓存命中省了钱，实则模型涨价了 | metric 必区分 `cached_tokens` vs `input_tokens` |
| 10 | **多租户 trace 串扰**：调试时把 A 租户 trace 给了 B 工程师 | 强制 `tenant_id` filter + RBAC + 审计读操作 |

---

## 18. 待决议

- [ ] Langfuse 自部署 vs SaaS（数据出境合规 / 维护成本权衡）
- [ ] 热数据存储：Postgres 起步 vs 直接 ClickHouse
- [ ] 评测 CI 频率：每 PR / nightly / pre-release（建议三级组合，详见 [L23](./23-agent-sdlc-and-ci-eval.md)）
- [ ] 用户反馈是否对租户开放查看（让客户看自己 ROI）
- [ ] LLM-as-Judge 是否使用同模型自评（自评偏差 vs 成本权衡）
- [ ] Eval golden set 标注外包 vs 内部
- [ ] 是否提供「客户自助 trace 查询」入口（合规边界）
- [ ] OTel Collector 部署形态：sidecar vs DaemonSet vs Gateway
- [ ] 跨 region trace 聚合（多 region 部署时）

---

> 关联文档：[L3 RAG](./03-rag-and-knowledge.md) · [L10 安全](./10-security.md) · [L16 OSS 栈](./16-oss-stack.md) · [L18 幻觉与安全](./18-hallucination-and-safety.md) · [L21 FinOps](./21-cost-and-finops.md) · [L22 HITL](./22-hitl-and-approval.md) · [L23 Agent SDLC](./23-agent-sdlc-and-ci-eval.md) · [L25 审计合规](./25-audit-and-compliance.md) · [L33 数据飞轮](./33-data-flywheel-and-finetuning.md) · [L35 仿真评测](./35-simulation-and-eval.md) · [L36 模型供应链](./36-model-supply-chain.md)
