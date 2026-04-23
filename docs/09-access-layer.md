# L9 · 接入层 (Access Layer)

> 状态：**重写版** · 版本 v0.2 · 2026-04-22 · Owner: 接入 / 前端 / DevRel

> **关联层**：[L10 鉴权](./10-auth.md) · [L12 LLM API 协议](./12-llm-api.md) · [L13 工具](./13-tools.md) · [L14 Computer Use](./14-computer-use.md) · [L15 编排](./15-orchestration.md) · [L17 数据权限](./17-data-permission.md) · [L18 知识库](./18-knowledge.md) · [L22 HITL UX](./22-hitl-ux.md) · [L24 多租户](./24-multi-tenant.md) · [L25 计费](./25-billing.md) · [L26 评估](./26-eval.md) · [L27 语音](./27-voice.md) · [L28 安全](./28-security.md) · [L29 Onboarding](./29-onboarding.md) · [L30 垂直模板](./30-verticals.md) · [L33 SDK 生态](./33-sdk-ecosystem.md) · [L35 监控](./35-monitoring.md) · [L36 国际化](./36-i18n.md)

---

## 1. 本层职责

接入层是 **Agent 平台触达用户的最后一公里**。再强的内核（L11–L17）、再准的 RAG（L18–L20）、再稳的运行时（L4–L6）—— 用户感知到的只是"打开 Web/IM 一句话能不能办成事"。

本层负责三个"多"：

| 维度 | 内容 |
|---|---|
| **多端 (multi-channel)** | Web 控制台 / IM Bot / IDE 插件 / 移动 H5 / CLI / OpenAPI / SDK / Embed |
| **多协议 (multi-protocol)** | REST 同步 · SSE 流式 · WebSocket 双向 · Webhook 回调 · 异步任务 |
| **多租户 (multi-tenant)** | 租户隔离的鉴权、限流、配额、审计；详见 [L24](./24-multi-tenant.md) |

**商业价值**：

- 多端覆盖 = 更多场景 = 高频使用 = 高粘性 → 续费
- 嵌入企业既有工作流 (IM/IDE/OA) = **零用户教育**
- 开放 API + SDK + Embed = 深度集成 → 高切换成本 → 高 NRR
- **OpenAI 兼容外观** = 客户改一行 `base_url` 切到你（[L12](./12-llm-api.md)）

---

## 2. 端形态全清单

### 2.1 矩阵概览

| 端 | 主用户 | 核心场景 | MVP | 关键技术 |
|---|---|---|---|---|
| Web 控制台 | 配置者 / 重度用户 | 调试 / 管理 / 看板 | P0 | Next.js 15 + Vercel AI SDK 6 / Assistant-UI |
| IM Bot | 业务一线 | 群 @ / 私聊 / 卡片 | P0 (1 个) | 飞书 / 钉钉 / 企微 / Slack / Teams |
| IDE 插件 | 开发者 | 代码 / 项目 RAG | P1 | VSCode / JetBrains Platform |
| 移动 H5 | 出差 / 一线 | IM 内嵌 / 链接 | P1 | PWA + 响应式 |
| 移动原生 | 高频移动 | 推送 / 录音 / 离线 | P2 | React Native / Flutter |
| CLI | 开发者 / SRE | 脚本 / CI | P1 | Click / Cobra |
| OpenAPI | 集成方 / ISV | REST + SSE + WS | P0 | OpenAPI 3.1 + AsyncAPI |
| SDK | 开发者 | Py / Node / Java / Go | P0 (Py+Node) | 自动生成 + 手写胶水 |
| OpenAI 兼容外观 | 已有 OpenAI 集成 | 一行切换 | P0 | 见 [L12](./12-llm-api.md) |
| Embed / Web Component | 客户网站 | 嵌入式客服 | P1 | iframe + postMessage / Custom Element |
| 白标 (white-label) | 大客户 / 渠道 | 域名/Logo/主题 | P2 | 多租户 + CDN 主题包 |

### 2.2 Web 控制台

**技术栈推荐**（2026 主流）：

| 层 | 选型 | 备注 |
|---|---|---|
| 框架 | Next.js 15 + React 19 | App Router + Server Actions |
| AI 渲染 | **Vercel AI SDK 6** 或 **Assistant-UI** | 流式 / 工具调用 / Generative UI 开箱即用 |
| UI | Tailwind v4 + shadcn/ui | + Radix Primitives |
| 状态 / 数据 | Zustand + TanStack Query + SSE | RSC 不全替代客户端状态 |
| 编辑器 | Monaco / CodeMirror 6 | 工具调试 / 代码块 |
| Markdown | react-markdown + remark + shiki | 数学 KaTeX；图表 Mermaid |
| 图表 | Recharts / Echarts | 数据看板 |
| 国际化 | next-intl / i18next | 中英起步；详见 [L36](./36-i18n.md) |
| 监控 | Sentry + PostHog | 错误 + 用户行为 |

**核心模块**：对话主界面 / 知识库 ([L18](./18-knowledge.md)) / 工具 ([L13](./13-tools.md)) / Agent 编排 ([L15](./15-orchestration.md)) / 数据看板 ([L35](./35-monitoring.md)) / 团队权限 ([L10](./10-auth.md)+[L24](./24-multi-tenant.md)) / 计费 ([L25](./25-billing.md))。

### 2.3 IM 集成（高频）

| IM | 用户量 | 难度 | 协议特点 | 真实坑 |
|---|---|---|---|---|
| **飞书** | 高速增长 ToB | 中 | 文档清晰 / Card v2 / Long-Connection | 卡片协议每年改、tenant_access_token 过期 |
| **钉钉** | 国内最大 ToB | 中 | Stream / HTTP 双模式 | 协议常变、审核严、大企业封闭 |
| **企业微信** | 国企 / 传统 | 难 | 限制多 / 加密回调 | 自建 vs 第三方差异大 |
| **Slack** | 海外 SaaS | 易 | Block Kit / Events / Socket Mode | 3s ACK 窗口 / 限频 |
| **Teams** | 海外大企 | 中 | Bot Framework / Adaptive Cards | Azure AD / 部署复杂 |
| **Lark** | 海外华企 | 中 | 与飞书近似 / region 隔离 | 数据驻留 / API host 不同 |
| **WhatsApp Business** | 海外 To B/C | 中 | Cloud API / 模板审核 | 模板审核 24h+ |
| **微信公众号 / 小程序** | C 端 | 难 | 5s 超时 / 客服 48h 窗口 | 流式不友好、长回复需异步推送 |

**集成模式**：群聊 `@` / 私聊 1v1 / **卡片消息**（按钮、表单、流式更新卡片）/ 工作流 / 审批 / 文档 / 日历集成。

### 2.4 IDE 插件

| IDE | 必做 | 备注 |
|---|---|---|
| **VSCode** | P0 | 用户最大、API 成熟 |
| **JetBrains 全家桶** | P1 | Java/Go/Python 客户必装 |
| **Cursor / Windsurf / Zed** | 共存 | 已自带 AI；做 MCP Server / OpenAI 兼容入口 |
| **Vim / Emacs / Helix** | 视用户 | LSP-style 桥接 |
| **Web IDE** (gitpod/coder) | P2 | 内嵌 Web 控制台或 iframe |

能力：选中代码问答 / 项目级 RAG / 与原生 Copilot 区分的代码补全 / git+PR 集成 / 终端 Agent。

### 2.5 移动端

**H5 + IM 嵌入**起步成本最低；**PWA** + Add-to-Home-Screen 近原生；**原生 App** (RN/Flutter) 仅在主战场（C 端/高频语音）才上。推送：APNs / FCM；国内必接厂商通道（华为/小米/OPPO/vivo/魅族），否则后台收不到。

### 2.6 CLI

给开发者 / SRE / DevOps Agent。脚本化、CI 集成、stdin/stdout 流。推荐 Click/Typer 或 Cobra。必备：`login` / `agents list` / `chat` / `task submit` / `logs` / `--json`。

### 2.7 OpenAPI / OpenAI 兼容外观

详见 §6；OpenAI 兼容详见 [L12](./12-llm-api.md)。

### 2.8 嵌入式 / Embed / 白标

| 形态 | 场景 | 技术 |
|---|---|---|
| iframe | 客户网站嵌入 | postMessage 双向；CSP 友好 |
| Web Component (`<my-agent-chat>`) | 现代前端 | Custom Element + Shadow DOM |
| JS Snippet (一行 `<script>`) | 营销页 / 客服 widget | 类 Intercom / Drift |
| 白标 | 渠道 / 大客户私域 | 自定义域名 + Logo + 主题 + 隐藏品牌 |

---

## 3. 协议设计深度

### 3.1 REST API（同步）

```
POST /v1/agents/{agent_id}/chat
  Headers: Authorization: Bearer <key>
           X-Tenant-Id: <tenant>
           X-Request-Id: <uuid>            # 追踪
           Idempotency-Key: <uuid>         # 写操作幂等
  Body:    { messages, stream?, metadata, tools_override?, hitl_policy? }
```

适合：短回复 (<3s)、历史/管理 GET、CRUD。

### 3.2 SSE 流式（主流）

```
POST /v1/agents/{id}/chat?stream=true
Accept: text/event-stream
```

**完整事件类型**：

| event | 时机 | data |
|---|---|---|
| `start` | turn 开始 | `{turn_id, model, ts}` |
| `thought` | 推理过程 (可折叠) | `{text, step_id}` |
| `tool_call` | 工具调用发起 | `{call_id, name, args, server}` |
| `tool_result` | 工具返回 | `{call_id, ok, result, latency_ms}` |
| `tool_error` | 工具失败 | `{call_id, code, message}` |
| `token` | 文本流 | `{delta, index}` |
| `citation` | 引用 | `{doc_id, span, score, url}` |
| `hitl_request` | 请求人工 ([L22](./22-hitl-ux.md)) | `{prompt, options, deadline}` |
| `progress` | 长任务进度 | `{pct, stage, eta_s}` |
| `usage` | 增量用量 | `{prompt_tokens, completion_tokens, cost_usd}` |
| `done` | 完成 | `{finish_reason, usage_total}` |
| `error` | 错误终止 | `{code, message, retriable}` |
| `ping` | 心跳 (15s) | `{}` |

**优势**：HTTP/防火墙/CDN 友好，实现简单。**劣势**：单向；客户端中途交互需另开 HTTP（如 `POST /sessions/{id}/cancel`）。

### 3.3 WebSocket（双向）

适用：双向语音 ([L27](./27-voice.md))、协同编辑、Computer Use 实时回放 ([L14](./14-computer-use.md))、IDE 插件中途插话。子协议建议 JSON-RPC 2.0 over WS。

### 3.4 长任务异步

适合：报表、深度研究、Computer Use 长流程。

```
POST /v1/tasks                  → { task_id, status: "queued" }
GET  /v1/tasks/{id}             → { status, progress, result?, error? }
GET  /v1/tasks/{id}/stream      → SSE 实时进度
WS   /v1/tasks/{id}/socket      → 双向 (中断/追加指令)
POST /v1/tasks/{id}/cancel
POST /v1/tasks/{id}/resume      → 断点恢复
```

生命周期：`queued → running → (paused?|hitl_waiting?) → succeeded|failed|cancelled|expired`

### 3.5 协议选择指南

| 场景 | 协议 |
|---|---|
| 一问一答短回复 | REST |
| 普通流式聊天 | SSE |
| 双向语音 / 协同 | WebSocket |
| 报表 / 长流程 / Computer Use | 异步 Task + SSE 进度 |
| 业务回调 | Webhook |

---

## 4. UI/UX 关键 (Web 端)

### 4.1 流式渲染

| 内容 | 关键点 |
|---|---|
| Markdown | 增量 parse；防 token 中断造成的 HTML 闪烁 |
| 代码块 | shiki 高亮（200+ 语言）/ 行号 / 复制 / 沙箱运行 |
| 数学 / 表格 | KaTeX inline `$..$` + block `$$..$$`；表格流式累积 + 超宽横滚 |
| Mermaid | 流程/时序/甘特，渲染 debounce |
| 图片 | OSS 直链 + 懒加载 + 占位避免抖动 |
| 生成式 UI | Vercel AI SDK Generative UI / Assistant-UI tools，工具直接渲染 React |

### 4.2 思考过程可折叠

默认折叠避免噪音，按钮"显示思考过程"展开；调试模式默认展开；流式时灰色渐入；支持复制思考链做反馈。

### 4.3 工具调用展示

| 状态 | UI |
|---|---|
| 调用中 | 工具图标 + 名称 + 参数摘要 + spinner + ETA |
| 成功 | 折叠卡片 + "查看结果"展开 (JSON/表格/图) |
| 失败 | 红边 + 错误码 + 重试 + 反馈 |
| 需 HITL | 黄色高亮 + 审批按钮 ([L22](./22-hitl-ux.md)) |

### 4.4 引用展示

行内角标 `[1][2]`（同 Perplexity / Bing Chat）；悬浮预览（标题+摘要+来源 logo+跳转）；底部"参考文献"列表；PDF/Doc 跳具体页码 + 高亮 span（[L18](./18-knowledge.md)）。

### 4.5 多模态输入

| 模态 | 实现 |
|---|---|
| 文本 | textarea + Composition Event 兼容输入法 |
| 图片 | 拖拽 / 粘贴 / 多图 / OCR 即时反馈 |
| 文件 | PDF/Word/Excel/PPT/代码；显示解析进度 |
| 语音 | MediaRecorder → Whisper / 本地 ASR；实时波形（[L27](./27-voice.md)） |
| 录屏 / 摄像头 | getDisplayMedia / getUserMedia → 截帧或片段 → Vision Model |

### 4.6 可中断 / 编辑重发 / 多版本

**中断**：流式中"停止"立即停 SSE + 后端 cancel，保留已输出。**编辑重发**：用户消息悬浮"编辑" → 修改后从该点 fork 新分支。**多版本**：助手消息底部"重新生成 (1/3)"切换；高级模式显示对话树。

### 4.7 反馈 / 4.8 引导发现

赞 / 踩 / 复制 / "为什么这个答案"（弹 trace 摘要）/ 详细反馈表单 → [L26 评估闭环](./26-eval.md)。首次使用 5 步遮罩 tour / 推荐问题 / 模板（按 Agent 分类）/ 工具市场 / Agent 广场 / 快捷指令 `/help` `@agent` `#kb` `!run` / 空对话区 3-6 sample prompt。

### 4.9 中文化

| 项 | 注意 |
|---|---|
| 字体 | 苹方 / 思源 / HarmonyOS Sans；fallback 链不丢 |
| 标点 | 中英标点不混用；代码内不替换 |
| 输入法 | Composition Event；回车提交看 isComposing |
| 节假日 | 春节/国庆等长假提示，影响 SLA |
| 时区 | 默认 Asia/Shanghai，海外切换显示用户本地 |
| 数字 | 中文常用"万/亿"；金额按地区格式 |

详见 [L36](./36-i18n.md)。

---

## 5. IM Bot 真实坑深度

### 5.1 协议变更

钉钉/飞书每年至少 2 次破坏性更新（卡片 v1→v2→v2.1）。做**协议适配层**，每 IM 一个 adapter，保留 v1/v2 双版本灰度。订阅厂商 changelog + 加官方运营群。

### 5.2 @ 提及解析

群聊 `@AI` 后文本可能含其他 `@user` 或表情；富文本 vs 纯文本两种事件并存，要 normalize；私聊不需 @ 但前端统一一套清洗。

### 5.3 卡片消息差异

| IM | 卡片技术 | 流式更新 | 互动元素 |
|---|---|---|---|
| 飞书 | Card v2 (JSON) | 支持 stream 卡片 | 按钮/表单/选择器 |
| 钉钉 | Markdown / ActionCard / FeedCard | 不支持流式（patch 消息） | 按钮 |
| 企微 | TextCard / NewsCard / TemplateCard | 不支持 | 受限 |
| Slack | Block Kit | chat.update 模拟流式 | 丰富 |
| Teams | Adaptive Cards | 支持但有延迟 | 丰富 |

写一层"卡片 DSL → 各 IM 卡片"的 transpiler。

### 5.4 长回复处理

单消息字数限制（飞书/钉钉约 5000 字符）。策略：a) 折叠为长文档；b) 转富文本附件；c) 拆多条+收起。流式：占位卡 → patch → 定型。

### 5.5 文件上传

各家协议不一：钉钉 media_id、飞书 file_token、Slack file.upload v2、企微 media_id 但格式不同。大文件需分片（>20MB）；用户上传文件下载 URL 短时效，要立即缓存。

### 5.6 消息有效期 / 5.7 机器人审核

飞书消息 24h 内可撤回/编辑；钉钉部分消息无法编辑；流式过程中"编辑"窗口已过则降级追加新消息。飞书/钉钉应用商店上架审核（隐私协议、能力声明、安全测试）；企微自建要管理员审批；WhatsApp Business 模板审核 24-72h。**提前 1-2 月走流程**。

### 5.8 限频与超时

| IM | 关键限制 |
|---|---|
| Slack | 3s 必须 ack（slow ack：先 ack 再后台处理） |
| 飞书 | 应用级 QPS；机器人发消息约 50 QPS |
| 钉钉 | Stream / Webhook 不同 token QPS 限制 |
| 微信公众号 | 5s 必返；超时只能客服消息异步推送 |

---

## 6. OpenAPI 设计

### 6.1 完整端点

| 资源 | 端点 |
|---|---|
| Chat | `POST /v1/chat` 或 `POST /v1/agents/{id}/chat`（stream 可选） |
| Sessions | `GET/POST /v1/sessions` `GET /v1/sessions/{id}/messages` |
| Tasks | `POST /v1/tasks` `GET /v1/tasks/{id}` `…/stream` `…/cancel` |
| Agents | `GET/POST/PATCH /v1/agents` |
| Tools/Skills | `GET/POST /v1/tools`（[L13](./13-tools.md)） |
| Knowledge | `GET/POST /v1/knowledge_bases` `…/documents`（[L18](./18-knowledge.md)） |
| Files | `POST /v1/files` `GET /v1/files/{id}` |
| Embeddings | `POST /v1/embeddings`（OpenAI 兼容） |
| Models | `GET /v1/models`（OpenAI 兼容） |
| HITL | `GET /v1/hitl/requests` `POST .../decision`（[L22](./22-hitl-ux.md)） |
| Webhooks | `GET/POST /v1/webhooks` |
| API Keys | `GET/POST/DELETE /v1/api_keys` |
| Usage | `GET /v1/usage` |
| Audit | `GET /v1/audit_logs` |

### 6.2 鉴权

| 方式 | 场景 |
|---|---|
| Bearer API Key | 默认 / 服务端集成 |
| OAuth 2.1 + PKCE | 第三方应用代用户操作 |
| JWT | SSO / 内部服务 |
| mTLS | 大客户高安全 |
| HMAC 签名 | Webhook 入站 / 高敏 API |

详见 [L10](./10-auth.md) + [L28](./28-security.md)。

### 6.3 限流（多维度同生效，取最严）

| 维度 | 默认（示例） | 用途 |
|---|---|---|
| 全局 | 100k req/min | 防 DDoS |
| 租户级 | 套餐定义 | [L25](./25-billing.md) |
| 用户级 | 60 req/min | 防个体异常 |
| API Key 级 | Key 创建时设置 | 客户自管 |
| IP 级 | 600 req/min | 防爬 / 扫描 |
| 模型级 | 按上游限流复制 | 防上游打满 |

算法：令牌桶（突发友好）+ 漏桶（保平稳）+ 热点 Key 滑动窗口。返回头：`X-RateLimit-Limit/-Remaining/-Reset`，超限 429 + `Retry-After`。

### 6.4 多语言 SDK

| 语言 | 受众 | 优先级 / 备注 |
|---|---|---|
| **Python** | 数据 / AI / 后端 | P0；Pydantic v2 |
| **Node/TS** | Web / Edge | P0；类型完整 |
| **Java** | 大企业 / 金融 | P1；JDK 17+ |
| **Go** | 基础设施 / 云原生 | P1 |
| **C#/.NET** | 微软生态 | P2 |

工程标准：自动重试+指数退避+jitter；流式 Python `async for` / Node `for await`；错误分层 `Auth/RateLimit/Server/Network/Validation`；Telemetry 可关闭；**OpenAI 兼容**（`from custom_agent import OpenAI` 或改 `base_url`）。详见 [L33](./33-sdk-ecosystem.md)。

### 6.5 SDK 示例（Python）

```python
from custom_agent import Client
client = Client(api_key="sk-xxx", base_url="https://api.example.com")

# 同步
resp = client.agents("kb-agent").chat("我的订单状态？", session_id="...")
print(resp.content, resp.citations)

# 流式
async for ev in client.agents("kb-agent").stream("..."):
    if ev.type == "token":      print(ev.delta, end="", flush=True)
    elif ev.type == "tool_call": print(f"\n[调用 {ev.name}]")

# 长任务
task = client.tasks.create(agent_id="report-agent", input={...})
async for ev in task.stream(): print(ev)
result = await task.wait()
```

---

## 7. Webhook（业务回调）

**事件**：

| 事件 | 触发 |
|---|---|
| `task.completed` / `task.failed` | 异步任务完结 |
| `hitl.requested` / `hitl.decided` | HITL ([L22](./22-hitl-ux.md)) |
| `feedback.created` | 用户反馈 |
| `session.ended` | 会话结束 |
| `knowledge.indexed` | 索引完成 |
| `usage.threshold` | 用量阈值（[L25](./25-billing.md)） |
| `agent.deployed` | Agent 发布 |

**投递保证**：HMAC-SHA256 签名（`X-Signature: t=...,v1=...`）；防重放 `X-Timestamp` + 服务端 5 分钟有效；重试指数退避 1m/5m/15m/1h/6h/24h 共 7 次；超最大重试进 DLQ，控制台手动重放；注册时发 `ping` 要求 200 验证端点。

---

## 8. 多 channel 用户身份映射

**核心问题**：同一用户在 Web / 飞书 / 钉钉 / API 中是同一个人，但每 channel 有自己的 ID。

```
identity (我们平台统一 user_id)
  ├─ identity_link (channel="lark",     external_id="ou_xxxxx")
  ├─ identity_link (channel="dingtalk", external_id="dingxxx")
  ├─ identity_link (channel="api_key",  external_id="ak_xxx")
  └─ identity_link (channel="sso_oidc", external_id="sub:xxx", iss="...")
```

| 场景 | 策略 |
|---|---|
| 企业 SSO（OIDC/SAML）+ IM | 邮箱 / 手机号 / employeeId 自动 link |
| 个人首次绑定 | Web 登录后扫码绑定 IM |
| 仅 IM 用户（无账号） | 自动建影子账号；后续可升级合并 |
| API Key 调用 | Key 关联 service account；带 `X-On-Behalf-Of` 代理为某用户 |

**SSO 透传**：OIDC/SAML token claims 透传 Agent 上下文（角色/部门/数据权限），与 [L10](./10-auth.md) + [L17](./17-data-permission.md) 配合。

---

## 9. 真实场景示例

### 9.1 飞书工作台 Agent

```
用户群里发 "@小助手 帮我查 5 月华东大区销售 Top10"
  │
  ▼
飞书事件回调 → 接入层 (lark adapter)
  ├─ 验签 / 解析 @ / normalize
  └─ identity 映射: lark_user_id → user_id → tenant_id
  ▼
鉴权 + 限流 + 配额 (L10/L24/L25)
  ▼
Agent 编排 (L15) → SQL 工具 (L13) → RAG (L18-20)
  ▼
流式 SSE → 接入层组装 Card v2
  ├─ 第一帧: 占位卡 (5s 内必发, 避免 IM 超时)
  ├─ N 帧: patch 卡片正文 (流式更新)
  └─ 末帧: 定稿 + "导出 Excel" / "追问" 按钮
```

### 9.2 OpenAPI 集成 CRM 侧边栏

```
客户 CRM 加入 "AI 助手" 侧边栏 (前端 React)
  ▼
client.agents("sales").stream(prompt, context={crm_record_id})
  ├─ Authorization: Bearer (客户租户 API Key)
  └─ X-Tenant-Id: <客户租户>
  ▼
接入层 Edge → SSE 一路转发到浏览器
  ├─ Agent 调用 CRM 工具 (MCP 反向接入客户 CRM, L13)
  └─ HITL 触发时, 前端弹审批 (L22)
  ▼
对话结束 → Webhook 回调 CRM (写回总结 / 线索评分)
```

### 9.3 IDE 插件代码解释

```
开发者选中代码 → 右键 "解释" → VSCode 命令
  ▼
扩展收集上下文: 选区 + 文件路径 + 语言 + git diff + 当前 PR
  ▼
client.agents("code").stream(...) 走 SSE
  ├─ 流式回到 IDE 侧边栏 (Webview)
  ├─ 工具调用展示: 跑测试 / 查 SO / 查 Issue
  └─ "应用建议" → 调 LSP edits / Quick Fix
  ▼
反馈 → 评估闭环 (L26)
```

---

## 10. 数据模型

```sql
-- 会话 (channel: web/lark/dingtalk/wecom/slack/teams/api/cli/ide/embed)
CREATE TABLE session (
  id UUID PRIMARY KEY, tenant_id UUID NOT NULL, user_id UUID NOT NULL, agent_id UUID NOT NULL,
  channel VARCHAR(32) NOT NULL, external_thread_id VARCHAR(128),  -- IM 群/会话 ID
  title TEXT, metadata JSONB,
  started_at TIMESTAMPTZ NOT NULL, last_active_at TIMESTAMPTZ NOT NULL, ended_at TIMESTAMPTZ,
  status VARCHAR(16) NOT NULL,  -- active/idle/ended/expired
  INDEX (tenant_id, user_id, last_active_at DESC), INDEX (channel, external_thread_id)
);

-- 消息 (parent_id 支持分支/重发; content_json 为多模态片段数组)
CREATE TABLE message (
  id UUID PRIMARY KEY, session_id UUID NOT NULL REFERENCES session(id), parent_id UUID,
  role VARCHAR(16) NOT NULL,  -- user/assistant/tool/system
  content_json JSONB NOT NULL, tool_calls JSONB, attachments JSONB, citations JSONB,
  usage JSONB, cost_usd NUMERIC(12,6), latency_ms INT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), INDEX (session_id, created_at)
);

-- API Key (key_hash 用 bcrypt/argon2; status: active/revoked/expired)
CREATE TABLE api_key (
  id UUID PRIMARY KEY, tenant_id UUID NOT NULL, name VARCHAR(128),
  key_prefix VARCHAR(16) NOT NULL, key_hash VARCHAR(128) NOT NULL,
  scopes TEXT[] NOT NULL,  -- ["chat:read","chat:write",...]
  rate_limit_rpm INT, rate_limit_tpm INT,
  expires_at TIMESTAMPTZ, last_used_at TIMESTAMPTZ,
  created_by UUID NOT NULL, status VARCHAR(16) NOT NULL,
  UNIQUE (tenant_id, name)
);

-- Webhook 订阅 (secret 为 HMAC 签名密钥)
CREATE TABLE webhook_subscription (
  id UUID PRIMARY KEY, tenant_id UUID NOT NULL, url TEXT NOT NULL,
  secret BYTEA NOT NULL, events TEXT[] NOT NULL,
  active BOOLEAN NOT NULL DEFAULT true, created_at TIMESTAMPTZ NOT NULL,
  last_success_at TIMESTAMPTZ, last_failure_at TIMESTAMPTZ, failure_count INT NOT NULL DEFAULT 0
);

-- 身份映射 (issuer 为 SSO iss)
CREATE TABLE identity_link (
  id UUID PRIMARY KEY, user_id UUID NOT NULL,
  channel VARCHAR(32) NOT NULL, external_id VARCHAR(255) NOT NULL, issuer VARCHAR(255),
  metadata JSONB, linked_at TIMESTAMPTZ NOT NULL,
  UNIQUE (channel, external_id, issuer)
);
```

---

## 11. 限流防护（边缘安全）

| 层 | 措施 |
|---|---|
| 网络 | CDN + WAF (SQLi / XSS / Path Traversal / Bot 识别) |
| 接入 | Rate Limit（多维 §6.3）+ 协议级校验 |
| 账号 | 异地登录提醒 / 二次校验 / 设备指纹 |
| 敏感操作 | 验证码 / TOTP / 二次密码 |
| API Key | IP/Referer 白名单（可选）+ 异常用量告警 |
| 机器流量 | hCaptcha / Turnstile + 评分模型异常识别 |

详见 [L28](./28-security.md)。

---

## 12. MVP 范围

| 模块 | MVP 必做 | 后续 |
|---|---|---|
| Web 控制台 | 对话 + 知识库 + 工具 + 用户 / 计费 | 数据看板 / Agent 广场 |
| IM | 1 个（**飞书** 或 **钉钉**，看种子客户） | 其余 IM 跟随 |
| OpenAPI | REST + SSE + OpenAI 兼容外观 | WebSocket / Tasks |
| SDK | Python + Node | Java / Go / C# |
| Embed / Webhook / 防护 / i18n | iframe + 任务/HITL 回调 + WAF + 多维限流 + 中英 | Web Component / 白标 / 完整事件 / 风控 / 多语言 |

---

## 13. 真实坑（按优先级）

1. **流式输出体验 = 第一印象**：卡顿/闪烁/排版乱 = 立刻丢信任。端到端 P95 首字 < 1.5s。
2. **IM 协议变更频繁**：钉钉/飞书一年多次破坏更新；做协议适配层，保留 v1/v2 双版本灰度。
3. **企业内网代理 / 离线包**：客户 IT 限制外联，要支持代理转发、私有化部署、离线 SDK 包。
4. **i18n 别忘**：东南亚 / 欧美场景需要 i18n + 多时区 + 本地节假日（[L36](./36-i18n.md)）。
5. **H5 vs 原生**：H5 起步够；原生只在主战场（高频/离线/推送/录音）才上。
6. **OpenAPI 兼容 OpenAI**：客户改一行 `base_url` 切到你，**极大降低替换成本，必做**。
7. **白标 / 嵌入是大客户必问**：架构预留主题、子域名、隐藏品牌。
8. **Webhook 重试必做**：否则集成方崩；重试 + 死信 + 控制台手动重放三件套。
9. **IM 卡片协议**：飞书/钉钉/Slack/Teams 完全不同，必有"卡片 DSL"中间层。
10. **审核 / 上架周期**：上架审核 1-4 周，提前规划。

---

## 14. 待决议

- [ ] **首选 IM**：飞书 vs 钉钉 vs 企微（看 3 家种子客户分布）
- [ ] **是否兼容 OpenAI 协议**：默认倾向"是"，定 v0/v1 接口冻结时间
- [ ] **是否做白标**：对前 5 大客户开放品牌定制？影响多租户主题架构
- [ ] **移动端形态**：H5/PWA 起步 vs 投入原生 RN
- [ ] **Web 渲染框架**：Vercel AI SDK 6 vs Assistant-UI vs 自研（评估 2 周）
- [ ] **SDK 自动生成 vs 手写**：OpenAPI Generator 自动 + 关键 SDK 手写胶水
- [ ] **WebSocket 是否进 MVP**：取决于语音 ([L27](./27-voice.md)) 是否进 MVP
- [ ] **Embed 数据安全**：iframe cookie 隔离 / postMessage 鉴权

---

> **Changelog**
> v0.2 (2026-04-22)：重写。补全多端清单、SSE 事件矩阵、IM 协议差异表、OpenAPI 完整端点、身份映射模型、3 个真实场景流程、SQL 数据模型、Webhook 投递机制；与 L10/L12/L13/L14/L15/L17/L18/L22/L24/L25/L26/L27/L28/L29/L30/L33/L35/L36 双向链通。
> v0.1 (2026-04-22)：初稿。
