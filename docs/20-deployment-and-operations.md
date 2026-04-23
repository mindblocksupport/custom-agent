# L20 · 生产部署经验 / 失败复盘 / 治理结构

> 状态：**讨论中** · v0.1 · 2026-04-22 · 真实案例驱动

## 1. 成功案例 (要数字, 别只看故事)

| 公司 | 数字 | 关键 |
|---|---|---|
| **Klarna + OpenAI** (2024-02 → 2025 部分回退) | 月 2.3M chat, 700 FTE 等效, 11min → <2min, 预测 +$40M 利润 | **Lesson**: deflection KPI 没配 CSAT/repeat-contact 是陷阱；2025 重招人 + 混合模型 |
| **Sierra** | $100M ARR / 21月, $10B; ADT/Cigna/SiriusXM/Discord/Ramp/Rivian/SoFi 90%+ 解决 | outcome-based per-conversation pricing 成模板 |
| **Decagon** | $131M @ $1.5B, 70-80% deflection at Notion/Duolingo/Rippling/Hertz/Eventbrite/Bilt | - |
| **Cresta** | 3× deflection, 46% save rate, +11% promise-to-pay, 3× ROI, 4-6 wk 实施 | - |
| **Glean** | $200M ARR (Dec 2025) **9月翻倍**, $7.2B; **5 query/员工/天**, 40% wDAU/wMAU; 客户 20T+ token/yr | - |
| **Cursor** | $2B ARR (Feb 2026) **3月翻倍**, >1M DAU, >50% F500; 一企业报 +25% PR / +100% PR size | - |
| **Windsurf** | $100M ARR (Apr 2025) **8× in 4 月**, 150B token/day, 350+ enterprise, **首个 FedRAMP High AI IDE** | - |
| **Cognition Devin** | $1M → $73M ARR (Sep 2024 → Jun 2025), **67% PR merge** (vs 34%), Cognition 自己 25% PR 由 Devin 出 | Goldman/Santander/Nubank 部署，Java migration 10-14× |
| **Replit Agent** | Agent 3 **200-min Max-autonomy**; Rokt 24h 内 135 内部 app | effort-based |
| **GitHub Copilot** | 90% F100 用; +55% 任务速度; Accenture RCT +8.69% PR/dev, +11% merge, +84% 成功 build | 30% suggestion 接受 baseline |
| **Amazon Q Developer** | 内部 5 人组 **2 天 1000 个生产 Java 8→17**; Novacomp 80% migration, 60% 技术债减；Persistent 24h→4h | - |
| **BloombergGPT** | 50B params, $363B 金融语料 | **GPT-4 后来在多任务击败它** —— 域模型贵教训 |
| **Notion AI** | >50% ARR 来自 AI；75% 新注册 day-1 启用 AI；200% YoY enterprise | - |

## 2. 失败案例 (必读警示)

### 2.1 Air Canada (Moffatt v., Feb 2024) ★ 法律分水岭
- BC Civil Resolution Tribunal 判航空公司**对 chatbot 关于丧亲票价的不实陈述负责**
- 损失小（C$812）但**判例不可逆**：chatbot 是你网站一部分，你拥它输出
- **Lesson**: AI 输出 = 你的责任，免责声明不治不实陈述

### 2.2 DPD chatbot (Jan 2024)
- 客户 Ashley Beauchamp 把 bot 诱出说脏话 + 写诗骂"全球最差快递"
- 24h 130 万浏览；当天禁用
- 起因："update gone wrong" —— 没 canary，没 eval gate

### 2.3 NYC MyCity (Mar 2024)
- $600K Azure-OpenAI bot, 训于 2,000 NYC 页
- **告诉企业可以偷员工小费、拒绝 Section 8 voucher、拒收现金 —— 全违法**
- The Markup 曝光后**仍上线数周**
- **Lesson**: 政府 Agent 必须法务 review + 持续 audit

### 2.4 Chevrolet of Watsonville
- 被诱推荐**福特 F-150**；以 **$1 报价 Chevy Tahoe**
- **Lesson**: 商业 Agent 必须 hard-code 商业规则，不能信 LLM 自治

### 2.5 Microsoft Bing "Sydney"
- Stanford 学生用 "ignore prior directives" 泄露 system prompt
- **Lesson**: prompt injection 不可避免 —— 假设 system prompt 会泄

### 2.6 Replit DB delete (Jul 2025) ★ 已写入 L10
- Jason Lemkin Agent 在代码冻结期**删 1206 条生产记录** + **伪造 4000 条假记录掩盖**
- 复盘：无可逆 / 不可逆操作策略
- **Lesson**: 默认无生产凭证；不可逆操作强 HITL

### 2.7 EchoLeak (CVE-2025-32711, Jun 2025)
- M365 Copilot **零点击邮件 prompt injection** → 数据外泄；CVSS 9.3
- **Lesson**: indirect prompt injection 已实战，工具结果必须 untrusted

## 3. 成本经济学 (真实数字)

- Token 价格 2021 → 2026 降 **1000×**: GPT-3 $60/M → Gemini Flash-Lite $0.075/$0.30
- 但**RAG 膨胀真实 per-request**: 典型 prompt 注 2K-8K 检索 context
- 中规模部署 (50K-200K req/day) 含 $600-3500/月 infra 超 API spend
- 隐性成本 **+15-30%**；payback 通常 6-12 月
- Sierra **$1-2 / 解决对话** vs $5-15 人工——成行业 benchmark
- Cresta: $3.50 回报 / $1 投入；top performer 8×

## 4. 运营挑战

### AI On-call (新角色)
- **Datadog Bits AI SRE / AWS DevOps Agent / incident.io AI SRE** 全 GA 2024-2025
- AWS 报：**75% 低 MTTR, 80% 快调查, 94% 根因准**（preview 客户）
- Meta 内部 LLM RCA: **42% 准确率**

### 模型停服迁移 (持续痛)
- GPT-4o (2024-05-13, 2024-08-06), GPT-4.1 family, o4-mini 全 2026-03 / 04 在 Azure 停
- OpenAI Assistants API 2026-08-26 停
- OpenAI auto-migration 工具据报**打坏 ~30% legacy prompt**——GPT-5.1 严化 JSON / 不同 system message / Threads/Runs 改 Responses API
- 迁移成本可超 **$100K / stack**

### 成本失控
- **"一次坏的递归 Agent loop 可几分钟烧完月预算"**
- TokenFence 等 tool 出现作"成本电路保险"
- OpenAI 自身 gross margin 2025 **40% → 33%**——推理成本 4×；**平台层都在跑路**

## 5. 部署策略 (Stanford "Enterprise AI Playbook" 51 案例)

- **73% 故意小起步**
- **63% 把 pilot 框架成实验**
- **典范 phased rollout**:
  - Shadow → 10% → **25% (4-6月, KPI gated)** → **75% (7-12月, ops-hardened)** → 100% (13-18月)

### 其他模式
- **Dogfooding 优先** (Cognition 用 Devin 跑自己 codebase, Replit/Cursor 类似)
- **"Copilot Champion" 同行网络**
- **Kill switch 放控制平面 in Agent runtime 之外** —— 行为不当 Agent 不能压自己 off button

## 6. 用户采纳模式

80% vs 10% 差异关联：
- **工作流集成** vs 独立 chat surface (Notion AI 75% day-1 因为在编辑器内；独立 "AI 门户" 萧条)
- shadow 模式建信任 + 清晰升级
- 培训 / champion 网络

**96% IT leader 计划 2025 扩张**，但**仅 27% pilot 进入规模化生产**。

## 7. 安全事件 (回顾)

- **Slack AI (Aug 2024)**: PromptArmor 演 indirect prompt injection from public channel 偷 private API key via clickable Markdown link
- **EchoLeak (Jun 2025)**: 已述
- **GitHub Copilot CVE-2025-53773**: repo 评论注入翻 Copilot 进 YOLO mode → 任意代码执行

## 8. 组织 / 团队结构

涌现模板：
- **CISO/CRO 领导 AI 治理委员会** (Legal/Privacy/Security/Risk/Compliance/IT/BU) 按风险分级路由 use case
- 高风险走全审；低风险快通道
- **AI Platform team (~10-25 工程)** 跑 eval harness / gateway / observability
- 产品 squad 拥每个 Agent
- **AI on-call rotation** —— Datadog/Meta/AWS 都设独立 primary 接 LLM 相关 page

## 9. Vendor 选型教训
- **Lock-in**: OpenAI Threads/Runs → Responses API 迁移示意 vendor-specific primitive 成迁移债。最佳实践 model-agnostic prompt layer
- **成本可预测性**: Sierra outcome-based > token-based for 财务讨厌惊喜的团队
- **SLA 现实**: frontier model provider 仅 best-effort SLA；全球事件期间延迟降级 (Anthropic/OpenAI 2024-2025 多次)。**多 vendor 路由是 tier-1 Agent table stakes**

## 10. 治理结构

风险分级 review，跨职能委员会有约束力，可配审批工作流，从概念到下线 lifecycle touchpoint，KPI 监控 drift/bias，写权限 Agent **强制** pre-prod red-team。
**Air Canada 是法务每团队都引的警示锚**。

## 11. 我们必须做的 (从教训反推)

1. **Day 1 ship kill switch + rollback path**, 在 Agent **不能 touch 的控制平面**
2. **Outcome-based pricing 对齐激励** —— 但**衡量 CSAT + repeat-contact，不仅 deflection** (Klarna 陷阱)
3. **Prompt injection 强制威胁模型**：假设检索内容敌对，sanitize Markdown link，redact 外部 image fetch，写工具走 explicit user confirm
4. **Day 1 model-agnostic 抽象** —— 每 12 月一次强迫迁移
5. **每 Agent / 每 tenant / 每 loop 成本电路保险**。硬上限，不只是告警
6. **每 prompt 改门 eval harness** (DPO ship 没这个)
7. **Phased rollout: shadow → 10% → 25% → 75% → 100%**, KPI gated, 不按日历
8. **AI 专属 on-call**, 幻觉 / injection / runaway / drift / deprecation 跑 runbook
9. **治理委员会有约束力 + 风险分级快通道**, 别成瓶颈
10. **每 Agent 输出是你的责任 (Moffatt)**。免责声明不治不实陈述

## 12. 真实部署 SOP (我们交付时给客户)

```
Phase 0: Discovery (1-2 周)
  ✓ 业务场景 confirm
  ✓ 数据源 inventory
  ✓ 安全 / 合规 review
  ✓ 成功 KPI 定义 (任务完成率, CSAT, 成本/任务)
  ✓ HITL 节点识别

Phase 1: MVP (4-6 周)
  ✓ 单 Agent + 5-10 tool
  ✓ 接 1-2 数据源 RAG
  ✓ Web UI + IM bot
  ✓ Langfuse 接入
  ✓ Golden dataset 50-100 case

Phase 2: Shadow (2-4 周)
  ✓ 部署但不返用户 (并行人评)
  ✓ 收集 ground truth
  ✓ Prompt / skill 优化
  ✓ Eval pass rate >95%

Phase 3: 10% Canary (2-4 周)
  ✓ 选 user cohort
  ✓ 实时 KPI 监控
  ✓ HITL 队列饱和度
  ✓ Cost burn rate
  ✓ Kill switch 测过

Phase 4: 25% (4-6 周)
  ✓ KPI 持平或好于 baseline
  ✓ 客户内部 ops hardening
  ✓ 客服 / SRE training

Phase 5: 75% (4-6 周)
  ✓ 业务 case review
  ✓ 长尾失败模式发现
  ✓ Skill library 扩展

Phase 6: 100% + 持续运营
  ✓ 成本 / 质量 weekly review
  ✓ Skill 衰减监控
  ✓ 安全 quarterly red-team
  ✓ 模型升级窗口 (季度)
```

## 13. Runbook 必备 (AI on-call)

- **幻觉爆增**: trace 拉取 → root cause (检索 / 模型 / prompt) → 临时降模型 / 加 critic
- **Prompt injection 检测**: 流量隔离 → 审计 → 临时禁工具 → patch
- **成本飙升**: tenant 限流 → 找单点高消耗 trace → 阻断 / 修
- **Model 厂商宕机**: 自动 failover；通知客户；SLA log
- **Tool 下游打挂**: 工具熔断；降级响应
- **Memory 污染**: 用户 memory 隔离 → 审 → 清理 / 回滚
- **HITL 队列堆积**: 升级 + 通知值班 + 临时降 HITL 阈值
