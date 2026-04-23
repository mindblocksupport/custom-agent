# L4 · 工具 / 函数调用 / MCP 运行时

> 状态：**讨论中** · 版本 v0.2（重写）· 2026-04-22 · Owner: Agent Platform / Tools WG

> v0.2 重写说明：v0.1 把"工具 + 技能 + 沙箱 + 集成"全部塞进一篇，与 [L14 计算机/浏览器使用](./14-computer-and-browser-use.md)、[L15 知识工程与 Skills](./15-knowledge-engineering-and-skills.md)、[L16 OSS 技术栈](./16-oss-stack.md)、[L22 HITL 与高风险工具](./22-human-in-the-loop.md)、[L24 多租户](./24-multi-tenant.md)、[L25 合规](./25-compliance.md) 大量重叠。v0.2 将本层收束为**工具/函数调用与 MCP 运行时**这个工程层，专注于协议、注册中心、调用执行、沙箱集成。

---

## 1. 本层职责

L4 是 Agent 与"外部世界"之间唯一的执行通道。Agent 决策（[L2](./02-agent-runtime.md)）→ 选工具 → **L4 执行** → 把结构化结果返回给 Agent。

### 1.1 In Scope（本层负责）

| 域 | 内容 |
|---|---|
| 工具协议 | OpenAI Function Calling / Anthropic Tool Use / **MCP（JSON-RPC 2.0）** |
| 注册中心 | tool registry（id/schema/version/permissions/risk/sla/cost） |
| 工具发现 | 两阶段路由（embedding 召回 + LLM 选择） |
| 调用执行 | 鉴权穿透 / 参数校验 / 超时重试 / 并行 / 结构化错误 |
| 沙箱集成 | 调度到 [L16](./16-oss-stack.md) 的 gVisor / E2B / Microsandbox / Kata |
| MCP 服务器 | 本地 stdio / 远程 SSE/HTTP / 沙箱化 / Marketplace |
| 企业系统集成 | SAP/用友/金蝶/Salesforce/钉钉/飞书 适配器与代理 |
| 工具描述与质量 | 描述规范、评分、A/B 比较 |

### 1.2 Out of Scope（边界与引用）

| 主题 | 归属 | 说明 |
|---|---|---|
| 计算机使用 / 浏览器使用 | [L14](./14-computer-and-browser-use.md) | "操作 GUI" 是一类**特殊工具**，单列 |
| Skills / SKILL.md / 知识工程 | [L15](./15-knowledge-engineering-and-skills.md) | Skills 是更高层的"打包能力"，本层只负责其 tool 调用部分 |
| 沙箱实现细节（gVisor/Firecracker/Kata 内核） | [L16](./16-oss-stack.md) | 本层只做"调度选型"，不展开实现 |
| HITL 审批流（L4-L5 风险工具如何走人工） | [L22](./22-human-in-the-loop.md) | L4 提供 hook，L22 负责流程 |
| 工具开发 SDLC / 测试 / CI | [L23](./23-agent-sdlc.md) | 本层只描述生命周期阶段 |
| 多租户配额、隔离、审计 | [L24](./24-multi-tenant.md) | L4 提供 hook（owner/permissions） |
| 数据合规、数据出境 | [L25](./25-compliance.md) | L4 提供 hook（risk_level/data_class） |
| 编排 / 多 Agent 工具共享 | [L13](./13-orchestration-and-multi-agent.md) | 工具路由、Agent-as-Tool 走编排层 |
| 模型适配（不同模型 tool 接口差异） | [L12](./12-model-gateway.md) | Model Gateway 负责协议归一化 |

---

## 2. 工具分类与风险等级

风险等级 L0–L5 的定义、HITL 触发策略、四眼审批等流程见 [L22 §3](./22-human-in-the-loop.md)。L4 在 tool registry 里**记录**等级并在调用前**强制**走 HITL gate。

| 风险 | 类型 | 例子 | L4 责任 |
|---|---|---|---|
| L0 | 只读/检索 | `search_kb` / `query_order` | 直接执行，记审计 |
| L1 | 计算/转换 | 报表生成、JSON→Excel | 沙箱执行 |
| L2 | 轻写入（可逆） | 建草稿、加 tag、打标签 | 记录原值便于回滚 |
| L3 | 重写入（不可逆） | 改订单、删文件、改库存 | **dry_run 优先 + L22 HITL** |
| L4 | 资金/外发 | 转账、发邮件给客户、发短信 | **强制 HITL，四眼审批** |
| L5 | 系统级/不可恢复 | 删除生产库、kill -9、删用户 | **多人审批 + 录音/录像 + 审计长期归档** |

---

## 3. MCP（Model Context Protocol）深度

> MCP 是 2026 年企业 Agent 平台的事实标准。本节是本文重点补强部分。

### 3.1 协议核心

- **底层协议**：JSON-RPC 2.0
- **传输**：
  - **stdio**（本地）：MCP server 作为子进程，通过 stdin/stdout 通信。开发期 / Desktop 场景默认。
  - **SSE**（已废弃但仍存量）：Server-Sent Events，2024 早期方案，2025-03 起被 Streamable HTTP 取代。
  - **Streamable HTTP**（2025 主推）：单端点，HTTP POST + 可选 SSE 回流。支持负载均衡、CDN，企业生产推荐。
- **Schema**：基于 JSON Schema 定义参数与返回。
- **多语言 SDK**：Python / TypeScript / Java / C# / Go / Rust / Kotlin / Swift 官方齐全（2026Q1）。

### 3.2 三原语 + 三高级能力

| 原语 | 方向 | 用途 |
|---|---|---|
| **Tools** | server → client | 可被 LLM 主动调用的函数（最常用，本层主战场） |
| **Resources** | server → client | 只读上下文数据（文件、数据库 row、API 结果），由 client/用户决定何时引入 |
| **Prompts** | server → client | 预定义提示模板，用户从 UI 选择触发 |

| 高级能力 | 方向 | 用途 |
|---|---|---|
| **Sampling** | client → server → client | server 反向请求 client 调用 LLM（让工具拥有"思考"能力） |
| **Roots** | client → server | 把本地文件系统根目录暴露给 server（可控范围） |
| **Elicitation**（2025-08 加入） | server → client | server 在执行中向用户索要补充信息（如缺参） |

### 3.3 认证：OAuth 2.1

2025-03 spec 引入 OAuth 2.1 + PKCE 作为 remote MCP server 标准认证：

- 支持 **Dynamic Client Registration**（RFC 7591）
- 支持 **Authorization Server Metadata**（RFC 8414）
- 2025-06 更新允许 MCP server **委托**给独立 IdP（避免人人自建 OAuth）
- 企业落地常见：MCP Server 与企业 IdP（Okta / Azure AD / Authing）打通，Agent 调用时透传用户 token（见 §8.1 鉴权穿透）

### 3.4 2026 生态

| Registry / Hub | 规模（2026Q1） | 特征 |
|---|---|---|
| **Anthropic Official MCP Registry** | 数百精选 | 官方背书，2025 下半年上线 |
| **mcp.so** | 5,000+ | 社区中文友好 |
| **Smithery** | 4,000+ | 一键部署 + 托管 |
| **PulseMCP** | 12,500+ | 最大目录，含 review |
| **Glama / mcpservers.org** | 数千 | 分类索引 |

主要 adopter（2026Q1 时间线）：

- **Claude Desktop / Claude Code**：MCP 起点（2024-11）
- **Cursor / Continue / Cline / Goose / Zed / Sourcegraph Cody**：2025 上半年原生支持
- **VS Code**：2025-06 GA
- **Windsurf / Replit**：2025 跟进
- **OpenAI**：2025-05 在 Responses API 加入 MCP
- **Google Gemini API**：2025 跟进
- **Anthropic 2026** 将 MCP 治理捐赠给 **Linux Foundation**（参考 OCI / CNCF 模式）

### 3.5 MCP 安全坑（必读 — 真实 CVE）

> 2025 年 MCP 爆发期暴露了大量安全问题，以下都是已发生的真实事件：

| 时间 | 事件 | 影响 | 来源 |
|---|---|---|---|
| 2025-04 | **Tool Poisoning** | 恶意 MCP server 在 tool description 里藏指令，LLM 读到后泄露 SSH 密钥 / 配置文件 | Invariant Labs |
| 2025-07 | **MCPoison（CVE-2025-54136）** | Cursor MCP 配置加载缺乏校验，本地写入恶意 mcp.json 即 RCE | Check Point |
| 2025-08 | **mcp-server-git RCE** | 参数注入 → `git clone` 命令拼接 → RCE 链 | GitHub Security Advisory |
| 2025-09 | **postmark-mcp npm 后门** | 被劫持的 npm 包，邮件发送时复制到攻击者地址 | Snyk |
| 2025-10 | **Indirect Prompt Injection via Tool Result** | 工具返回的 markdown 含隐藏指令，LLM 执行后越权调其他工具 | 多家厂商联合披露 |
| 2026-04 | **Ox Security 报告** | ~30 个高危漏洞，覆盖 1.5 亿+ 累计下载量的主流 MCP server | Ox Security 2026-04 |

**OWASP MCP Top 10**（2026 草案）：

1. Tool Description Injection
2. Indirect Prompt Injection via Tool Result
3. Insufficient Sandboxing of MCP Server
4. Supply Chain Attack（npm/pypi 包劫持）
5. Insecure OAuth Configuration（无 PKCE / 弱 redirect URI 校验）
6. Excessive Permissions（roots 暴露过宽）
7. Confused Deputy（server 用自身权限做用户的事）
8. Unbounded Sampling Loop（Sampling 失控烧 token）
9. Insecure Local Config（mcp.json 无校验/签名）
10. Lack of Audit Trail

**企业落地强制要求**：

- 所有 MCP server **必须**走内部 marketplace（不允许 Agent 直连公网未审计 server）— 见 [L23](./23-agent-sdlc.md)
- Tool description 进入 prompt 前**做一次扫描**（注入关键词、零宽字符、长度异常）
- MCP server 进程**必须**沙箱化（gVisor / Microsandbox），禁止裸跑
- 所有 MCP 调用**强审计**（who / when / which server / which tool / args / result hash）

### 3.6 工具路由：>50 工具时怎么办

LLM 在 prompt 里塞 100+ 工具会出现：context 暴涨、选错率上升、token 烧钱。两阶段路由是 2026 行业共识：

```
(用户请求 + 历史)
   ↓
[阶段 1] embedding 召回 top 20–30 工具（基于 description 向量）
   ↓
[阶段 2] LLM 在召回集中精确选择
   ↓
执行
```

更深的工具路由策略（场景绑定、层级目录、Agent-as-Tool）见 [L13](./13-orchestration-and-multi-agent.md)。

### 3.7 MCP Server 托管模式

| 模式 | 部署 | 适用 | 风险 |
|---|---|---|---|
| **Local stdio** | Agent 进程 fork | Desktop / 开发期 | 完全信任，不能在企业生产 |
| **Sandboxed local** | gVisor / Microsandbox 内 stdio | 单租户私有 server | 隔离强，启动有开销 |
| **Remote SSE/HTTP** | 独立服务，OAuth 2.1 | 多 Agent 共享、跨租户 | 推荐生产形态 |
| **Marketplace 托管** | 平台统一托管 + 计费 | 第三方 server 给企业用 | 必须签名、扫描、灰度 |

---

## 4. 协议差异：OpenAI vs Anthropic vs MCP

L12 [Model Gateway](./12-model-gateway.md) 负责把内部统一格式翻译成各家协议。L4 维护**唯一**内部 schema，不为每家模型重写工具。

| 维度 | OpenAI Function Calling | Anthropic Tool Use | MCP |
|---|---|---|---|
| Schema 字段 | `parameters`（JSON Schema） | `input_schema`（JSON Schema） | `inputSchema`（JSON Schema） |
| 并行调用 | 支持 | 支持 + thinking | 支持 |
| 调用 ID | `tool_call_id` | `tool_use_id` | JSON-RPC `id` |
| 流式工具 | delta 流式 | content_block_delta | Streamable HTTP 分块 |
| 强制调用 | `tool_choice=required/auto/none` | `tool_choice=any/tool/auto` | client 决定 |
| 错误反馈 | role=tool, content=error | tool_result, is_error=true | JSON-RPC error code |
| 跨模型可移植 | ✗ | ✗ | **✓**（核心优势） |

**内部规范建议**：

- 工具内部 schema = MCP schema 的超集（多 owner / risk_level / hitl_required / cost / sla）
- L12 在出向时自动剥离非 MCP 字段，转译成各家协议
- 工具实现优先按 MCP server 写，本地 / 远程都能复用

---

## 5. 工具描述质量（直接决定调用准确率 60% → 90%+）

工具描述是**给 LLM 的文档**，不是给人的。一个 description 改写能让相同工具集准确率从 60% 提升到 90%+。

**坏例子**：

```python
def get_data(id: str) -> dict:
    """获取数据"""
```

**好例子**：

```python
def query_order(order_id: str, include_items: bool = False) -> Order:
    """
    查询电商订单详细信息（B2C 主站，不含跨境）。

    适用场景：
        - 用户问"我的订单 12345 状态如何"
        - 客服需查看完整订单详情
        - 财务对账抽样

    不适用：
        - 跨境订单（用 query_cross_border_order）
        - 退款流水（用 query_refund）
        - 30 天前订单批量查询（用 export_archived_orders）

    参数：
        order_id: 订单号，纯数字字符串，长度 8-12，例如 "12345678"
        include_items: 是否包含订单商品明细。默认 False。
                       订单含 20+ 件时返回体可能 >1MB，不建议开启。

    返回 Order：
        - status: "pending" | "paid" | "shipped" | "delivered" | "cancelled"
        - amount: Decimal，单位元，保留两位
        - created_at: ISO 8601 UTC

    错误：
        - OrderNotFound: 订单不存在或已归档（>180 天）
        - PermissionDenied: 用户无该订单查看权限（多为跨租户访问）
        - RateLimited: 当前用户 QPS 超限，建议等 1s 重试
    """
```

**评分维度（内部 lint 工具 + LLM judge）**：

| 维度 | 检查项 |
|---|---|
| 触发场景明确 | "适用 / 不适用" 段是否清晰 |
| 参数有约束 | 类型/格式/范围/示例齐全 |
| 返回有结构 | 字段、枚举值列出 |
| 错误可学习 | 错误码 + 处理建议 |
| 无注入风险 | 无可疑指令、零宽字符、超长描述 |
| 长度合理 | 200–800 token 之间最佳 |

工具上架前必须过 lint + LLM judge 双轨，分数 < 80 不允许上架（流程见 [L23](./23-agent-sdlc.md)）。

---

## 6. 工具注册中心数据模型

### 6.1 字段定义

| 字段 | 类型 | 说明 |
|---|---|---|
| id | uuid | 全局唯一 |
| name | string | 调用名（snake_case，全平台不重复） |
| version | semver | major.minor.patch |
| description | text | 给 LLM 看的描述（§5） |
| input_schema | json | JSON Schema |
| output_schema | json | JSON Schema |
| category | enum | search / write / compute / external / code_exec / browser / computer |
| owner_team | string | 业务负责团队 |
| owner_email | string | 责任人邮箱 |
| permissions | json | 角色 / 部门 / 租户白名单（hook 给 [L24](./24-multi-tenant.md)） |
| risk_level | enum | L0–L5（hook 给 [L22](./22-human-in-the-loop.md)） |
| hitl_required | bool | 是否必走人工 |
| data_class | enum | public / internal / confidential / restricted（hook 给 [L25](./25-compliance.md)） |
| sla_timeout_ms | int | 超时（默认 30000） |
| sla_retry | json | 重试策略（idempotent / max / backoff） |
| cost_per_call | decimal | 计费单价（hook 给 [L24](./24-multi-tenant.md) 配额） |
| sandbox_profile | enum | none / docker / gvisor / e2b / microsandbox / kata |
| transport | enum | http / mcp_stdio / mcp_sse / mcp_http / native |
| endpoint | string | URL or command |
| auth_mode | enum | none / oauth_passthrough / token_exchange / saml / signed_jwt |
| tags | string[] | 用于 embedding 路由 |
| status | enum | draft / staging / ga / deprecated / retired |
| created_at | timestamp | |
| deprecated_at | timestamp | 标记淘汰时间 |
| audit_required | bool | 强审计开关（默认 true） |

### 6.2 SQL（PostgreSQL）

```sql
CREATE TABLE tool_registry (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            VARCHAR(128) NOT NULL,
  version         VARCHAR(32)  NOT NULL,
  description     TEXT         NOT NULL,
  input_schema    JSONB        NOT NULL,
  output_schema   JSONB,
  category        VARCHAR(32)  NOT NULL,
  owner_team      VARCHAR(64)  NOT NULL,
  owner_email     VARCHAR(128) NOT NULL,
  permissions     JSONB        NOT NULL DEFAULT '{}',
  risk_level      SMALLINT     NOT NULL CHECK (risk_level BETWEEN 0 AND 5),
  hitl_required   BOOLEAN      NOT NULL DEFAULT FALSE,
  data_class      VARCHAR(16)  NOT NULL DEFAULT 'internal',
  sla_timeout_ms  INTEGER      NOT NULL DEFAULT 30000,
  sla_retry       JSONB        NOT NULL DEFAULT '{"idempotent":false,"max":0}',
  cost_per_call   NUMERIC(10,4) NOT NULL DEFAULT 0,
  sandbox_profile VARCHAR(32)  NOT NULL DEFAULT 'gvisor',
  transport       VARCHAR(16)  NOT NULL,
  endpoint        TEXT         NOT NULL,
  auth_mode       VARCHAR(32)  NOT NULL DEFAULT 'oauth_passthrough',
  tags            TEXT[]       NOT NULL DEFAULT '{}',
  status          VARCHAR(16)  NOT NULL DEFAULT 'draft',
  audit_required  BOOLEAN      NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  deprecated_at   TIMESTAMPTZ,
  UNIQUE (name, version)
);

CREATE INDEX idx_tool_status_category ON tool_registry (status, category);
CREATE INDEX idx_tool_tags_gin        ON tool_registry USING GIN (tags);
CREATE INDEX idx_tool_perms_gin       ON tool_registry USING GIN (permissions);

CREATE TABLE tool_embedding (
  tool_id      UUID PRIMARY KEY REFERENCES tool_registry(id) ON DELETE CASCADE,
  embedding    VECTOR(1024) NOT NULL,
  embedded_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE tool_invocation_log (
  id              BIGSERIAL PRIMARY KEY,
  trace_id        UUID         NOT NULL,
  agent_id        UUID         NOT NULL,
  tenant_id       UUID         NOT NULL,
  user_id         UUID         NOT NULL,
  tool_id         UUID         NOT NULL REFERENCES tool_registry(id),
  tool_version    VARCHAR(32)  NOT NULL,
  args_hash       CHAR(64)     NOT NULL,
  args_redacted   JSONB,
  result_hash     CHAR(64),
  status          VARCHAR(16)  NOT NULL,  -- ok / error / timeout / hitl_pending
  hitl_decision   VARCHAR(16),            -- approved / rejected / na
  latency_ms      INTEGER,
  cost            NUMERIC(10,4),
  error_code      VARCHAR(64),
  started_at      TIMESTAMPTZ  NOT NULL,
  finished_at     TIMESTAMPTZ
);
CREATE INDEX idx_inv_tenant_time ON tool_invocation_log (tenant_id, started_at DESC);
CREATE INDEX idx_inv_trace       ON tool_invocation_log (trace_id);
```

---

## 7. 生命周期管理（仅描述阶段，流程见 [L23](./23-agent-sdlc.md)）

```
draft → staging → ga → deprecated → retired
  │        │        │        │           │
  本地     灰度     正式     标记         180 天
  开发    白名单   全量      新调用       后强制
                          降级警告        删除
```

每个阶段的 owner、CI、灰度比例、回滚策略统一在 L23 说明。L4 只**强制**：

- `draft` 工具不可被生产 Agent 调用
- `deprecated` 工具被调用时返回告警 header（让 Agent 切新版本）
- `retired` 工具直接 4xx，不再执行

---

## 8. 调用执行

### 8.1 鉴权穿透（重灾区）

工具调用必须以**当前用户身份**执行，不能用全局服务账号（否则越权 + 审计失效）。

| 模式 | 适用 | 实现 |
|---|---|---|
| **OAuth Token Exchange**（RFC 8693） | 大部分 SaaS / 内部系统 | Agent 拿用户 token → IdP 换目标系统 token → 调用 |
| **SAML Assertion** | 老企业系统、AD 域 | 用户 SAML assertion → STS → 目标系统 token |
| **Signed JWT (内部)** | 内部 API | 平台签发短期 JWT（含 user_id / tenant_id），目标 API 验签 |
| **Service Account + on-behalf-of header** | 不支持身份穿透的老系统 | 服务账号调用，附 `X-Acting-User` header，目标系统记录但需 + 审批 |

**反模式**（禁止）：用全局 admin token 调任何业务系统。

### 8.2 参数校验

1. **JSON Schema 强校验**：类型、范围、enum、pattern、required
2. **业务校验**：金额上限、白名单、租户隔离（`tenant_id` 必须 match 当前会话）
3. **校验失败**：返回结构化错误给 LLM 自纠

```json
{
  "is_error": true,
  "error_code": "INVALID_ARG",
  "field": "amount",
  "message": "amount 超出当前用户审批额度（最大 5000，传入 12000）",
  "suggestion": "请拆分订单或转人工审批"
}
```

### 8.3 超时与重试

| 工具 | 默认 | 重试 |
|---|---|---|
| 只读 / 幂等 | 30s | 3 次，指数退避（1s / 2s / 4s） |
| 写入 / 非幂等 | 30s | **不重试**，返错让 LLM 决策 |
| 长耗时（>30s） | 单独 sla_timeout_ms | 走异步 / job 模式（poll） |

### 8.4 并行调用

- 独立工具并行执行（OpenAI / Anthropic / MCP 都支持）
- **并发上限**：单 trace 默认 5，租户级配额见 [L24](./24-multi-tenant.md)
- **下游限流**：在 L4 工具适配器内做 token bucket，防 Agent "一调一千次" 打挂业务系统
- **依赖关系**：A 输出是 B 输入则串行，由编排层（[L13](./13-orchestration-and-multi-agent.md)）处理

### 8.5 错误反馈

错误**必须**结构化、可学习。**禁止**返回 stack trace 给 LLM（污染 context + 暴露内部）。

```json
{
  "is_error": true,
  "error_code": "ORDER_NOT_FOUND",
  "message": "订单 12345678 不存在",
  "suggestion": "请确认订单号 8-12 位纯数字，或调用 search_order 模糊查询"
}
```

---

## 9. 沙箱集成（深度选型见 [L16](./16-oss-stack.md)）

L4 不实现沙箱内核，只**调度**到下层 runtime。但需要根据工具特征选 profile：

| 场景 | 默认 sandbox_profile | 理由 |
|---|---|---|
| 内部受信 MCP server（只读） | `gvisor` | 系统调用过滤足够，启动 ~1s |
| 第三方 / Marketplace MCP server | `microsandbox` 或 `e2b` | 强隔离 + 短生命周期 |
| 用户自定义 Python 脚本 / 数据分析 | `e2b`（商用） 或 自建 `gvisor + 加固 docker` | 任意代码必须强隔离 |
| 短暂、轻量计算（<100ms 启动要求） | `firecracker` micro-VM | AWS Lambda 路径 |
| 需要 GPU + 处理高敏数据（如医疗影像） | `kata` + Confidential Computing（SEV-SNP / TDX） | 内存加密，云厂商也看不到 |
| 浏览器自动化 / GUI 操作 | 见 [L14](./14-computer-and-browser-use.md) | 浏览器有自己的 profile |

**默认底线（任何 sandbox_profile 必须满足）**：

- 网络默认 deny，按工具白名单开放（域名 / IP / 端口）
- 文件系统：rootfs 只读 + 临时写入区（执行结束即销毁）
- CPU / 内存 / 时间 limit（Cgroup v2）
- seccomp 过滤危险 syscall
- rootless（不允许 root）
- 凭据通过环境变量短期注入，禁止落盘

---

## 10. 企业系统集成（80% 时间在鉴权和数据格式）

| 系统 | 协议 | 鉴权 | 真实坑 |
|---|---|---|---|
| **SAP S/4HANA** | OData v4 / RFC / IDoc | OAuth 2.0 / SAP IdP | 协议老、字段名晦涩、需 SAP 顾问；建议先用 SAP BTP 包一层 OData |
| **用友 U8/NCC** | API + 数据库直连 | API Key / 钉钉登录 | 接口稳定性差、版本碎片化；建议加内部代理统一签名 |
| **金蝶 EAS/云星空** | API / WebService | API Key / 应用授权 | SOAP 残留、字段大量自定义；推荐 ETL 层落 ODS 再查 |
| **Salesforce** | REST / Bulk API 2.0 | OAuth 2.1 + JWT Bearer | 限流严（Composite 25/事务）；批量必走 Bulk |
| **钉钉** | 开放平台 API | 应用 access_token + 用户 token | 接口频繁变化、文档与实际不符；做版本兼容层 |
| **飞书 / Lark** | 开放平台 API | App access token + user token | tenant/user/app 三类 token 易混；权限模型复杂 |
| **企业微信** | 企业微信 API | corp + agent + user | 同上 |
| **Jira / Confluence** | REST | API Token / OAuth | 自定义字段每家不同，schema 必须运行期反射 |
| **内部 MySQL / Oracle** | JDBC / ODBC | 平台 IdP → DB Proxy | DBA 不愿开权限；走只读账号 + DB Proxy（限制表/列/行级） |
| **Mainframe / AS/400** | 屏幕抓取 / MQ | 隔离网段 | 走 RPA 桥接，由 [L14](./14-computer-and-browser-use.md) 计算机使用接管 |

### 10.1 数据格式坑

- **字段命名**：中拼英混用（`shopName` vs `店铺名` vs `pinpai_id`）→ 统一在适配层做 mapping
- **编码**：GB2312 / GBK / UTF-8 混合 → 入口统一转 UTF-8
- **时区**：服务端 UTC，UI 本地，老系统常 +08:00 写死 → 时区元数据必须显式
- **数值**：金额必须 `Decimal`，**禁止** float（0.1 + 0.2 ≠ 0.3）
- **日期**：`yyyyMMdd` / `yyyy-MM-dd` / Unix ts 混乱 → schema 强约束

---

## 11. iPaaS vs 直连 vs 代理 模式对比

| 模式 | 路径 | 优点 | 缺点 | 适用 |
|---|---|---|---|---|
| **直连** | Agent → SAP | 简单、低延迟 | 鉴权碎片化、限流难、审计散 | POC / 单系统 |
| **iPaaS**（如 MuleSoft / 阿里云 IS / Boomi） | Agent → iPaaS → SAP/CRM/钉钉… | 复用历史投资、连接器现成 | 多一跳延迟、按调用次数计费贵 | 已有 iPaaS 投资的中大型企业 |
| **代理（推荐）** | Agent → 内部 MCP/Tool Proxy → 业务系统 | 统一鉴权穿透、统一限流、统一审计、按 risk_level 拦截 | 需自建代理层 | **企业 Agent 平台默认** |

代理模式下，**所有**对外调用经过平台 proxy，proxy 负责：

- OAuth Token Exchange / 身份穿透
- 限流（租户级 + 全局）
- 审计落盘（写 `tool_invocation_log`）
- 风险拦截（risk_level + HITL gate）
- 成本计算（cost_per_call → [L24](./24-multi-tenant.md) 计费）
- 数据脱敏 / DLP（hook 给 [L25](./25-compliance.md)）

---

## 12. 工具市场 / 内部 Marketplace

详细的 SDLC、上架审核、灰度策略见 [L23](./23-agent-sdlc.md)。L4 只描述**接口契约**：

- 工具上架走统一 manifest（YAML），含上述所有 registry 字段
- 必须签名（开发者证书）
- 必须过 description lint + LLM judge + 安全扫描
- 高风险工具（risk_level >= 3）必须二人审核 + 录音
- 内置工具 / 第三方工具 / 用户私有工具三档
- 计量：调用次数 + 数据量 + 资源用量（hook [L24](./24-multi-tenant.md) 计费）

---

## 13. 真实坑总结

1. **工具描述比工具实现还重要**：工程师常把 80% 精力花在代码上，5% 在 description。结果调用错。
2. **工具数量爆炸**：>30 个工具不做路由，准确率断崖下跌；>100 个 prompt 直接爆。
3. **企业集成 80% 时间花在鉴权和数据格式**，实际"调通"只占 20%。
4. **写操作必须 dry_run**：先模拟、返回"将要做什么"、用户确认再执行。Stripe / GitHub API 的最佳实践。
5. **错误信息必须可学习**：返回 stack trace 给 LLM 是常见错误。
6. **下游限流必须在工具层做**：Agent 一旦循环错乱可能秒级千次调用。
7. **沙箱网络默认必须 deny**：开放白名单是 OWASP MCP Top 10 的常见漏洞。
8. **MCP server 不能裸跑**：2025 多起 RCE 都源于此。
9. **OAuth 配置错配**：弱 redirect URI 校验 / 缺 PKCE 是 MCP 第二大类问题。
10. **审计完整性 > 调用性能**：丢一条 invocation_log 比慢 100ms 严重得多。

---

## 14. MVP 范围

5–10 个核心工具 + 完整运行时。

| 工具 | 用途 | 风险 | sandbox |
|---|---|---|---|
| `search_kb` | 内部知识检索 | L0 | none |
| `search_web` | 公网检索 | L0 | gvisor |
| `query_db` | 受限只读 SQL（DB Proxy） | L1 | none |
| `query_order` / `query_customer` | 业务读 | L0 | none |
| `send_message` | 钉钉/飞书消息 | L2 | gvisor |
| `create_draft` | 邮件/文档草稿 | L2 | gvisor |
| `run_python` | 数据分析 / 报表 | L1–L3 | e2b 或 microsandbox |
| `read_file` / `write_file` | 文件读写（工作区内） | L1 | gvisor |
| `update_ticket` | 工单状态变更 | L3 | gvisor + HITL |

平台基础组件 MVP：

- tool_registry + tool_embedding（PG + pgvector）
- 两阶段路由（embedding 召回 + LLM 选择）
- JSON Schema 校验
- OAuth Token Exchange 鉴权穿透
- 默认 sandbox = gVisor
- 完整 invocation log + trace_id 串到 [L17 可观测性](./17-observability.md)
- Description lint + LLM judge

---

## 15. 待决议

| 议题 | 选项 | 影响 |
|---|---|---|
| MCP 自建 registry vs 直接对接 Anthropic registry / mcp.so / Smithery 镜像 | 自建（需安全扫描） / 镜像（需协议合规） | 见 [L23](./23-agent-sdlc.md) |
| MCP server 默认 sandbox：gVisor vs Microsandbox | gVisor 成熟、Microsandbox 启动更快 | 见 [L16](./16-oss-stack.md) |
| 用户自定义代码沙箱：自建 vs E2B 商用 | 自建可控、E2B 省事 | 见 [L16](./16-oss-stack.md) |
| 是否对外开放 marketplace（第三方上架） | 平台属性 vs 安全风险 | 见 [L23](./23-agent-sdlc.md) / [L26 商业模式](./26-business-model.md) |
| iPaaS 整合：自建代理 vs 复用现有 iPaaS | 取决于客户存量 | 实施期决定 |
| OWASP MCP Top 10 进入合规基线的优先级 | 一刀切 / 分阶段 | 见 [L25](./25-compliance.md) |
| 工具描述 lint 阈值（80 / 90 / 95） | 严格 → 上架慢 / 宽松 → 准确率低 | 平台规范决定 |
| 高风险工具是否强制四眼审批（不可关闭） | 强制 / 可由租户管理员关闭 | 见 [L22](./22-human-in-the-loop.md) |

---

## 引用层级索引

- [L10 整体架构总览](./10-architecture-overview.md)
- [L11 LLM 选型](./11-llm-selection.md)
- [L12 模型网关](./12-model-gateway.md)
- [L13 编排与多 Agent](./13-orchestration-and-multi-agent.md)
- [L14 计算机/浏览器使用](./14-computer-and-browser-use.md)
- [L15 知识工程与 Skills](./15-knowledge-engineering-and-skills.md)
- [L16 OSS 技术栈与沙箱](./16-oss-stack.md)
- [L17 可观测性](./17-observability.md)
- [L22 HITL 与高风险工具](./22-human-in-the-loop.md)
- [L23 Agent SDLC 与 Marketplace](./23-agent-sdlc.md)
- [L24 多租户](./24-multi-tenant.md)
- [L25 合规](./25-compliance.md)
- [L26 商业模式](./26-business-model.md)
