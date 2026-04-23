---
title: L2 · 模型网关（LLM Gateway）— 工程实现层
version: v0.2 重写版
status: 讨论中
last_updated: 2026-04-22
owner: Platform / Gateway Team
audience: 网关研发、平台架构、SRE
---

# L2 · 模型网关（LLM Gateway）— 工程实现层

> 本次重写：从"模型选型 + 商业卖点"剥离，专注**网关本体的工程实现**。
> 选型 / 协议 / 成本 / 战略已分别下沉到 L11 / L12 / L16 / L21，本文不再重复。

---

## 1. 本层职责定位

L2 是平台**唯一的 LLM 出口**。它不决定"用哪个模型最好"（那是 L11），也不决定"怎么省钱"（那是 L21），它负责：**把上层 Agent / RAG / Skill 的调用，工程化地、稳定地、可观测地翻译成下游 LLM Provider 的请求**。

| 维度 | 谁负责 | 本文 (L2) 角色 |
|---|---|---|
| 模型清单、价格、能力矩阵、定级 | [L11 模型策略](./11-model-strategy.md) | **消费方**：把 L11 的策略表加载为路由配置 |
| OpenAI / Anthropic / Gemini 协议字段、流式格式、Tool schema | [L12 LLM API 协议](./12-llm-api-protocols.md) | **执行方**：实现协议适配器，对外暴露统一外观 |
| LiteLLM / NewAPI / Portkey / 自研 选型 | [L16 OSS 栈选型](./16-opensource-stack-decision.md) | **落地方**：按 L16 决策做 wrapper 或自研填空 |
| Token 单价、配额、客户级 showback、预算告警 | [L21 FinOps](./21-finops-cost-management.md) | **生产方**：吐出原始 usage 事件，L21 做账单聚合 |
| 跨区域容灾、Provider 黑名单、DR 切换 | [L26 DR/BCM](./26-disaster-recovery-bcm.md) | **执行方**：实现 Failover 状态机 |
| 多租户隔离、数据出境拦截 | [L24 多租户](./24-multi-tenant-isolation.md) / [L25 合规](./25-data-compliance-and-residency.md) | **拦截层**：在网关入口做策略检查 |

**一句话**：L2 = **路由 + 缓存 + 限流 + Failover + 流式代理 + 计费埋点** 六大工程模块的实现文档。

---

## 2. Gateway 架构总览

```
                         ┌──────────────────────────────────────────┐
                         │         L9 接入层 / L5 Agent Core         │
                         └─────────────────────┬────────────────────┘
                                               │ (OpenAI / Anthropic 兼容)
                                               ▼
   ┌──────────────────────────────────────────────────────────────────────────┐
   │                       L2 Gateway (Go / Rust 进程)                        │
   │                                                                          │
   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
   │  │ Ingress  │→ │ AuthN/Z  │→ │ Policy   │→ │ Router   │→ │ Adapter  │  │
   │  │ (HTTP/   │  │ (API Key │  │ (合规/   │  │ (Rule +  │  │ (OAI/    │  │
   │  │  gRPC)   │  │  /JWT)   │  │  PII)    │  │  Embed + │  │  Anth/   │  │
   │  │          │  │          │  │          │  │  Learned)│  │  Qwen…)  │  │
   │  └──────────┘  └──────────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
   │                                   │             │             │         │
   │                ┌──────────────────┴─┐  ┌────────┴───────┐    │         │
   │                │ Cache (Exact /     │  │ Rate Limiter / │    │         │
   │                │ PromptCache /      │  │ Quota Engine   │    │         │
   │                │ Semantic)          │  │ (TB+SW)        │    │         │
   │                └────────────────────┘  └────────────────┘    │         │
   │                                                              │         │
   │                ┌────────────────────────┐  ┌─────────────────┴──────┐  │
   │                │ Failover State Machine │  │ Streaming Proxy (SSE)   │  │
   │                │ (Health / Circuit)     │  │ + Token Counter (live)  │  │
   │                └────────────────────────┘  └─────────────────────────┘  │
   │                                                              │         │
   │                ┌────────────────────────────────────────────┴──────┐   │
   │                │  Metering Sink → Kafka → ClickHouse / Postgres    │   │
   │                └───────────────────────────────────────────────────┘   │
   └──────────────────────────────────────────────────────────────────────────┘
                                               │
                                               ▼
                         ┌──────────────────────────────────────────┐
                         │  Providers (Claude / OpenAI / Qwen /     │
                         │  DeepSeek / vLLM 私有化 / …)             │
                         └──────────────────────────────────────────┘
```

**进程形态**：单进程多模块（不是微服务）。Router/Cache/Limiter 都是同进程的 in-memory + Redis；只有 Metering 是异步出 Kafka。

**为什么不拆服务**：每个 LLM 调用上路径多 1ms 都心疼，服务间 RPC 不可接受。

---

## 3. 请求生命周期

```
┌──────────────────────────────────────────────────────────────────────┐
│ 1. Ingress  收到 POST /v1/chat/completions                           │
│ 2. AuthN    校验 API Key → 解出 tenant_id / user_id / scopes         │
│ 3. Policy   PII 扫描、出境检查、内容审核预过滤                        │
│ 4. Quota    预扣 estimated_tokens → 拒/排队/放行                     │
│ 5. Cache    Exact Hash → Semantic Embed → 命中则直接返回 (含 X-Cache)│
│ 6. Route    选 model + provider + endpoint (主+备列表)               │
│ 7. Adapter  把统一请求翻译成 provider 原生 schema                    │
│ 8. Call     发 HTTP / WS；流式则建立 SSE 上行 + 下行通道              │
│ 9. Stream   边收 chunk 边 (a) 转发上层 (b) 累计 token (c) 写 trace   │
│ 10. Failover 收到 5xx / 超时 → 切备 endpoint → 重放未完成 stream     │
│ 11. Settle  实际 usage → 校正预扣 → 计费事件入 Kafka                 │
│ 12. Cache-Write 异步把 (req_hash, response) 写回缓存 (含 TTL 策略)   │
│ 13. Audit   脱敏后 prompt + response 入冷存储 (合规 6/12 月)         │
└──────────────────────────────────────────────────────────────────────┘

延迟预算 (P50):
  Step 1-7 (路由前置)      ≤ 8ms
  Step 8 网络握手          50–200ms (海外 endpoint 主要损耗)
  Step 9 首 token (TTFT)   200–1500ms (取决于模型)
  Step 11-13 异步           不阻塞响应
```

---

## 4. 路由模块设计

L2 不重新发明"该用哪个模型"，那张策略表来自 [L11](./11-model-strategy.md)。L2 实现的是**把策略表跑起来的引擎**。

### 4.1 三层路由器（按代价由低到高串联）

| 层 | 触发条件 | 实现 | 决策延迟 |
|---|---|---|---|
| **Rule Router** | 显式 model="..." 或租户硬约束 | YAML / DSL 加载到内存树 | < 0.1ms |
| **Embedding Router** | model="auto" + 业务标签 | 预训 32d 分类向量 + cosine 比对 | 1–3ms |
| **Learned Router** | 高价值流量、A/B 实验 | 在线 bandit (Thompson Sampling) | 2–5ms |

代码组织：

```
gateway/
  router/
    engine.go            // Pipeline: Rule → Embedding → Learned → Default
    rule/
      dsl.go             // 解析 L11 输出的 strategy.yaml
      compiler.go        // 编译成决策树（避免每请求遍历）
    embedding/
      classifier.go      // 加载 ONNX 模型，给 prompt 打类目标签
      labels.go          // 类目→候选模型池的映射
    learned/
      bandit.go          // 多臂 bandit；reward = (quality_score - cost_norm)
      reward_collector.go // 从 L7 eval 拿 quality 分数回灌
    fallback.go          // 主备列表生成器
```

**关键设计**：路由器**只输出候选列表**（`[primary, backup1, backup2]`），不直接调用。真正发请求由 Failover 状态机决定从哪个开始打。

### 4.2 路由配置热更新

策略 YAML 通过 etcd watch / Nacos 推送；变更后 30s 内全网生效。**严禁重启网关换路由**。

---

## 5. 缓存模块

三级缓存，命中代价依次升高，但**回报也依次升高**。

| 类型 | 命中条件 | 存储 | 实测命中率 (客服场景) | 节省成本 |
|---|---|---|---|---|
| **Exact Cache** | prompt + 全部参数 SHA256 完全相等 | Redis String, TTL 1h | 8–12% | 100% |
| **Prompt Cache (透传)** | 复用 LLM Provider 自己的 prompt cache | 不存，传 `cache_control` 标记给 Provider | 取决于 system prompt 占比 | 输入 50–90% |
| **Semantic Cache** | embedding cosine ≥ 0.93 + 业务标签匹配 | Qdrant / Milvus + Redis 元数据 | 25–40% | 100% (但有质量损失风险) |

### 5.1 Redis 数据结构

```
# Exact Cache
KEY:   gw:cache:exact:{model}:{sha256(canonical_request)}
VALUE: msgpack { response, usage, created_at }
TTL:   3600s (可按 model 配)

# Semantic Cache 元数据
KEY:   gw:cache:sem:meta:{vector_id}
VALUE: hash { tenant, biz_tag, prompt_preview, response_ref, hit_count }

# 命中计数（用于淘汰）
ZSET:  gw:cache:hot
        member = vector_id, score = hit_count_decay
```

### 5.2 Prompt Cache 透传

[L12](./12-llm-api-protocols.md) 已写清 Anthropic / OpenAI / Gemini 各自的 cache 字段。L2 在 Adapter 层负责**自动加 `cache_control` 标记**：识别 system prompt > 1024 token 即标记，无需上层关心。

### 5.3 语义缓存的"防误命中"

- **每租户独立向量空间**（避免 A 公司的回答给 B 公司）
- 命中后**抽样 5%** 走真实模型 + 比对，质量分 < 阈值则降权该向量
- 工具调用、含变量插值的 prompt **永不进语义缓存**

详细评估方法见 [L7 可观测与评估](./07-observability-and-eval.md)。

---

## 6. 限流 + 配额引擎

### 6.1 算法组合

```
请求进入 → ┌─ 令牌桶 (Token Bucket)：吸收突发，桶容量 = 2× rate
          │
          └─ 滑动窗口 (Sliding Window Log)：精确按 1min/1h/1d 累计
                ↓
            两者都通过 → 放行；任一拒绝 → 429 + Retry-After
```

为什么两个都要：令牌桶处理短突发友好但长期不准；滑动窗口精确但对突发不友好。组合后两全。

### 6.2 维度 × 单位矩阵

| 维度 | QPS | RPM | TPM (input) | TPM (output) | 日 ¥ |
|---|---|---|---|---|---|
| API Key | ✓ | ✓ | ✓ | ✓ | ✓ |
| User | – | ✓ | ✓ | ✓ | ✓ |
| Tenant | ✓ | ✓ | ✓ | ✓ | ✓ |
| Tenant × Model | ✓ | ✓ | ✓ | ✓ | ✓ |
| 全局 Provider | ✓ | – | ✓ | – | – |

每个组合一份限流配置。读取走 Redis Cluster；写入用 Redis 原子脚本（Lua）保证一致。

### 6.3 ClickHouse 实时聚合（用于配额账户）

预扣 + 实算的差异需要回写校正。直接 Postgres 单库扛不住高频写入：

```
Gateway → Kafka (topic: llm.usage.events)
             ↓
     ┌───────┴────────┐
     ▼                ▼
  ClickHouse     Postgres
  (1s 窗口聚合)   (落地账单 + 配额状态)
     │
     ▼
  Quota Cache (Redis) ← 每 5s 从 CH 拉最新累计值刷新
```

[L21](./21-finops-cost-management.md) 详述账单 / showback；这里只关心**实时配额扣减**。

---

## 7. Failover 状态机

每个 (provider, endpoint) 是状态机的一个节点：

```
            ┌──────────┐  连续 N 次成功    ┌────────────┐
            │  CLOSED  │ ◄─────────────── │ HALF_OPEN  │
            │ (健康)   │                   │ (探测中)   │
            └────┬─────┘                   └─────┬──────┘
                 │ 错误率 > 阈值 / P99 > 阈值        ▲
                 ▼                                │ cooldown 30s 后探一次
            ┌──────────┐                         │
            │   OPEN   │ ────────────────────────┘
            │ (熔断)   │   30s
            └──────────┘
```

### 7.1 健康探测

- **被动**：基于真实流量统计 (滑动 10s 窗口；errror_rate > 5% 或 P99 > 配置值)
- **主动**：每 15s 一次 `/health` 或最廉价 endpoint 调用（OpenAI 没有 health → 用 1-token completion）

### 7.2 降级矩阵

| 主模型故障 | 1 级备 | 2 级备 | 兜底 |
|---|---|---|---|
| Claude Opus 4.7 | Claude Sonnet 4.6 | GPT-5 | Qwen3-235B (本地) |
| GPT-5 | GPT-4o | Claude Sonnet | Qwen3-235B |
| 通义 Max | Qwen3-32B (本地) | DeepSeek-V3 | 拒绝服务 + 报警 |

降级矩阵从 [L11](./11-model-strategy.md) 加载；DR 跨区切换流程详见 [L26](./26-disaster-recovery-bcm.md)。

### 7.3 流式中断的特殊处理

流式请求被 Failover 切换时，**已发出的 token 不能再发**。两种策略：

1. **断点续接**：把已生成内容塞进新请求的 messages，让备模型续写（适合 Claude/GPT 互切）
2. **吞掉重来**：返回 SSE 错误事件 `[ERROR_RECOVERABLE]`，由上层 Agent SDK 自动重试（推荐，简单）

---

## 8. 流式代理

### 8.1 统一外观

对外只暴露**一种 SSE 格式**，下游各 Provider 的差异由 Adapter 抹平。详细字段映射见 [L12 §3](./12-llm-api-protocols.md)。

```
event: message_start          # 第一个事件
data: {"id":"...","model":"...","role":"assistant"}

event: content_delta          # 增量内容
data: {"delta":{"text":"..."},"index":0}

event: tool_use_delta         # 工具调用片段
data: {"delta":{"name":"...","input_json":"..."}}

event: usage_update           # 阶段性 token 计数（每 N chunk 推一次）
data: {"input_tokens":1024,"output_tokens":256,"cache_read":512}

event: message_stop           # 结束
data: {"stop_reason":"end_turn","final_usage":{...}}

event: error                  # 错误，含可恢复标记
data: {"code":"...","recoverable":true}
```

### 8.2 实现要点

- **零拷贝转发**：Adapter 解析 → 重新序列化的成本不可忽视；用流式 JSON parser（如 Go 的 `json-iterator`），逐字段映射不重建大对象
- **背压**：上游断开时及时 cancel 下游 HTTP，避免 Provider 继续算而我们继续付钱
- **首 token 监控**：TTFT 是最重要的用户感知指标，按 model 单独埋点

---

## 9. 计费引擎

### 9.1 Token 计算

```
       ┌──────────────────────────────────────────────────┐
       │ 每个 model 注册一个 Tokenizer 适配               │
       │   Claude:  anthropic-tokenizer (HTTP API/本地)   │
       │   OpenAI:  tiktoken (cl100k/o200k)               │
       │   Qwen:    qwen-tokenizer (HuggingFace tokenizer)│
       │   DeepSeek: deepseek-tokenizer                   │
       └──────────────────────────────────────────────────┘
                         ↓
       入口预估 (粗) → 实际 usage (准, 来自 Provider 响应)
                         ↓
                 差值校正 → 计费事件
```

**严禁用一个 tokenizer 估所有模型**。Claude 与 GPT 在中文上能差 30%+。

### 9.2 价格表热更新

- 价格存 Postgres + Redis 双写；Redis 为读热路径
- 字段：`(model, region, input_unit_price, output_unit_price, cache_read_price, cache_write_price, currency, effective_from, effective_to)`
- Provider 调价 → 运营在管理台改 → 走审批 → 推送 → 网关 5s 内生效
- **历史账单按 effective 时间点的价格回放**，不能用当前价

### 9.3 客户级 showback

L2 只负责**产事件**：

```json
{
  "event_id": "uuid",
  "ts": 1745366400000,
  "tenant_id": "...", "user_id": "...", "api_key_id": "...",
  "biz_tag": "customer_service", "session_id": "...",
  "model": "claude-sonnet-4-6", "provider": "anthropic", "region": "us-east",
  "input_tokens": 1024, "output_tokens": 256,
  "cache_read_tokens": 512, "cache_write_tokens": 0,
  "cost_cny": 0.0312, "cost_usd": 0.0044,
  "latency_ms": 1832, "ttft_ms": 412,
  "cache_layer": "semantic", "route_reason": "rule:vip_premium",
  "fallback_chain": ["claude-opus-4-7"], "final_attempt": 2
}
```

聚合、对账、出账单、定价模型在 [L21 FinOps](./21-finops-cost-management.md)。

---

## 10. 统一 API 设计（双外观）

历史包袱：上层代码已经分两派——**Anthropic SDK 派**（Agent / Skill）和 **OpenAI SDK 派**（RAG / 旧业务）。强制统一会撕裂团队。

**方案**：暴露**两套 endpoint**，内部走同一套核心。

| Endpoint | 兼容协议 | 主要消费者 |
|---|---|---|
| `POST /v1/chat/completions` | OpenAI Chat Completions | RAG、传统业务、第三方 |
| `POST /v1/messages` | Anthropic Messages | Agent Core (L5)、Skill (L4) |
| `POST /v1/embeddings` | OpenAI Embeddings | RAG、Semantic Cache |
| `POST /v1/responses` | OpenAI Responses (新) | 长任务、批处理 |

字段差异、tool schema 转换、stream 事件映射全部在 Adapter 层。详见 [L12 §2-§5](./12-llm-api-protocols.md)。

**自有扩展头**（两套外观共用）：

```
请求头:
  X-Tenant-Id, X-User-Id, X-Biz-Tag, X-Session-Id
  X-Routing-Hint: "auto|cheap|quality|local-only"
  X-Max-Cost-CNY: 0.5
  X-Allow-Overseas: true|false

响应头:
  X-Model-Used, X-Provider-Used, X-Region-Used
  X-Cost-CNY, X-Input-Tokens, X-Output-Tokens, X-Cache-Read-Tokens
  X-Cache: HIT-exact | HIT-semantic | MISS
  X-Trace-Id, X-Route-Reason, X-Fallback-Used
```

---

## 11. NewAPI / LiteLLM 包装策略

[L16](./16-opensource-stack-decision.md) 已经做完选型决策：**MVP 期 LiteLLM Python proxy + 自研治理层**，6 个月后核心模块自研。本节回答工程层"具体怎么夹层"。

| 组件 | MVP (V1, 4-6w) | 中期 (V2, +3m) | 长期 (V3, +6m) |
|---|---|---|---|
| Provider Adapter | LiteLLM | LiteLLM | 自研 (Go) |
| Router | 自研 (Rule only) | + Embedding | + Learned |
| Cache | 自研 (Exact + Semantic) | + Prompt Cache 透传 | 同 |
| Rate Limit / Quota | 自研 | 同 | 同 |
| Failover | 自研 | 同 | 同 |
| Streaming Proxy | LiteLLM 转发 | 半自研 (背压控制) | 全自研 |
| Metering / Audit | 自研 | 同 | 同 |
| 管理台 (NewAPI) | NewAPI 二开 | 自研接入 | 自研 |

**夹层方式**：

```
Client → 自研 Gateway (Go) → LiteLLM Proxy (Python) → Provider
              │
              └─ 治理 / 路由 / 缓存 / 计费 / 限流 全部在 Go 这一层
```

LiteLLM 只当"Provider SDK 联邦"用，**不让它管路由、不让它管缓存、不让它管计费**——这些社区版做得不行，企业版又贵。

---

## 12. 数据模型

### 12.1 `gateway_request` (Postgres, 主键档案)

```sql
CREATE TABLE gateway_request (
  request_id        UUID PRIMARY KEY,
  trace_id          VARCHAR(64),
  tenant_id         VARCHAR(64) NOT NULL,
  user_id           VARCHAR(64),
  api_key_id        VARCHAR(64),
  biz_tag           VARCHAR(64),
  session_id        VARCHAR(64),

  external_endpoint VARCHAR(32),       -- /v1/chat | /v1/messages
  requested_model   VARCHAR(64),       -- 'auto' or specific
  routed_model      VARCHAR(64),
  provider          VARCHAR(32),
  region            VARCHAR(32),

  status            VARCHAR(16),       -- success | failed | partial
  http_status       INT,
  error_code        VARCHAR(64),

  cache_layer       VARCHAR(16),       -- exact | semantic | prompt | miss
  route_reason      VARCHAR(128),
  fallback_chain    JSONB,
  final_attempt     SMALLINT,

  created_at        TIMESTAMPTZ DEFAULT now(),
  ttft_ms           INT,
  total_latency_ms  INT
);
CREATE INDEX ON gateway_request (tenant_id, created_at DESC);
CREATE INDEX ON gateway_request (trace_id);
```

### 12.2 `gateway_usage` (ClickHouse, 高频写)

```sql
CREATE TABLE gateway_usage (
  ts                DateTime64(3),
  request_id        UUID,
  tenant_id         LowCardinality(String),
  model             LowCardinality(String),
  provider          LowCardinality(String),
  biz_tag           LowCardinality(String),
  input_tokens      UInt32,
  output_tokens     UInt32,
  cache_read_tokens UInt32,
  cache_write_tokens UInt32,
  cost_cny          Decimal(18,6),
  cost_usd          Decimal(18,6)
) ENGINE = MergeTree
PARTITION BY toYYYYMMDD(ts)
ORDER BY (tenant_id, ts);
```

### 12.3 `gateway_audit` (对象存储 + 索引)

prompt / response 全文脱敏后写 S3 / OSS（合规要求 6–12 月）；Postgres 只存对象 key 和元数据。审计调阅走 [L8 安全治理](./08-security-and-governance.md) 流程。

---

## 13. MVP 范围（4–6 周）

| 周 | 交付物 |
|---|---|
| W1 | Ingress + AuthN + 双 Endpoint 骨架；接 LiteLLM 跑通 Claude + Qwen + DeepSeek |
| W2 | Rule Router（YAML 加载）+ Failover (CLOSED/OPEN 两态)；Prometheus 指标 |
| W3 | Exact Cache + Token 计数 + Postgres 落 `gateway_request`；价格表 |
| W4 | 限流 (令牌桶 + Redis) + 租户日预算；429 / 降级路径 |
| W5 | 流式代理统一 SSE；Anthropic / OpenAI 流格式适配；TTFT 指标 |
| W6 | Semantic Cache (Qdrant) + 管理台 (NewAPI 二开)；压测 + 灰度 5%流量 |

**不在 MVP 范围**：Embedding Router / Learned Router、Prompt Cache 透传 (V2)、Half-Open 探测 (V2)、ClickHouse 实时聚合 (用 PG 凑合，V2 上 CH)、Audit 全量入冷存 (V2)。

---

## 14. 真实坑（务必提前考虑）

| # | 坑 | 触发频率 | 应对 |
|---|---|---|---|
| 1 | **Tokenizer 估算偏差** Claude / GPT / Qwen 各家不一，中文偏差最高 30%+ | 每天 | 每模型独立 tokenizer；预估只用于配额预扣，结算用 Provider 实算 |
| 2 | **流式协议差异** Anthropic event-based、OpenAI data-only、Qwen 部分错按 NDJSON | 接新模型必踩 | Adapter 写一个流式状态机，按 event_type 路由 |
| 3 | **限流响应不统一** 有 429、有 503、有连接 reset、有静默 truncate | 每周 | 维护 error 规则库 (regex + http code + body 关键词)，命中即映射 |
| 4 | **价格频繁变** 2024–2026 价格降了 5–10×，年内调价 3–5 次属常态 | 每季度 | 价格表热更新 + 历史账单按 effective_at 回放 |
| 5 | **Lost-in-the-middle** 声称 1M 上下文实际 200K 后质量大降 | 长上下文场景 | Router 拒绝 > 阈值的 prompt，强制走 RAG (L3) 或截断 |
| 6 | **Tool use schema 差异** Anthropic `input_schema`、OpenAI `parameters`、并行调用支持度不一 | 接新模型 | Adapter 双向转换；不支持并行的模型路由层屏蔽 |
| 7 | **国产 API 高峰期不稳** 阿里 / 文心 / 豆包白天峰段秒级延迟 / 限流抖动 | 每天 | 必须有跨厂商备模型；国产之间也要互备 |
| 8 | **Prompt Cache 命中陷阱** 系统 prompt 里塞了时间戳 / UUID 永远不命中 | 接入即踩 | Adapter 在加 cache_control 前扫描动态变量并告警 |
| 9 | **超长 stream 内存泄漏** 长流式响应未及时 flush 造成 buffer 堆积 | 高并发场景 | 强制每 64KB / 100ms flush，Goroutine / Task 数量监控 |
| 10 | **预扣未释放** 流式 cancel 后没结算，配额"挂账" | 上线 1-2w 内会暴露 | 每个请求注册 defer 结算；30s 未结算的事件由 reaper 强制冲销 |

---

## 15. 待决议

- [ ] **进程语言**：Go (生态/招聘) vs Rust (性能/安全)；流量 < 10k QPS Go 完全够
- [ ] **是否在网关做 PII 脱敏**：当前思路在网关做粗粒度，细粒度交 [L8 安全治理](./08-security-and-governance.md)
- [ ] **Embedding Router 的训练数据来源**：用 [L7 eval](./07-observability-and-eval.md) 历史数据回灌还是新标注
- [ ] **是否开放"客户自带 API Key"模式 (BYOK)**：节省客户成本但破坏统一计费
- [ ] **流式 Failover 默认策略**：续接 vs 重来——倾向重来 (简单) + 上层 SDK 重试
- [ ] **Audit 留存周期**：金融 12 月、政企 6 月、互联网 3 月——按租户配置 vs 一刀切
- [ ] **是否支持 WebSocket 入口**（除 SSE）：客户端复杂度 vs 双向性需求；目前倾向 SSE only

---

## 关联文档

- 模型选型与商业策略：[L11 模型策略](./11-model-strategy.md)
- 协议字段 / 流式 / Tool schema：[L12 LLM API 协议](./12-llm-api-protocols.md)
- 路由后置评估：[L7 可观测与评估](./07-observability-and-eval.md)
- 出口策略 / 出境合规：[L25 数据合规与驻留](./25-data-compliance-and-residency.md)
- 多租户隔离与计费维度：[L24 多租户隔离](./24-multi-tenant-isolation.md)
- 选型对比与开源栈：[L16 开源栈选型](./16-opensource-stack-decision.md)
- 跨区域容灾切换：[L26 灾备 BCM](./26-disaster-recovery-bcm.md)
- 账单 / showback / 预算：[L21 FinOps 成本管理](./21-finops-cost-management.md)
- 当前问题与缓解：[L10 当前问题](./10-current-problems-and-mitigations.md)
- 安全审计与脱敏：[L8 安全治理](./08-security-and-governance.md)
