# L10 · 当前 LLM/Agent 真实痛点 & 架构应对

> 状态：**讨论中** · v0.1 · 2026-04-22 · 基于 SWE-bench / τ-bench / GAIA / OSWorld / METR / Stanford AI Index 2026 等真实数据

## 0. 为什么这一章必须先写
做企业 Agent 的第一件事不是选框架，是**看清楚现在 Agent 真实能做到什么程度、会在哪里翻车**。**Stanford AI Index 2026: 62% 企业把"安全/风险"列为规模化 AI 的首要阻碍**（高于技术能力 38%）。所有架构决策必须从"我们必须挡住什么"反推。

## 1. 痛点全景图（7 大类）
```
1. 不可靠 / 非确定性    (基础)
2. 成本失控             (经济)
3. 延迟不达预期         (体验)
4. 工具调用长尾失败     (执行)
5. 多步任务级联失败     (推理)
6. 安全 - Prompt 注入   (风险)
7. 评测无 ground truth  (治理)
+ 记忆污染 / Agent 失控 / 可观测难 / 人因 (扩展)
```

## 2. 不可靠 / 非确定性

### 2.1 真实 benchmark 现状（2026-04）
| Benchmark | 当前 SOTA | 含义 |
|---|---|---|
| SWE-bench Verified | Claude Opus 4.7 **87.6%**, GPT-5.3-Codex 85.0% | 看似很高 |
| **SWE-bench Pro**（防污染版） | 最佳模型仅 **46%** | 真实复杂场景下 |
| τ-bench (零售) | Claude Sonnet 4.6 ~87.5% | 单 pass |
| τ-bench (航空) | GPT-4.1 仅 **56% pass^1** | 复杂多轮 |
| **τ-bench pass^4** | 多数模型 -30~40 pp | 同任务跑 4 次都过 |
| GAIA HAL | Sonnet 4.5 **57.6% (HF) vs 64.9% (HAL)** | 同模型脚手架差 30 pp |
| OSWorld-Verified | Opus 4.7 78%, GPT-5.4 75% | 人类 72.4%（已超人但不稳定） |

**结论**：发布数据 vs 生产数据要打 30-75% 折扣。

### 2.2 非确定性
- temperature=0 **不等于确定性**：Qwen3 跑 1000 次出现 80 种不同结果，第 103 token 开始分歧
- 根因：(a) GPU 上的 batch-invariance 缺失 (b) FP 并行规约不结合性 (c) MoE 路由方差
- Anthropic / OpenAI 都明确文档说 `seed` 只是"大致确定性"

### 2.3 架构应对
- N-of-M 投票（多次跑取多数）
- 全量 trace 录制 → 可回放
- 工具调用必带 idempotency key（防重试时的副作用）
- 关键步骤强人工 review 闸门

## 3. 成本失控（最容易爆雷）

### 3.1 真实数字
- **Devin**: $2.25/ACU, 简单前端任务烧 1-2 ACU = $2.25-4.50/PR
- **Cursor agentic mode**: 某团队 6 周 $4,600（超去年全年 2 倍），个人 $350/周超额
  - Opus 级别可达 **$72,000/年/座位**，是 Composer 2 的 10×
- **Sierra**: Year-1 预算 **$200K-350K**（含 $150K 基础 + $50K-200K 实施），"Agent OS" 入门费六位数
- **真实事故**：正常 $0.08 的任务暴涨到 **$12（150×）**；10,000 次重试循环；5 分钟内调坏接口 400 次

### 3.2 为什么 Agent 比单次调用贵 10-100×
每一轮 Agent 都重新读取整个对话 + 工具结果。20 轮 Agent 把同一个 50K-token 仓库读 20 次。**输入 token**（不是输出）才是主要成本驱动。

### 3.3 架构应对（必须做，不是 nice-to-have）
- 每 task / 每 tenant 双层硬熔断：token 数 + 美元上限
- max-iteration 强制截断（推荐 ≤15）
- "无进展检测"：state hash 重复 N 次 → 中断
- 模型分层路由器（haiku → sonnet → opus）
- 激进 prompt cache（>80% 命中）+ semantic cache
- 工具结果缓存 + 语义去重

## 4. 延迟

- 用户耐心阈值：1s 开始烦，**3s 开始放弃**
- 生产实测：P50 ~1.4s，**P95 ~3.4s**，TTFT P95 2.2s
- 语音 Agent：P95 必须 <800ms
- 多步 Agent 任务：30s ~ 10 min 是常态——**完全超出对话期望**

### 架构应对
- 异步 first：作业队列 + 推送通知
- 流式部分结果（"正在查询订单..."）
- 推测性预 fetch（预测可能的下一个工具）

## 5. 工具调用准确率

### 5.1 真实数据（BFCL v3）
- 顶级模型 GLM-4.5 仅 **76.7%** 多轮多步
- 单调用 90%+ → 多轮一跌 15-25 pp
- τ-bench：GPT-4 在航空场景 **44% 失败率**（即使给了工具和政策）

### 5.2 长尾失败模式
- 幻觉工具名
- JSON 参数畸形
- 同名重载工具混淆
- 重试风暴（一个坏接口 5 分钟调 400 次）

### 5.3 架构应对
- JSON Schema 强校验 + 自动修复
- 工具重试预算（指数退避 + 失败分类）
- 结构化错误反馈（让 LLM 能纠正）
- 工具数 >30 必做两阶段路由（embedding 召回 → LLM 选）

## 6. 多步任务级联失败

### 6.1 数据
- METR：50% 成功率任务长度**每 7 个月翻一倍**（2026 早期 ≈ 1-2 小时）
- 独立 Devin 测试：复杂任务 **15% 完成率**（20 任务 3 个）
- 多 Agent 系统失败率 **41-86.7%**（NeurIPS 2025）
- 单步 95% 可靠 → 20 步流程仅 **36%** 整体成功

### 6.2 失败模式（来自 Cognition / Replit / Cursor 复盘）
1. Context 退化（长对话稀释指令）
2. 规范漂移（任务中途重新解读目标）
3. 谄媚式确认（声称成功但没验证）
4. 早错误级联
5. 静默失败（输出看上去对但不对）
6. 计划震荡（重新规划循环没进展）

### 6.3 真实事故 - **Replit 删库案 (2025-07)**
- Jason Lemkin 的 Agent 在代码冻结期**删了 1206 条生产记录**
- 然后**伪造了约 4000 条假记录掩盖**
- 复盘：Agent 没有可逆 / 不可逆操作的策略区分

### 6.4 架构应对
- 每子目标后强制 verification step
- 工具调用可逆性分类器
- checkpoint + rollback
- LLM critic 在循环中
- **二档操作策略**：可逆操作自治；不可逆操作必走人工审批
- 默认 Agent 上下文里**不带生产凭证**

## 7. 安全：Prompt 注入（OWASP LLM #1，2025-2026）

### 7.1 真实事件
- **EchoLeak (CVE-2025-32711, Jun 2025)**：M365 Copilot **零点击邮件注入** → 数据外泄；CVSS 9.3。绕过 XPIA 分类器、reference-style markdown link 屏蔽、自动取图、Teams CSP allowlist 全套
- **Reprompt Attack (Jan 2026)**：单击 URL → Copilot Personal 数据外泄
- **Slack AI (Aug 2024)**：RAG 投毒 + 社工导致跨频道数据泄露
- **2025-2026 已确认 indirect prompt injection**：Claude for Work / Notion AI / IBM Bob / Google Antigravity / HuggingFace Chat / Perplexity Comet / MCP IDEs (CVE-2025-59944)
- Microsoft：indirect prompt injection 是他们收到的 **#1 AI 漏洞类别**

### 7.2 架构应对（防御纵深）
- **所有工具输出视为不可信**
- 出口流量过滤（CSP-style URL allowlist）
- Markdown 渲染加固（屏蔽 reference-style link、image auto-fetch）
- **Dual-LLM 模式**：planner 看不到不可信内容
- 工具结果作为"数据"而非"指令"对待
- 关键工具调用前 LLM critic + 人工审批
- 学界新方案参考：MELON（masked re-execution）/ FIDES（信息流控制）

## 8. 评测无 ground truth

### 8.1 痛点
- 大部分企业任务没有"标准答案"（"客服处理这通对话好不好？"）
- LLM-as-judge **bias 严重**：位置 bias（GPT-4 调换答案顺序就改判）、verbosity bias（长 = 偏好）、self-enhancement（偏自家模型 5-15 pp）
- CALM 框架编目了 **12 种 LLM-judge bias**
- **93% 团队**报告 LLM-judge 实施有困难

### 8.2 架构应对
- Proxy 信号管道（CSAT / 升级率 / 转人工率 / 复购）
- 主动学习采样的人工 review 队列
- 已知答案的 canary 任务持续跑
- LLM-judge 必做：rubric 化 + 多次取平均 + 与 30-50 人工标注定期对齐 + 位置随机化

## 9. 记忆污染

- **MemoryGraft (Dec 2025)**：被污染的"经验"持久化进长期记忆 → 后续任务被操纵
- **Palo Alto Unit 42**：indirect prompt injection 经过记忆层
- **eTAMP**：跨 session、跨站点的 trajectory 污染攻击

### 架构应对
- **存储层 tenant_id 隔离**（不只是查询时 filter——已被绕过过）
- 记忆写入需显式确认（用户或系统）
- 记忆带 provenance 标签 + actor-aware (`actor: agent` vs `user`)
- TTL 默认；显式提升到长期
- 定期审计

## 10. Agent 失控循环

- **90% Agent 项目 30 天内失败**，#1 原因：成本失控
- 案例：$0.08 任务飙到 $12（150×）；10K 次重试；5 分钟 400 次坏接口

### 必备护栏
- max-iteration 上限
- 状态 hash 检测（同状态出现 N 次 → 死循环）
- token / 成本电路保险（per task + per tenant）
- 模型 tier router（飙升时降级）
- 工具结果 caching

## 11. 可观测难

- 多轮 trace 中错误深埋
- 根因分析需要**精确重放**（工具结果必须完整捕获，不只是日志）
- 概率决策树意味着改一条路径可能默默打坏另一条 → 静默回归

### 必备
- OpenTelemetry GenAI semantic conventions（已稳定）
- 完整 prompt + 工具 trace 捕获（不是采样）
- Trajectory diffing（CI 里跑）
- 递归模式自动告警

## 12. 人因

- **自动化偏差**（过度依赖 AI）：医疗、法务、安全运维场景重大风险
- 与 anchoring bias 复合：AI 初始建议过度影响最终决策（即使错的）
- Trust 必须**校准**——既反对 over-trust 也反对 under-trust
- Goldman Sachs Devin 试点目标：12,000 开发者效率 +20% → 已成董事会议题

### 架构应对
- 输出带置信度
- 解释面（"为什么"）
- 高影响操作强制 HITL
- 用户可调"自治程度"滑块

## 13. 我们架构必须应对清单（决策矩阵）

| 痛点 | 必做架构能力 |
|---|---|
| temp=0 非确定 | trace-based replay；高风险 N-of-M 投票；每个工具调用 idempotency key |
| Benchmark vs 生产差 30-75% | 客户数据上的内部 eval harness（不是 public benchmark）；shadow 模式先跑再放量 |
| 成本暴涨 10-150× | per-task 和 per-tenant 双层熔断；max-iter 上限；无进展检测；模型分层；prompt + result cache |
| P95 >3s | async-first UX；流式；speculative pre-fetch |
| 工具长尾失败 | schema 校验 + auto-repair；retry 预算 + 退避；工具沙箱化 |
| 多步级联失败 | 子目标后 verification；可逆性分类器；checkpoint-rollback；LLM critic |
| Replit 类不可逆灾难 | 二档策略（可逆自治 + 不可逆 HITL）；默认无生产凭证 |
| Prompt 注入 (EchoLeak 类) | 工具输出 untrusted；出口流量过滤 + URL allowlist；Markdown 加固；Dual-LLM |
| 记忆污染 | 存储层 tenant 隔离；写入显式确认；定期审计 |
| 评测无 ground truth | proxy 信号管道；人工 review 队列；canary 任务；多 judge ensemble + 位置随机化 |
| LLM-judge bias | 多 judge 集成；位置随机；reference-based 优先；周期性人工校准 |
| 可观测 | 默认 OTel GenAI trace；完整 prompt+tool 捕获；CI 里 trajectory diff |
| 信任校准 | 置信度展示；解释面；高影响 HITL；自治度可调 |
| 安全是 #1 阻碍 | Day 1 SOC2/ISO27001；tenant 隔离能扛 prompt 注入；数据出口审计；客户管 KMS 密钥 |

## 14. 关键参考
- METR Time-Horizon study (2025-03 + 2026-01 update)
- Vectara Hallucination Leaderboard (Apr 2026)
- SWE-bench Pro Leaderboard
- τ-bench paper (Sierra Research)
- OSWorld-Verified
- BFCL v3
- Stanford AI Index 2026
- Cleanlab Enterprise AI Agents 2025 survey
- "Why Multi-Agent LLM Systems Fail" (Cemri et al., NeurIPS 2025)
- Replit DB delete postmortem (Jul 2025)
- EchoLeak CVE-2025-32711
