# L23 · Agent SDLC / 生命周期管理

> 状态：**讨论中** · v0.1 · 2026-04-22 · 把 Agent 当软件管 vs 当玩具

## 0. 为什么独立成章
- 企业 Agent 不是"上线一次了事"——会持续 dirft / 模型停服 / skill 衰退
- 没 SDLC 就是"个人项目"——出事不可重现、不可回滚、不可问责
- **2025 出现 Agent SDLC (ADLC) 新词**——Arthur AI / EPAM 都正式定义

## 1. 5 阶段 ADLC 框架

```
┌─────────────────────────────────────────────────────────────┐
│  1. Ideation / Design                                        │
│     业务 case → 风险评估 → 数据可行性 → eval 标准定义        │
├─────────────────────────────────────────────────────────────┤
│  2. Inner-loop Development                                   │
│     Agent 定义 → tool 接入 → prompt 迭代 → 本地测            │
├─────────────────────────────────────────────────────────────┤
│  3. Test / Validate                                          │
│     CI eval → red team → simulation → 性能基线               │
├─────────────────────────────────────────────────────────────┤
│  4. Deploy                                                   │
│     Shadow → canary → 灰度 → 全量；BYOC / SaaS / 私有化       │
├─────────────────────────────────────────────────────────────┤
│  5. Monitor / Tune                                           │
│     trace + KPI + 反馈 → 周 / 月迭代 → eventual sunset       │
└─────────────────────────────────────────────────────────────┘
```

## 2. Agent 定义格式（推荐 git-stored）

```yaml
# agents/customer_support_v2.yaml
name: customer_support
version: 2.3.1
description: |
  Tier-1 客服 Agent。处理订单、退换、物流问题。
  转人工：投诉、技术故障、超 ¥5000 退款。

owner: support-team@acme.com
risk_level: L3  # 涉及发邮件 / 改订单
tier: T2

# 能力
model:
  primary: claude-sonnet-4-6
  fallback: [qwen3-235b, deepseek-v3.2]
  routing_policy: cost_optimized

skills:
  - order_query@1.5
  - refund_calc@2.0
  - send_template_email@1.2
  
tools:
  - query_order
  - query_logistics
  - calc_refund
  - send_email (HITL: amount > 100)
  - escalate_to_human
  
knowledge_bases:
  - support_docs@2026-04-15
  - product_specs@2026-04-01
  
memory:
  - user_profile (read)
  - last_30d_session (read)
  - preferences (read/write)

# 安全 / 合规
guardrails:
  - pii_redaction
  - profanity_filter
  - chinese_compliance
  
hitl:
  required_for:
    - "refund > 5000"
    - "delete_order"
    - "send_promotional_email"

# Eval
eval_dataset: support_golden_v3.4
min_pass_rate: 0.95
sla:
  p95_latency_ms: 3000
  cost_per_task_max_cny: 0.3

# 部署
deployment:
  channels: [web, dingtalk, feishu]
  tenants: [tenant_a, tenant_b]
  rollout: canary_25_percent
  kill_switch_enabled: true
```

**关键设计**：所有依赖（model / skill / KB / tool / dataset）**全 pin 版本**。

## 3. 版本化策略

### 3.1 Semver
- `MAJOR.MINOR.PATCH`
- MAJOR: 破坏性变更（去掉 skill / 改 schema）
- MINOR: 新能力 / 新 skill
- PATCH: bug fix / prompt 微调

### 3.2 不可变 release
- 一旦 release，**不能改**——只能新版本
- 每 release 包含完整 snapshot：prompt / model / skill / KB version
- Agent runtime 按 version 加载（多版本共存）

### 3.3 多版本共存
- 一些客户在 v2.3，一些在 v3.0（灰度中）
- 退订流程：deprecated → sunset (6 月) → archived

## 4. Dev → Staging → Canary → Production

```
┌──────────┐  PR    ┌──────────┐  CI eval  ┌──────────┐
│   Dev    │──────→ │ Staging  │──────────→│  Canary  │
│          │        │          │           │  (10%)   │
└──────────┘        └──────────┘           └────┬─────┘
                                                 │ 7 day KPI
                                                 ▼
                                           ┌──────────┐
                                           │   25%    │
                                           └────┬─────┘
                                                 │ 14 day KPI
                                                 ▼
                                           ┌──────────┐
                                           │ Production│
                                           └──────────┘
```

每阶段必须门控：
- **Dev → Staging**: PR + code review
- **Staging → Canary**: 全 eval suite pass + 安全 review
- **Canary 7d → 25%**: KPI 不退化 (任务完成率 / CSAT / 成本)
- **25% 14d → Production**: 同上 + 业务 sign-off

## 5. CI / CD 集成（GitHub Actions 例）

```yaml
on:
  pull_request:
    paths:
      - 'agents/**.yaml'
      - 'prompts/**.md'
      - 'skills/**'

jobs:
  validate:
    steps:
      - schema_validate (yaml linter)
      - skill_dependency_check
      - cost_budget_check (estimate)
      
  eval:
    steps:
      - ragas_rag_metrics
      - deepeval_pytest
      - promptfoo_yaml_tests
      - inspect_ai_agent_eval
      
  red_team:
    steps:
      - garak_scan (基础)
      - promptfoo_red_team (自定义)
      
  cost_estimate:
    steps:
      - run_eval_set
      - estimate_cost_per_task
      - block_if_over_threshold
```

## 6. A/B 测试基建

```
[请求]
   ↓
[路由器: experiment_assignment]
   ↓
   ├──50%──→ [Agent v2.3.1 (control)]
   └──50%──→ [Agent v2.4.0-beta]
   
[Langfuse 标 experiment_id]
[业务指标按 experiment 切片]
[统计显著性自动计算]
```

实验设计：
- **Power calculation**（典型 1-2 周/臂中等流量）
- 主指标 + 防御指标（成本不能涨太多）
- Multi-armed bandit 加速（Thompson sampling，比固定 A/B 快 ~37% 找 winner）

## 7. 回滚 Playbook

| 触发 | 行动 |
|---|---|
| 任务完成率 -5% | 自动 rollback (kill switch) |
| 成本 +30% | 自动降流量 50% |
| 安全事件（注入 / 数据泄露） | 立即下线 + 隔离 |
| CSAT 跌 | 24h 内 review；不行就 rollback |
| 模型 vendor 宕机 | failover 到备模型 |

**Kill switch 必须在 Agent runtime 之外**——Agent 不能压自己 off button。

## 8. Skill / Tool 依赖管理

```
Agent v2.3.1
  ├─ skill: order_query@1.5
  │    └─ tool: query_order_db (deprecated 2026-06)
  ├─ skill: refund_calc@2.0
  │    └─ depends: tax_rules@2026
  └─ ...
```

- **依赖图**自动生成
- **过期警告**：依赖快下线时通知 owner
- **强制升级窗口**：deprecation 6 月 → 必须迁

## 9. 模型 deprecation 处理

**真实痛**: Azure 2026-03/04 停 GPT-4o + GPT-4.1 + o4-mini；OpenAI Assistants API 2026-08-26 停。OpenAI auto-migration **打坏 ~30% legacy prompt**。

我们的 SOP：
1. **接收 vendor deprecation 通知** → 入 backlog
2. **影响分析**：哪些 Agent 用此模型？
3. **新模型 eval**：跑 golden set
4. **迁移 PR**：改 agent.yaml 模型字段
5. **Shadow 测试**
6. **Canary**
7. **全量**
8. **deprecation 前 30 天必须完成**

## 10. Sunset 流程

| 阶段 | 时长 | 行动 |
|---|---|---|
| **Deprecation 公告** | T0 | UI 显示，文档标 |
| **新增禁止** | T0 | 不能再创建新使用 |
| **Migration window** | 6 月 | 客户迁移期 |
| **强制升级 / 关闭** | T+6m | 仍未迁的客户被切 |
| **Archive** | T+12m | 代码归档，可历史查 |

## 11. 部署形态

| 形态 | 适合 | 我们交付 |
|---|---|---|
| **Our SaaS** | SMB | 完全托管 |
| **Customer cloud (BYOC)** | 中大型 | Helm 进客户 K8s, 控制平面我们 SaaS |
| **私有化 (on-prem)** | 政企 / 涉密 | 离线安装包 + 离线模型镜像 |
| **Edge (端) ** | 终端 / IoT | 极简 runtime + 小模型 |

## 12. Agent Registry / Marketplace（前瞻）

像 Slack App / OpenAI GPT Store / MCP registry：
- 内部 marketplace（员工可发现 / 订阅 Agent）
- 跨 tenant marketplace（合作伙伴上架）
- 收入分成
- 安全审核 + 治理 review

## 13. 合规 audit log

每 Agent lifecycle 事件入审计：
```sql
agent_audit_log (
    id, agent_name, version,
    event_type (create / deploy / kill / sunset / eval),
    actor_user_id, actor_role,
    diff_from_previous,
    ts, ip
)
```

满足等保 + EU AI Act 高风险 Agent audit 要求。

## 14. 实施清单
- [ ] Agent 定义 YAML schema 锁定
- [ ] git 仓库 `agents/` 结构
- [ ] 版本管理（semver + immutable release）
- [ ] CI eval pipeline
- [ ] A/B 路由器（基于 user / experiment）
- [ ] Kill switch（Agent runtime 之外）
- [ ] 灰度发布工具
- [ ] 模型 deprecation 跟踪 board
- [ ] Sunset SOP
- [ ] Audit log + 合规导出
- [ ] Internal Agent registry / marketplace（v2）

## 15. 前瞻
- **GitOps for Agent**: Agent 定义 = git；ArgoCD 自动同步
- **Agent observability standard**: OTel GenAI 已稳定 → 跨 vendor 通用 trace
- **Agent identity**: Workday ASOR + Microsoft Entra Agent ID 暗示——每 Agent 有 ID + signed audit
- **Cross-vendor agent collab (A2A)**: Google A2A v1.0 (Apr 2026) 加 Signed Agent Cards
- **Agent 评级 / 认证**: 类比 ISO27001 for AI——AI Verify, EU AI Act 合格
