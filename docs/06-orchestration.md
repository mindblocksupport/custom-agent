# L6 · 编排层 (Orchestration)

> 状态：**讨论中** · 版本 **v0.2 重写版** · 2026-04-22
> 受众：平台架构师、Workflow Engine 维护者、业务 Agent 开发者
> 一句话：L6 把"单 Agent 一次推理"升级为"多 Agent + 长流程 + HITL + 可补偿"的**业务级工作流**。

---

## 0. 本层定位与边界

| 层 | 关注点 | 关键产出 |
|---|---|---|
| [L5 Agent Core](./05-agent-core.md) | **单 Agent** 的推理 / 工具调用 / 一次任务的完整闭环 | `Agent.run()` 一次调用 |
| **L6 Orchestration（本层）** | **多 Agent 协作 + 长流程 + DAG + HITL 编织** | `Workflow.start()` → 跨 Agent / 跨人 / 跨天 |
| [L7 Observability](./07-observability.md) | Trace / Metric / Log / Replay | OTel span tree、Workflow timeline |
| [L16 Engine 选型](./16-engines.md) | OSS 引擎调研（Temporal / LangGraph / Restate / Hatchet …） | 选型矩阵、PoC 结论 |
| [L22 HITL UX](./22-hitl-ux.md) | 审批界面、推送渠道、超时升级、移动端、批量审批 | 审批组件库 + 推送 SDK |
| [L23 Agent SDLC](./23-agent-sdlc.md) | Workflow 定义版本化、灰度、回滚、CI/CD | Workflow Registry + Pipeline |
| [L34 A2A](./34-a2a.md) | 跨组织 / 跨 Agent 平台的协作（远期） | A2A 协议、信任模型 |

**L6 不做什么**：
- 不重新发明工具调用 → 由 L5 Agent Core 完成
- 不画审批表单像素 → 由 L22 HITL UX 负责
- 不写"哪个引擎更好" → 由 L16 给出结论；本层只声明**怎么用**
- 不规范跨公司 Agent 通信 → 由 L34 接管
- 不做 trace UI → 由 L7 提供

**L6 的核心交付**：
1. **多 Agent 拓扑**（Supervisor / Pipeline / Hierarchical / Critic 等模式）
2. **Workflow Runtime 抽象**（屏蔽 LangGraph / Temporal 差异）
3. **HITL 节点协议**（暂停 / 推送 / 等待 / 恢复 / 超时）
4. **长任务对外 API**（POST/GET/SSE/cancel/resume）
5. **Saga 补偿与 DLQ**
6. **Workflow 数据模型与版本化**

---

## 1. 何时需要多 Agent / 长流程？

> **不要为了多 Agent 而多 Agent**。80% 的业务场景，单 Agent + 工具就够。

### 1.1 决策树

```
用户需求
  │
  ├─ 单轮对话能完成？ ── YES ──► L5 单 Agent
  │                       NO
  │                        ▼
  ├─ 单 Agent + ReAct 工具循环能完成？ ── YES ──► L5 单 Agent + Tools
  │                                       NO
  │                                        ▼
  ├─ 流程 < 5 分钟、不跨人工？ ── YES ──► L6 LangGraph 状态机
  │                              NO
  │                               ▼
  ├─ 跨人工 / 跨天 / 必须可补偿？ ── YES ──► L6 LangGraph + Temporal
  │                                NO
  │                                 ▼
  └─ 多组织 / 跨平台协作？ ──────────► L34 A2A（v1 不做）
```

### 1.2 真正需要多 Agent 的信号

| 信号 | 单 Agent 行不行 | 多 Agent 收益 |
|---|---|---|
| 角色边界清晰（销售 / 法务 / 财务） | 勉强，prompt 很乱 | 角色独立、可独立迭代 |
| 工具数量 > 50 | 选错率飙升 | 各 Agent 工具集 < 15 |
| 需要并行（多专家同时分析） | 串行慢 | 并行加速 N 倍 |
| 需要"裁判 / 复核" | 容易自吹自擂 | Critic Agent 提质 |
| 不同步骤需要不同模型 | 浪费 token | Supervisor 用 Opus，子 Agent 用 Haiku |
| 流程必须可建模 / 审计 | 黑盒 | DAG 可视化 |

### 1.3 反信号（别上多 Agent）

- "感觉这样更智能" → **不**，调试成本 3 倍
- "可以让 Agent 互相讨论" → 80% 是无用对话、烧 token
- "客户希望看到很多 Agent 在工作" → 用 UI 假装就行，后端单 Agent
- "未来可能扩展" → YAGNI，需要时再拆

---

## 2. 多 Agent 模式对比

| 模式 | 拓扑 | 优势 | 劣势 | 适用场景 | 推荐度 |
|---|---|---|---|---|---|
| **Supervisor（主从）** | 1 主 N 从，主控调度 | 清晰、可控、易调试、易审计 | Supervisor 是瓶颈 / 上下文压力 | 80% 业务场景 | ★★★★★ |
| **Hierarchical（层级）** | 多级 Supervisor 树 | 大型组织建模、分而治之 | 链路长、延迟高、故障定位难 | 复杂企业流程（>10 个 Agent） | ★★★ |
| **Network/Swarm（网状）** | Agent 互相 P2P 调用 | 灵活、涌现性 | 难调试、状态混乱、易死循环 | 探索 / 创意 / 辩论 | ★★ |
| **Pipeline（流水线）** | A → B → C 串行 | 简单、确定性、可断点 | 无并行、无回路 | 审批流、ETL、内容生产线 | ★★★★ |
| **Critic / Reviewer** | 主 Agent 输出 → 评审 → 反馈 | 质量提升 20-40% | 慢一倍、token 翻倍 | 代码 PR、内容生成、合规审 | ★★★★ |

### 2.1 Supervisor（推荐缺省）

```
              ┌───────────────┐
              │  Supervisor   │ ← 接收用户请求 / 总控
              │ (路由 + 总结) │
              └───────┬───────┘
                      │ structured handoff
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   ┌────────┐    ┌────────┐    ┌────────┐
   │AgentA  │    │AgentB  │    │AgentC  │
   │销售    │    │财务    │    │法务    │
   └────────┘    └────────┘    └────────┘
```

- Supervisor **不**直接调业务工具，只负责路由 + 汇总
- 子 Agent 互相**不认识**（避免网状）
- 子 Agent 输出走**结构化 schema**，不走自由文本

### 2.2 Hierarchical（大型组织）

```
            Top Supervisor
           /              \
      Sales Sup        Service Sup
      /     \           /     \
   Lead   Quote    Ticket   Knowledge
```

- 每个 Sub-Supervisor 维护自己的子 Agent 池
- 适合 > 10 个 Agent、跨部门复用

### 2.3 Pipeline（流水线）

```
[Intake] → [Enrich] → [Classify] → [Decide] → [Notify]
```

- 每步可独立超时 / 重试 / 替换
- 强烈推荐做成**Workflow as Code**（LangGraph / Temporal），不要写成一个大 Agent

### 2.4 Critic / Reviewer

```
[Author Agent] ─output─► [Critic Agent] ─verdict─► [Author Agent revise]
                              │ approve
                              ▼
                          [Publish]
```

- 关键参数：**最多迭代次数**（默认 2，多了不收敛）
- Critic 用更强模型 + 独立 prompt（避免同一模型自我认可）

### 2.5 Network/Swarm（慎用）

> 看起来很 cool，调试地狱。需要时再上。常见死锁：A 等 B，B 等 C，C 等 A。

---

## 3. Workflow 引擎选型（详见 [L16](./16-engines.md)）

L16 给出完整调研，本层做**用法决策**。

### 3.1 引擎矩阵（2026 Q2 视角）

| 引擎 | 类型 | 优势 | 劣势 | L6 用途 |
|---|---|---|---|---|
| **LangGraph 1.0** | Agent 状态机 / DAG | Agent 原生、checkpointer、Streaming、社区活跃 | Python only、长任务弱 | **短任务推理编排**（默认） |
| **Temporal** | Workflow as Code | 工业级、durable execution、OpenAI Agents SDK 已 GA（2026-03）、多语言 | 重、学习曲线、自托管贵 | **长任务 / 关键流程 durability** |
| **Restate** | Durable Execution | BSL 协议、轻量、SQLite/FoundationDB、API 比 Temporal 友好 | 生态新、企业案例少 | Temporal 替代候选 |
| **Dapr Workflow** | CNCF graduated | 多语言、跟 Dapr 生态打通、Side-car | 抽象多、调试难 | Service Mesh 已用 Dapr 时考虑 |
| **Trigger.dev v3** | TS-friendly Job runner | DX 好、内置 UI、Realtime | 偏短任务、多租户企业能力弱 | TS 团队短任务 |
| **Inngest** | Event-driven | Serverless 友好、并发控制 | 厂商锁定（Cloud） | 事件驱动场景 |
| **Hatchet** | Postgres-only Queue | 单库部署、低运维 | 小生态、规模未验 | 中小团队、想省运维 |
| **Airflow / Prefect** | DAG / ETL | 老牌、可视化、社区大 | **粒度错** —— 为离线批跑设计，不适合在线交互 Agent | 离线批处理 |
| **Camunda** | BPMN | 企业 BPM 标准、有可视化 | 老派、与 LLM 集成生硬、JVM 重 | 必须 BPMN 兼容时 |
| **n8n / Dify / Coze** | Low-code 可视化 | 业务方可拖、上手快 | **复杂场景必撞墙**、版本控制差、性能弱 | 业务前置 / 原型 |

### 3.2 推荐组合 ★

> **LangGraph（推理） + Temporal（durability）**
>
> LangGraph 负责"一次会话内的推理 + 工具循环 + Agent 协作"，
> Temporal 负责"跨人工 / 跨服务重启 / 跨天的工作流持久化与重试"。

```
┌────────────────────────── Temporal Workflow ──────────────────────────┐
│                                                                       │
│   step1: parseInput          ◄── activity (idempotent)                │
│   step2: runLangGraphAgent   ◄── activity 包裹一次 Agent 推理         │
│   step3: requestHITL         ◄── activity → 暂停 → signal 唤醒        │
│   step4: callBackend         ◄── activity (Saga: 注册补偿)            │
│   step5: notifyUser                                                   │
│                                                                       │
│   compensation: undoBackend, refund, ...                              │
└───────────────────────────────────────────────────────────────────────┘
                ▲
                │ 一次 step2/3 内部
                │
        ┌───────┴────────┐
        │ LangGraph node │  ← 多 Agent 推理 / 工具循环
        │ checkpointer   │
        └────────────────┘
```

**为什么不用 Temporal 做 Agent 内部循环？**
Temporal 每个 activity 持久化一次太重，Agent 一秒钟可能 10 次工具调用。
**为什么不用 LangGraph 做长流程？**
LangGraph 的 checkpointer 是给"会话续杯"用的，不是给"七天后老板回来审批"用的。

### 3.3 排除清单

- ❌ Airflow / Prefect 做 Agent 编排：粒度不匹配，调度器不为亚秒级在线请求设计
- ❌ 纯 n8n / Dify 做生产业务：业务方爽 1 周，开发哭半年
- ❌ 自研 Workflow Engine 做 MVP：你不会比 Temporal 写得好

---

## 4. 真实业务场景

### 4.1 报销审批 Agent（Pipeline + HITL）

```
┌──────────┐
│ 用户上传  │
│ 发票图片  │
└────┬─────┘
     │
     ▼
┌──────────────────────┐
│ Step1: OCR + 字段抽取 │  ← LangGraph node, activity 包裹
│   Agent (Vision)      │
└────┬─────────────────┘
     │
     ▼
┌──────────────────────┐
│ Step2: 合规检查        │  ← 工具：政策库 / 历史报销
│   Agent + 规则引擎     │
└────┬─────────────────┘
     │
     ▼
┌──────────────────────┐
│ Step3: 决策路由        │
│   金额 > 5000？需主管  │
└─┬──────────────────┬─┘
  │ NO              │ YES
  │                  ▼
  │         ┌──────────────────┐
  │         │ Step4: HITL 审批  │ ← Temporal pause + signal
  │         │   推送主管 (L22)  │   超时 24h 升级到部门长
  │         └────┬─────────────┘
  │              │ approved
  │◄─────────────┘
  ▼
┌──────────────────────┐
│ Step5: 录入财务系统    │ ← 注册补偿：撤销凭证
│   (Saga compensable)  │
└────┬─────────────────┘
     │
     ▼
┌──────────────────────┐
│ Step6: 通知申请人      │
└──────────────────────┘
```

| 关键设计 | 说明 |
|---|---|
| 引擎 | Temporal 总框 + LangGraph 跑每个 Agent step |
| 跨度 | 几小时到几天 |
| 状态持久化 | Temporal history（必须） |
| HITL | 推送钉钉 / 飞书（详见 [L22](./22-hitl-ux.md)） |
| 补偿 | 录入失败 → 回滚 OCR 缓存、通知用户重传 |
| 审计 | 每步 step_run 记录，trace 关联（详见 [L7](./07-observability.md)） |

### 4.2 销售助手（Supervisor 多 Agent）

```
                 ┌──────────────────┐
                 │   Supervisor      │
                 │  (路由 + 汇总)     │
                 └─┬─┬─┬─┬─┬────────┘
                   │ │ │ │ │
       ┌───────────┘ │ │ │ └────────────┐
       │   ┌─────────┘ │ └────────────┐ │
       ▼   ▼           ▼              ▼ ▼
  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
  │ 客户研究 │ │ 需求分析 │ │ 方案匹配 │ │  报价    │ │ 文档生成 │
  │  Agent  │ │  Agent  │ │  Agent  │ │  Agent  │ │  Agent  │
  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘
       │         │         │         │         │
       └─────────┴────┬────┴─────────┴─────────┘
                      ▼
                 ┌─────────────────┐
                 │ Supervisor 汇总  │
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐
                 │ HITL: 销售审核    │ ← L22
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐
                 │  发送给客户       │
                 └─────────────────┘
```

| 关键设计 | 说明 |
|---|---|
| 拓扑 | Supervisor + 5 个并行 sub-Agent |
| 引擎 | LangGraph（推理为主，单次会话内完成） |
| 通信 | 黑板模式（共享 state），子 Agent 之间不直接通信 |
| 模型分层 | Supervisor=Opus，子 Agent=Sonnet/Haiku |
| HITL | 终审 1 个节点（不要每步都审，审死人） |

### 4.3 故障应急（运维 Critic + Pipeline）

```
[告警] → [诊断 Agent: 日志/监控/变更] → [Critic 评审根因, conf<0.7 回退]
       → [处置方案生成] → [HITL: SRE 审核, 超时 5min 拉电话]
       → [执行 Agent (调 K8s/Ansible, Saga 补偿)]
       → [验证 Agent (监控 5min)] → [复盘报告生成]
```

| 关键设计 | 说明 |
|---|---|
| 引擎 | Temporal（必须 durable，重启不丢） |
| 拓扑 | Pipeline + Critic（诊断阶段） |
| HITL | 关键节点强制人工，超时升级 |
| 补偿 | 每个执行动作必须可回滚或可跳过 |
| 观测 | 全程 OTel trace，审计强制（[L7](./07-observability.md)） |

---

## 5. HITL 集成（详见 [L22](./22-hitl-ux.md)）

### 5.1 HITL 节点协议（L6 提供）

```python
# pseudo-code
@workflow.defn
class ReimburseFlow:
    @workflow.run
    async def run(self, req):
        ocr = await wf.execute_activity(ocr_invoice, req)
        if ocr.amount > 5000:
            decision = await wf.wait_for_signal(
                signal="hitl_decision",
                timeout=timedelta(hours=24),
                on_timeout=ESCALATE,        # 超时升级
            )
            if decision == "reject":
                return Rejected(reason=decision.reason)
        ...
```

### 5.2 L6 ↔ L22 接口

| 方向 | 接口 | 说明 |
|---|---|---|
| L6 → L22 | `POST /hitl/requests` | 创建审批请求（含上下文 / 摘要 / 决策选项） |
| L22 → L6 | `signal hitl_decision` | 推送审批结果回到 Workflow（resume） |
| L6 → L22 | `PATCH /hitl/requests/{id}/escalate` | 超时升级 |
| L22 → L6 | `POST /hitl/batch_decide` | 批量审批回调 |

### 5.3 哪些节点必须 HITL

| 场景 | 触发条件 | 默认行为 |
|---|---|---|
| 不可逆（删除 / 转账 / 发邮件） | 总是 | 强制审批 |
| 高金额 | 超过策略阈值 | 强制审批 |
| 模型置信度低 | confidence < 0.7 | 询问审批 |
| 用户主动设置 | 用户偏好 | 询问 |

---

## 6. 长任务管理

### 6.1 异步任务对外 API

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/v1/tasks` | 提交任务，返回 `task_id`，立即 202 |
| `GET` | `/v1/tasks/{id}` | 查询当前状态 / 进度快照 |
| `GET` | `/v1/tasks/{id}/stream` | SSE 实时事件流（步骤、token、HITL） |
| `POST` | `/v1/tasks/{id}/cancel` | 取消（触发补偿） |
| `POST` | `/v1/tasks/{id}/resume` | 恢复（HITL 通过 / 错误重试） |
| `POST` | `/v1/tasks/{id}/signal` | 任意 signal（HITL 决策、外部事件） |
| `GET` | `/v1/tasks/{id}/history` | 完整步骤记录（审计） |

### 6.2 任务状态机

```
                ┌───────────┐
                │  pending  │
                └─────┬─────┘
                      │ start
                      ▼
                ┌───────────┐
       ┌────────┤  running  ├─────────┐
       │        └─────┬─────┘         │
       │              │ wait_signal   │ error
       │              ▼               │
       │        ┌───────────┐         │
       │        │  paused   │         │
       │        │ (HITL/IO) │         │
       │        └─────┬─────┘         │
       │              │ resume         │
       │              ▼                ▼
       │ cancel ┌───────────┐    ┌───────────┐
       └───────►│ cancelled │    │  failed   │
                └───────────┘    └─────┬─────┘
                                       │ retry/compensate
                                       ▼
                                 ┌───────────┐
                                 │ completed │
                                 └───────────┘
```

### 6.3 进度反馈

| 粒度 | 形式 | 例子 |
|---|---|---|
| Workflow 级 | step `i/N` + 摘要 | "5/10 步：正在生成报告" |
| Step 级 | 工具调用透明 | "正在查询订单系统..." |
| Token 级 | 流式 | OpenAI 风格 chunk |
| HITL 级 | 等待者 + 等待时长 | "等待主管审批，已等 12 分钟" |

### 6.4 失败与补偿（Saga）

| 模式 | 适用 | 注意 |
|---|---|---|
| **重试** | 幂等 / 临时故障 | 指数退避 + 抖动 + 最大次数 |
| **Saga 补偿** | 多步事务、不可分布式锁 | 每步都要写好补偿；**已发邮件/短信无法补偿** → 走"人工通知 + 道歉信"路径 |
| **DLQ** | 超过 N 次仍失败 | 入死信队列，告警 SRE，留人工处理界面 |
| **断路器** | 下游持续失败 | 暂停整个 Workflow 类，避免雪崩 |

**Saga 设计真相**：很多业务**根本无法补偿**，要在 Workflow 设计时把"不可逆步骤"放到 HITL 之后，确保人工已确认。

---

## 7. 多 Agent 通信

| 模式 | 描述 | 优势 | 劣势 | 推荐 |
|---|---|---|---|---|
| **黑板（Blackboard）** | 共享 state，每个 Agent 读写 | 简单、解耦 | 写冲突、状态漂移 | ★★★★ Supervisor 缺省 |
| **结构化交接（Handoff）** | 上一个 Agent 输出严格 schema 给下一个 | 可校验、可审计 | 需要定义 schema | ★★★★★ Pipeline 缺省 |
| **消息传递（Message）** | Agent 互发消息，类似 actor | 灵活、并发 | 调试难、易死锁 | ★★ 仅 Network 模式 |
| **自由对话** | Agent 互相聊天 | 看着热闹 | 烧 token、无收敛 | ❌ 禁用 |

**强制规范**：
- Supervisor → 子 Agent：**结构化 input**，禁止丢一段自由文本
- 子 Agent → Supervisor：**结构化 output**（含 confidence / citations），禁止 markdown 文章
- 子 Agent ↔ 子 Agent：**禁止直接通信**，必须经 Supervisor

---

## 8. 数据模型

```sql
-- 工作流定义（版本化）
CREATE TABLE workflow_def (
  id              BIGSERIAL PRIMARY KEY,
  name            TEXT NOT NULL,
  version         INT  NOT NULL,                    -- 版本号
  engine          TEXT NOT NULL,                    -- langgraph | temporal
  definition_json JSONB NOT NULL,                   -- 节点 / 边 / Agent 引用
  schema_hash     TEXT NOT NULL,                    -- 防止线上漂移
  owner_team      TEXT,
  status          TEXT NOT NULL,                    -- draft | active | deprecated
  created_at      TIMESTAMPTZ DEFAULT now(),
  UNIQUE (name, version)
);

-- 工作流实例
CREATE TABLE workflow_run (
  id               UUID PRIMARY KEY,
  workflow_def_id  BIGINT REFERENCES workflow_def(id),
  tenant_id        UUID NOT NULL,
  user_id          UUID,
  trace_id         TEXT,                            -- 关联 L7
  status           TEXT NOT NULL,                   -- pending|running|paused|completed|failed|cancelled
  current_step     TEXT,
  state_json       JSONB NOT NULL,                  -- 黑板 state
  parent_run_id    UUID,                            -- 子工作流父引用
  started_at       TIMESTAMPTZ,
  completed_at     TIMESTAMPTZ,
  error            JSONB,
  INDEX (tenant_id, status, started_at DESC)
);

-- 步骤执行记录（审计 + 重放）
CREATE TABLE step_run (
  id               UUID PRIMARY KEY,
  workflow_run_id  UUID REFERENCES workflow_run(id),
  step_name        TEXT NOT NULL,
  step_type        TEXT NOT NULL,                   -- agent|tool|hitl|branch|loop
  agent_id         TEXT,                            -- 若是 agent step
  input_json       JSONB,
  output_json      JSONB,
  status           TEXT NOT NULL,
  attempt          INT  DEFAULT 1,
  trace_span_id    TEXT,                            -- L7 关联
  started_at       TIMESTAMPTZ,
  ended_at         TIMESTAMPTZ,
  error            JSONB
);

-- HITL 审批
CREATE TABLE hitl_request (
  id               UUID PRIMARY KEY,
  workflow_run_id  UUID REFERENCES workflow_run(id),
  step_run_id      UUID REFERENCES step_run(id),
  approver_id      UUID,
  approver_group   TEXT,                            -- 部门 / 角色
  channel          TEXT,                            -- dingtalk|feishu|email|app
  payload_json     JSONB,                           -- 摘要 + 上下文 + 选项
  status           TEXT NOT NULL,                   -- pending|approved|rejected|timeout|escalated
  decision         TEXT,
  reason           TEXT,
  requested_at     TIMESTAMPTZ DEFAULT now(),
  decided_at       TIMESTAMPTZ,
  expires_at       TIMESTAMPTZ,
  escalated_to     UUID
);

-- 补偿动作（Saga）
CREATE TABLE saga_compensation (
  id               UUID PRIMARY KEY,
  workflow_run_id  UUID,
  step_run_id      UUID,
  compensate_action JSONB,                          -- 调用什么补偿
  status           TEXT NOT NULL,                   -- pending|done|failed|skipped
  attempt          INT DEFAULT 0,
  created_at       TIMESTAMPTZ DEFAULT now()
);
```

### 8.1 版本化策略（详见 [L23](./23-agent-sdlc.md)）

- **新实例总是用最新激活版本**
- **旧实例必须用启动时的版本跑完**（`workflow_def_id` 锁版本）
- 兼容性变更（加节点、加字段）→ 小版本
- 不兼容变更（删节点、改 schema）→ 大版本，旧实例**不迁移**
- 灰度：按 tenant / 流量比例分流到新版本

---

## 9. MVP 范围（v1）

| 范围 | 内容 |
|---|---|
| ✅ 引擎 | LangGraph 1.0 单一引擎（Temporal v2 接入） |
| ✅ 拓扑 | Supervisor + Pipeline + Critic |
| ✅ HITL | 关键节点 pause/signal，钉钉 + 飞书推送（[L22](./22-hitl-ux.md)） |
| ✅ 持久化 | Postgres（workflow_def / workflow_run / step_run / hitl_request / saga） |
| ✅ API | POST/GET/SSE/cancel/resume/signal |
| ✅ 观测 | OTel trace + 步骤级 span（[L7](./07-observability.md)） |
| ✅ 版本化 | workflow_def 版本号 + 旧实例锁版本 |
| ❌ 不做 | 可视化编辑器 / 自研 BPMN / Network 拓扑 / 跨租户 A2A |

---

## 10. 真实坑总结

| # | 坑 | 缓解 |
|---|---|---|
| 1 | **多 Agent 不是银弹** —— 80% 场景单 Agent 够，硬上多 Agent 调试成本 ×3 | 决策树严格执行（§1.1） |
| 2 | **HITL 卡住** —— 审批人请假、邮件没看、群消息淹没 | 超时升级、多渠道、移动端、批量审批（[L22](./22-hitl-ux.md)） |
| 3 | **长任务必须状态持久化** —— 服务重启不能丢、扩缩容不能丢 | Temporal 强制 durable / LangGraph checkpointer 配 Postgres |
| 4 | **Workflow 修改向后兼容** —— 改了节点，已有 5 万实例怎么办？ | schema 版本化，旧实例不迁移，新实例走新版（§8.1） |
| 5 | **Saga 设计很难** —— 邮件已发、款已转、消息已推都没法收回 | 设计时把不可逆操作放到 HITL 后；准备"道歉补偿"路径 |
| 6 | **多 Agent / 长任务没 trace = 盲跑** —— 出问题完全不知道哪一步、哪个 Agent | 强制 OTel trace，每个 Agent / step 独立 span（[L7](./07-observability.md)） |
| 7 | **可视化编排灵活度永远不如代码** —— 业务方 1 周后就要嵌 Python | 默认 Workflow as Code；可视化只做"查看 / 简单分支" |
| 8 | **Supervisor 上下文爆炸** —— 子 Agent 输出全塞回去 token 5 万 | 子 Agent 强制结构化 + 摘要；Supervisor 用 1M context 模型或分批 |
| 9 | **HITL 审批"假同意"** —— 审批人随手点通过 | 摘要前置 + 风险提示 + 抽样回访 + 审计记录决策时长 |
| 10 | **Workflow 嵌套太深** —— 嵌 5 层完全无法维护 | 限制嵌套 ≤ 2，用 Hierarchical 替代 |

---

## 11. 待决议

- [ ] **LangGraph + Temporal 融合方式**：是 Temporal 整体框 + LangGraph activity 内部跑？还是各跑各？POC 决定
- [ ] **HITL 推送渠道优先级**：钉钉 / 飞书 / 邮件 / 自研 App / 短信兜底；多租户怎么按企业偏好配置
- [ ] **是否做可视化工作流编辑器**：业务方一直要，但维护成本高；先做"只读视图 + 代码 PR"
- [ ] **工作流定义存储格式**：JSON / YAML / Python DSL；倾向 Python DSL（git diff 友好）+ JSON 序列化
- [ ] **Critic Agent 缺省启用**：是否所有 Agent 默认套 Critic？性能 vs 质量
- [ ] **跨 Workflow 信号机制**：Workflow A 完成后通知 Workflow B（先用事件总线，未来看 [L34](./34-a2a.md)）
- [ ] **Workflow 计费**：按 step / 按 wall-clock / 按 token？影响 [L10](./10-pricing.md) / [L17](./17-billing.md)

---

## 附录 A：跨层引用速查

| L6 关心 | 由谁负责 |
|---|---|
| 单 Agent 推理 | [L5](./05-agent-core.md) |
| 引擎选型理由 | [L16](./16-engines.md) |
| HITL 审批 UI / 推送 | [L22](./22-hitl-ux.md) |
| Workflow 版本化 / 灰度 / 回滚 | [L23](./23-agent-sdlc.md) |
| Trace / Replay / 步骤可观测 | [L7](./07-observability.md) |
| 计费粒度 | [L10](./10-pricing.md) / [L17](./17-billing.md) |
| 跨平台 Agent 协作（远期） | [L34](./34-a2a.md) |
| 安全 / 权限 / 审计 | [L12](./12-security.md) / [L18](./18-audit.md) |
| 工具 / MCP 生态 | [L8](./08-tools.md) / [L25](./25-mcp.md) |
| 模型路由 / 成本 | [L11](./11-model-router.md) |
| 多租户 / 配额 | [L19](./19-multi-tenant.md) |
| 数据 / 知识 | [L13](./13-knowledge.md) / [L24](./24-data-lake.md) |
| 评估 / 基准 | [L26](./26-eval.md) / [L36](./36-benchmark.md) |
