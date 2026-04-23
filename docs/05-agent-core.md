# L5 · Agent Core(运行时核心)

> 状态:**讨论中** · 版本 v0.2(重写) · 2026-04-22
> 上游/下游:[L4 Tools & Skills](04-tools-and-skills.md) · [L6 Orchestration](06-orchestration.md) · [L7 Observability & Eval](07-observability-and-eval.md) · [L13 Context Engineering](13-context-engineering.md) · [L16 OSS Stack](16-opensource-stack-decision.md) · [L22 HITL](22-hitl-design.md) · [L23 Agent SDLC](23-agent-sdlc.md) · [L34 A2A](34-a2a-agent-collaboration.md) · [L35 Simulation](35-agent-simulation.md)

---

## 1. 本层职责

L5 是 **单个 Agent 的"运行时核心(Runtime Core)"** —— 一个 Agent 从拿到输入、思考规划、调用工具、观察结果、迭代直到结束(或挂起)整个**推理循环**的引擎。

### 1.1 边界定义(防跨层重叠)

| 层 | 管 | 不管 |
|---|---|---|
| **L5 本层** | Planner / 主循环 / Tool Caller / State / 流式 / 中断 / 失控保护 | Token 怎么压(L13) / 多 Agent 调度(L6) / 框架选型(L16) |
| [L13](13-context-engineering.md) | Token 预算 / Compaction / Memory 内容 / Prompt Cache | 主循环 / Tool 调度 |
| [L16](16-opensource-stack-decision.md) | LangGraph/Temporal/Hatchet 选型 | Planner 内部 |
| [L6](06-orchestration.md) | 多 Agent / DAG / supervisor-worker | 单 Agent 内部 |
| [L4](04-tools-and-skills.md) | 工具注册、描述、MCP | 工具何时/谁调度 |

> 一句话:**L5 决定"一个 Agent 怎么独自跑一个任务"; 内容侧、调度侧、协作侧都在别处。**

### 1.2 商业价值

智能上限(Planner+模型) · 可控性(失控保护,参见 [L10 §10](10-current-problems-and-mitigations.md)) · 单次成本(思考链/并行/ckpt) · 交互体验(流式/中断/续跑/透明度)。

---

## 2. 核心模块图

```
                 ┌──────────────────────────────────────────────────────┐
   user input →  │                  Agent Runtime (L5)                  │
                 │                                                      │
                 │   ┌──────────┐    ┌────────────┐    ┌────────────┐   │
                 │   │ Planner  │──▶│ Tool Caller │──▶│ Observation │──┐
                 │   │ (LLM)    │    │ (执行 + 校验)│    │ (归一化)     │ │
                 │   └────┬─────┘    └─────┬──────┘    └─────┬──────┘ │
                 │        │                │                  │        │
                 │        ▼                ▼                  ▼        │
                 │   ┌────────────────────────────────────────────┐   │
                 │   │   Context Manager  (拼装 prompt / 裁剪)       │◀─┘
                 │   │   ── 详细见 L13 Context Engineering            │
                 │   └────────────┬───────────────────────────────┘   │
                 │                │                                    │
                 │        ┌───────┴────────┐                           │
                 │        ▼                ▼                           │
                 │   ┌──────────┐    ┌──────────────┐                  │
                 │   │ Memory IO│    │ State Store  │                  │
                 │   │ 接口层    │    │ (checkpointer)│─── Postgres     │
                 │   │ ──→ L13  │    └──────────────┘                  │
                 │   └──────────┘                                      │
                 └──────────────────────────────────────────────────────┘
                          │            │           │
                          ▼            ▼           ▼
                       L4 Tools    L7 Trace    L22 HITL
```

| 模块 | 职责 | 本层范围 |
|---|---|---|
| **Planner** | 决策下一步(思考 / 调工具 / 输出) | ✅ 核心 |
| **Tool Caller** | 执行工具调用、校验、并行/重试 | ✅ 核心 |
| **Observation** | 归一化工具结果 → 可消费的字符串 | ✅ 核心 |
| **State Machine** | 主循环 + 状态机定义 | ✅ 核心 |
| **Context Manager** | 拼 prompt(裁剪/压缩在 L13) | ✅ 接口在 L5,策略在 L13 |
| **Memory IO** | 读写 working/episodic/semantic | ✅ 仅接口层,实现在 L13 |
| **State Store** | checkpoint 持久化 | ✅ 落地在 L23 SDLC |

---

## 3. Planner 范式深度对比 2026

### 3.1 五大范式速查表

| 范式 | 核心机制 | 模型门槛 | 单步成本 | 总延迟 | 调试难度 | 推荐占比 |
|---|---|---|---|---|---|---|
| **ReAct** | Thought → Action → Observation 循环 | BFCL ≥ 85 | 1× | 中 | 低 | **80%(默认)** |
| **Plan-and-Execute** | 先全局规划成 DAG → 并行执行 | BFCL ≥ 88 + 长上下文跟随 | 0.5–0.8×(并行省) | 低(并行) | 中 | 10%(复杂多步) |
| **Reflexion / Self-Refine** | 执行后自我评分 → 重写 → 重做 | 自我批判稳定性 | 2–4× | 高 | 中 | 5%(高质量场景) |
| **Tree of Thoughts (ToT)** | 多分支探索 + BFS/DFS 剪枝 | 顶级模型 + 评估器 | 5–20× | 极高 | 高 | <2%(研究/深推理) |
| **CodeAct** | 模型生成代码作为 action(执行在沙箱) | HumanEval ≥ 80 + 代码 tool use | 1.2× | 低(一次代码代多次工具) | 中 | 10–30%(数据/RPA) |

### 3.2 模型能力门槛参考(2026-Q2 公开榜单观察)

| 能力维度 | 参考榜单 | 上 ReAct 阈值 | 上 Plan-Execute 阈值 |
|---|---|---|---|
| Tool Use 准确率 | **BFCL v3** (overall) | ≥ 85 | ≥ 88 |
| 多轮 Tool 跟随 | **τ-bench / NexusRaven** | pass@1 ≥ 70% | ≥ 80% |
| Agent 长任务 | **AgentBench** / **GAIA L2** | ≥ 30% | ≥ 45% |
| 代码生成(CodeAct) | **HumanEval+ / SWE-Bench Verified** | ≥ 80 / ≥ 35% | — |

> **2026 推荐池**:Claude Sonnet 4.7 / Opus 4.7 · GPT-5 family · Qwen3-Max · DeepSeek-V3.2 · Gemini 3 Pro。
> 自部署优选:Qwen3-32B-Instruct / Llama 4 Scout / DeepSeek-V3 蒸馏小模型。
> 模型选型详见 [L11 Model Strategy](11-model-strategy.md)。

### 3.3 决策树:何时选哪种?

```
任务步数 < 5 且 工具 < 10  ──────▶  ReAct
任务步数 ≥ 5 且 步骤间弱依赖   ──▶  Plan-and-Execute(可并行)
质量优先 + 成本可承受       ──────▶  ReAct + Reflexion(只在失败/低分时触发)
任务高度数据驱动 / 可代码化   ──▶  CodeAct(数据分析、RPA、ETL)
研究 / 长 horizon 推理        ──▶  ToT(只在专项,绝不默认)
```

---

## 4. ReAct 主循环代码骨架

```python
# Pseudo Python · 实现基于 LangGraph(见 L16)
@dataclass
class AgentState:
    messages: list
    scratchpad: list = field(default_factory=list)   # thought/action/obs
    step: int = 0
    tokens_used: int = 0
    cost_usd: float = 0.0
    state_hash_history: list = field(default_factory=list)
    consecutive_tool_errors: int = 0
    status: Literal["running","done","halted","awaiting_human"] = "running"

async def react_loop(state, cfg):
    while state.status == "running":
        if guardrails_breached(state, cfg):                # §5 五道闸门
            state.status = "halted"; break

        prompt = context_manager.build(state)              # 拼装策略 → L13
        resp = await llm.complete(
            prompt=prompt,
            tools=tool_registry.list_for(state.tenant),
            stream=True,                                    # 流式 → §8
        )
        state.tokens_used += resp.usage.total; state.cost_usd += resp.cost

        if resp.stop_reason == "end_turn":
            state.messages.append(resp.message); state.status = "done"; break

        if resp.tool_calls:                                 # Tool Caller → §6
            results = await tool_caller.dispatch(
                resp.tool_calls, tenant=state.tenant, user=state.user)
            for r in results:
                state.scratchpad.append({"action": r.call, "observation": r.result})
                state.consecutive_tool_errors = 0 if not r.error else state.consecutive_tool_errors + 1

        state.step += 1
        state.state_hash_history.append(hash_state(state))
        await checkpointer.save(state.thread_id, state)     # 每步 ckpt → §7
    return state
```

**关键设计**:状态全显式可序列化;stop_reason 驱动终止;async 全 IO 并发;每步 checkpoint(不是结尾才存,否则崩溃丢整段)。

---

## 5. 防失控(本层最重要的工程)

> 上游问题清单见 [L10 §10 Agent 失控循环](10-current-problems-and-mitigations.md):**90% Agent 项目 30 天内失败,#1 原因就是成本失控**;典型案例 $0.08 任务飙到 $12(150×)。

### 5.1 五道闸门

| # | 闸门 | 默认值 | 触发后行为 |
|---|---|---|---|
| 1 | **max_steps** | 10–20(简单) / 40(复杂) | 立即 halt → 输出当前最佳 / 求助人工 |
| 2 | **max_tokens(单 run)** | 200K–500K | halt + 报警 |
| 3 | **max_cost_usd(单 run)** | tier 默认 $0.50 / pro $5 / autonomous $20 | halt + 通知 owner |
| 4 | **死循环检测(state hash)** | 同 hash 出现 ≥ 3 次 | halt + 标记需重 prompt |
| 5 | **连续工具失败** | ≥ 3 次同工具 / ≥ 5 次任意工具 | 降级:换工具 / 切人工 / 终止 |

### 5.2 死循环检测实现

```python
def hash_state(s: AgentState) -> str:
    # 取最近一次 thought + action + arg 做 hash
    last = s.scratchpad[-1] if s.scratchpad else {}
    key = json.dumps({"a": last.get("action"), "args": last.get("args")}, sort_keys=True)
    return hashlib.sha1(key.encode()).hexdigest()[:12]

def guardrails_breached(s, cfg):
    if s.step >= cfg.max_steps: return True
    if s.tokens_used >= cfg.max_tokens: return True
    if s.cost_usd >= cfg.max_cost_usd: return True
    if s.consecutive_tool_errors >= cfg.max_consec_tool_errors: return True
    # state hash 重复
    h = s.state_hash_history
    if len(h) >= 3 and h[-1] == h[-2] == h[-3]: return True
    return False
```

### 5.3 异常累计降级策略

```
┌──────────────┐
│ tool error 1 │── retry(指数退避)
└──────┬───────┘
       ▼
┌──────────────┐
│ tool error 2 │── retry,LLM 拿到结构化错误自纠
└──────┬───────┘
       ▼
┌──────────────┐
│ tool error 3 │── 切换:同类备用工具 / 简化路径 / 求助 HITL(L22)
└──────────────┘
```

---

## 6. Tool Caller 实现

### 6.1 完整调用链

```
LLM 输出 tool_calls
   │
   ├── (a) Schema 校验 ──── 不通过 ──▶ 结构化错误返回 LLM 自纠(不计入失败)
   │
   ├── (b) 权限检查 ─────── RBAC/ABAC,详见 L4 §6.1 + L8 安全
   │
   ├── (c) HITL 检查 ────── 风险分级 → 等待审批(详见 L22)
   │
   ├── (d) 调度 ────────── 并行(无依赖) / 串行(显式依赖)
   │
   ├── (e) 执行 ────────── 超时 / 重试 / 沙箱(L4 §7)
   │
   ├── (f) 结果归一化 ──── 长结果裁剪 / 错误结构化
   │
   ├── (g) 审计日志 ────── 写入 tool_call 表 + L7 trace
   │
   └── (h) 注入 context ── 回到 Planner 下一轮
```

### 6.2 并行执行 + 单调用流程

```python
async def dispatch(tool_calls, tenant, user):
    groups = topo_sort(tool_calls)              # 显式依赖按 DAG,否则全并行
    results = []
    for group in groups:
        results += await asyncio.gather(
            *[execute_one(tc, tenant, user) for tc in group])
    return results

async def execute_one(tc, tenant, user):
    if not validate(tc.args, tool_registry.schema(tc.name)):
        return err("E_SCHEMA", "参数不符 schema", suggestion="检查必填", retryable=True)
    if not authz.allow(user, tc.name, tc.args):
        return err("E_PERM", "无权限", retryable=False)
    if hitl.required(tc, tenant):               # 详见 L22
        await hitl.request_approval(tc, user)   # 阻塞或挂起 state(见 §7)
    try:
        with timeout(tool_registry.timeout(tc.name)):
            return normalize(await tool_registry.invoke(tc.name, tc.args, tenant=tenant))
    except ToolTimeout:
        return err("E_TIMEOUT", "工具超时", retryable=True)
    except Exception as e:
        return err("E_RUNTIME", str(e), retryable=False)
```

### 6.3 结果归一化(防 context bloat)

| 结果类型 | 归一化策略 |
|---|---|
| **长 JSON / 表格** | 取关键字段 + 总条数;原文存 blob,留 `result_ref` |
| **二进制 / 文件** | 写入对象存储,context 只放 URL + 元数据 |
| **错误** | 转成 `{code, message, suggestion, retryable, doc_url}`(详见 §9) |
| **空 / null** | 显式 `{result: null, reason: "..."}` 而非空字符串 |

> 详细的"长工具结果如何在多轮中清理"见 [L13 §10 Claude Code 5 层 compaction](13-context-engineering.md#10-多轮-agent-上下文演进) —— Tool-result clearing 是第一档。

---

## 7. State 持久化与断点续跑

> 落地选型:**LangGraph + Postgres checkpointer**(<5min 任务) 或 **Temporal**(>5min / 跨人工审批) —— 详见 [L16 §6 Workflow](16-opensource-stack-decision.md#6-workflow--长任务) 与 [L23 Agent SDLC](23-agent-sdlc.md)。

### 7.1 为什么必须持久化

| 场景 | 持久化作用 |
|---|---|
| 服务重启 / 部署滚动 | 不丢任务 |
| HITL 审批等几小时/几天(L22) | Agent 挂起,审批回来续跑 |
| 长任务跨多 worker | 状态可被任何 worker 接管 |
| 审计 / 重放 / Eval | trajectory diffing(L7) |
| 用户中途打断 | 重连后续接 |

### 7.2 Checkpoint 数据模型

```python
class Checkpoint(TypedDict):
    thread_id: str               # 一个 run 的标识
    step: int                    # 第几步
    state: AgentState            # 完整状态快照(JSON)
    parent_checkpoint_id: str    # 链式追溯
    created_at: datetime
    metadata: dict               # tenant / user / agent_version / model
```

存储:Postgres `JSONB` 列 + `(thread_id, step)` 唯一索引。每步写一次 → 任意 step 可续跑或回放。

### 7.3 断点续跑

```python
async def resume(thread_id: str, from_step: int = -1):
    cp = await checkpointer.load(thread_id, step=from_step)  # -1 = latest
    state = AgentState(**cp.state)
    return await react_loop(state, cfg)                      # 主循环幂等续跑
```

### 7.4 awaiting_human 状态

```
running ──HITL 触发──▶ awaiting_human ─审批通过─▶ running
                              │
                              └──超时 / 拒绝──▶ halted / cancelled
```
HITL 设计、超时策略、审批 UX 见 [L22 §3-5](22-hitl-design.md)。

---

## 8. 流式 + 中断

### 8.1 流式输出三档

| 流式层级 | 实现 | 用户感知 |
|---|---|---|
| **L1 思考过程** | LLM token-by-token SSE | "正在分析你的问题..." |
| **L2 工具进度** | tool_call 事件 + 工具内 progress 回调 | "正在查询订单 12345..." |
| **L3 最终答案** | LLM 边生成边推送 | 类 ChatGPT 打字效果 |

### 8.2 中断协议

```python
async def react_loop_with_interrupt(state, cfg, cancel_token):
    while state.status == "running":
        if cancel_token.cancelled:
            state.status = "interrupted"
            await checkpointer.save(state.thread_id, state)   # 保存当前进度
            return state
        # ... 主循环
```

- **客户端中断**:SSE 双向,客户端发 `cancel` 事件 → 当前 LLM 调用 abort + 保存 state
- **正在执行的工具**:超时机制兜底,长工具应支持 cancel 接口
- **续接**:用户回来 `resume(thread_id)` 即可

### 8.3 思考过程透明度开关

| 模式 | 适用 | 风险 |
|---|---|---|
| **完全透明**(thought/action/obs 都流给用户) | 开发 / 高级用户 / Code Agent | 暴露 prompt、易被 prompt-extraction |
| **摘要可见**("正在查物流...") | 客服 / 大众 C 端 | 低 |
| **完全黑盒**(只显示最终答案) | 内嵌系统 / 高隐私 | 出错难调,需 L7 trace |

> 推荐生产:摘要可见 + 后台保留完整 trace(L7)。

---

## 9. 错误反馈链路(LLM 自纠的关键)

### 9.1 结构化错误格式

```json
{
  "error": {
    "code": "E_ORDER_NOT_FOUND",
    "message": "订单 12345 不存在",
    "suggestion": "确认订单号格式;或使用 search_order_by_phone 工具",
    "retryable": false,
    "doc_url": "https://docs.../tools/query_order#errors",
    "context": { "tried_with": {"order_id": "12345"} }
  }
}
```

### 9.2 错误码分类

| Code 前缀 | 含义 | LLM 应该 |
|---|---|---|
| `E_SCHEMA_*` | 参数错 | 立即按 suggestion 修参数重试 |
| `E_PERM_*` | 无权限 | 不要重试,告知用户 / 走 HITL |
| `E_NOT_FOUND_*` | 资源不存在 | 改用查询/搜索类工具 |
| `E_TIMEOUT` / `E_NETWORK` | 临时 | 自动重试(指数退避,重试上限在 caller) |
| `E_RATE_LIMIT` | 限流 | 退避 + 切换 provider/key |
| `E_TOOL_INTERNAL` | 工具内部错 | 至多重试 1 次,然后求助 |

### 9.3 防"工具失败死磕"

> [L10 §6 多步任务级联失败](10-current-problems-and-mitigations.md) 的典型反模式 ——LLM 看到错误反复用同一个工具试 10 次。

```python
# 在 caller 层硬阻止
if same_tool_call_in_last_n(state, tc, n=3):
    return ToolResult(error=structured_err(
        "E_REPEATED_FAIL",
        "同一调用 3 次失败,放弃",
        suggestion="尝试其他工具或回答用户当前已知信息",
        retryable=False,
    ))
```

---

## 10. 真实场景流程示例

### 10.1 客服(ReAct,3 步)

```
用户:"上周买的耳机还没到,订单号 12345"
[1] Memory IO → 用户档案 + 7 天会话摘要(L13)
[2] Plan: query_order(12345) → {status:shipping, tracking:SF888}     · ckpt #1
[3] Plan: query_logistics(SF888) → {current:杭州, expected:明天}      · ckpt #2
[4] Plan: end_turn → 流式回复 "您的订单已发出..."
[5] Memory 写入(L13):本次咨询事件、用户情绪平和
总:3 step / ~6K tok / $0.012 / 4.2s
```

### 10.2 编程(CodeAct + HITL)

```
用户:"prod 报错日志最近 1h 飙升,看下"
[1] CodeAct:gen 代码 = 查 ELK 1h ERROR 聚合 → 沙箱执行(L4 §7)
[2] 结果:NPE 占 80% → gen 代码 = git blame 该行
[3] 结果:commit abc123 / 2h 前 → draft PR fix
[4] HITL 阻断(L22 高风险)→ awaiting_human(state 持久化)
[5] 审批通过 30min 后 resume → create_pr → 返回 PR 链接
```

### 10.3 财务对账(Plan-and-Execute + HITL)

```
用户:"对一下 3 月银行流水和 ERP"
Plan 阶段输出 DAG:
  P1=fetch_bank(3m)  P2=fetch_erp(3m)         # 并行
  P3=match(P1,P2)                              # 依赖 P1,P2
  P4=draft_adjustments(P3.unmatched)
  P5=[HITL] confirm(P4)                        # 阻断
  P6=post_to_erp(P5.approved)                  # 仅写已批准

Executor:P1||P2 → P3 → P4 → 挂起等审批 → P6
审批批 12 / 驳 3 → resume → 完整 audit trail(L22 §8 / L23 §13)
总:6 步,墙钟 8 min(等审批 5 min)
```

---

## 11. 多 Agent 协作(指针)

本层只负责**单 Agent 内部**;多 Agent 编排(supervisor-worker / hierarchical / debate / market)在:

- [L6 Orchestration](06-orchestration.md) —— 内部多 Agent 工作流
- [L34 A2A](34-a2a-agent-collaboration.md) —— 跨组织/跨厂商 Agent 协议(Google A2A 0.3 / 2026-Q2)
- [L35 Agent Simulation](35-agent-simulation.md) —— 多 Agent 模拟评测

---

## 12. 数据模型

### 12.1 SQL Schema(Postgres,核心三表)

```sql
CREATE TABLE agent_run (
  id              UUID PRIMARY KEY,
  thread_id       UUID NOT NULL,                -- LangGraph thread
  tenant_id       UUID NOT NULL,
  user_id         UUID,
  agent_id        TEXT NOT NULL,
  agent_version   TEXT NOT NULL,                -- 版本(L23)
  model           TEXT NOT NULL,
  status          TEXT NOT NULL,                -- running/done/halted/awaiting_human/cancelled
  started_at      TIMESTAMPTZ NOT NULL,
  ended_at        TIMESTAMPTZ,
  total_steps     INT DEFAULT 0,
  total_tokens    INT DEFAULT 0,
  total_cost_usd  NUMERIC(10,4) DEFAULT 0,
  halted_reason   TEXT,                         -- max_steps / loop / cost / tool_fail
  trace_id        TEXT,                         -- L7 OTel
  metadata        JSONB
);
CREATE INDEX ON agent_run(tenant_id, started_at DESC);

CREATE TABLE agent_step (
  id            UUID PRIMARY KEY,
  run_id        UUID REFERENCES agent_run(id),
  step_no       INT NOT NULL,
  type          TEXT NOT NULL,                  -- plan / tool / observe / answer
  thought       TEXT,
  state_hash    TEXT,
  tokens_in     INT, tokens_out INT, latency_ms INT,
  created_at    TIMESTAMPTZ NOT NULL,
  UNIQUE (run_id, step_no)
);

CREATE TABLE tool_call (
  id            UUID PRIMARY KEY,
  step_id       UUID REFERENCES agent_step(id),
  run_id        UUID,
  tool_name     TEXT NOT NULL,
  args          JSONB,
  result        JSONB,                          -- 长内容仅 ref
  result_ref    TEXT,                           -- 对象存储 URL
  error_code    TEXT,
  duration_ms   INT, retry_count INT DEFAULT 0,
  hitl_id       UUID,                           -- 关联 L22
  started_at    TIMESTAMPTZ, ended_at TIMESTAMPTZ
);
CREATE INDEX ON tool_call(run_id);

-- Checkpoint(LangGraph 兼容)
CREATE TABLE agent_checkpoint (
  thread_id UUID, step INT, state JSONB NOT NULL, parent_step INT,
  created_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (thread_id, step)
);
```

### 12.2 常用诊断查询

```sql
-- Top 5 最耗钱的 run(24h)
SELECT id, total_cost_usd, halted_reason FROM agent_run
WHERE started_at > now()-interval '24h' ORDER BY total_cost_usd DESC LIMIT 5;

-- 死循环 / halted 趋势
SELECT date_trunc('hour', started_at), halted_reason, count(*) FROM agent_run
WHERE status='halted' GROUP BY 1,2 ORDER BY 1 DESC;
```

---

## 13. Observability Hook(链入 L7)

> 完整规范见 [L7 Observability & Eval](07-observability-and-eval.md)。L5 必须暴露:

| Hook 点 | OTel 事件 / Span |
|---|---|
| run 开始 / 结束 | span `agent.run` (含 model, tenant, total_cost) |
| 每个 Planner 调用 | span `agent.plan`(含 tokens_in/out, model_latency) |
| 每个 Tool 调用 | span `agent.tool_call`(含 tool_name, error_code) |
| Checkpoint | event `agent.checkpoint`(thread_id, step) |
| Guardrail 触发 | event `agent.guardrail` (reason, severity) |
| HITL 阻断 | event `agent.hitl_pending`(approval_id) |

遵循 **OpenTelemetry GenAI semantic conventions**(2025 已稳定,详见 [L10 §11](10-current-problems-and-mitigations.md))—— 必须**完整捕获 prompt + 工具结果**,不可采样,否则根因分析失效。

---

## 14. MVP 范围

> 4–6 周交付企业可用 Agent Runtime。

**必需**:ReAct 主循环(LangGraph) · Tool Caller(schema/权限/并行/重试) · 五道失控闸门(steps/tokens/cost/state-hash/工具失败) · State checkpoint(Postgres 每步) · 流式 SSE(L1+L3 两档) · 结构化错误(§9) · 短期 memory 接口(实现走 L13) · OTel(§13 Hook 全打) · audit log 三表。

**v1 后续**:Plan-and-Execute · CodeAct · 中断+续接 · Reflexion · Sub-agent spawn(L13 §10)。

---

## 15. 真实坑(本层)

> 本节聚焦**主循环和 Tool Caller 层**的坑;Context bloat / Memory 写入污染 等"内容侧"详细分析见 [L13](13-context-engineering.md) 与 [L10 §9 记忆污染](10-current-problems-and-mitigations.md)。

| # | 坑 | 表现 | 缓解 | 详见 |
|---|---|---|---|---|
| 1 | **死循环是第一杀手** | 同一 action 反复执行,token 飞 | state hash + 强 max_steps | L10 §10 |
| 2 | **Context bloat** | 多轮后 prompt 50K+,质量断崖 | 长结果 ref 化 + L13 五层 compaction | L13 §10 |
| 3 | **工具失败死磕** | LLM 不会"放弃" | caller 强制阻断 + 错误码 retryable | §9.3 |
| 4 | **思考过程透明 vs 暴露** | 暴露后被 prompt-extract / 仿冒 | 摘要可见 + 后台 trace | §8.3 |
| 5 | **Memory 写入需审** | 注入 / 脏数据自我强化 | 写入审核 + LLM-as-judge | L10 §9 |
| 6 | **状态持久化常被忽略** | 服务重启丢任务,P0 事故 | 每步 checkpoint;不只是"结尾存" | §7 |
| 7 | **不同模型 ReAct 表现差异巨大** | 换模型整套 prompt 失灵 | model-pinning + 切换走 canary(L23 §6) | L11 / L23 |
| 8 | **HITL 挂起忘了清理** | awaiting_human 永久占内存 / 队列堆积 | 超时回收 + L22 §5 策略 | L22 §5 |
| 9 | **并行工具调用未做幂等** | 重试触发副作用(双发邮件) | 工具 idempotency_key 必填(L4 §6) | L4 §6 |
| 10 | **Token 计算不准** | 真实成本 > 预估 30%+ | 实时累计 usage,不依赖 tiktoken 估算 | L13 §11 |

---

## 16. 待决议

- [ ] 主框架:LangGraph(单节点) vs LangGraph + Temporal(durability) —— 倾向后者(参考 [L16 §6](16-opensource-stack-decision.md#6-workflow--长任务) 的 Grid Dynamics 模式)
- [ ] 默认 Planner:ReAct(80% 场景),CodeAct 是否在数据/RPA 场景设为默认?
- [ ] Reflexion 引入策略:全局开关 vs 仅 eval 失败时触发
- [ ] 思考过程默认透明度:摘要可见 / 完全黑盒
- [ ] state_hash 算法:是否包含 thought 文本(包含会过敏感)
- [ ] Tool Caller 是否独立成微服务 vs 进程内调用 —— 大并发场景需独立
- [ ] CodeAct 沙箱:E2B / Daytona / 自建 firecracker(详见 [L4 §7](04-tools-and-skills.md))
- [ ] 多模型 ReAct prompt 兼容层:统一中间表示 vs 每模型一套 prompt 模板

---

## 附录 · 关联章节速查

[L4](04-tools-and-skills.md) MCP/工具描述 · [L6](06-orchestration.md) 多 Agent · [L7](07-observability-and-eval.md) trace/eval · [L10](10-current-problems-and-mitigations.md) 失控事故 · [L13](13-context-engineering.md) Memory/Compaction · [L16](16-opensource-stack-decision.md) 框架选型 · [L22](22-hitl-design.md) HITL · [L23](23-agent-sdlc.md) SDLC · [L33](33-continuous-finetuning-loop.md) trajectory 微调 · [L34](34-a2a-agent-collaboration.md) 跨组织 A2A · [L35](35-agent-simulation.md) Simulation
