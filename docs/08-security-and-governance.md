# L8 · 安全治理 (Security & Governance)

> 状态：**讨论中** · 版本 v0.2 重写版 · 2026-04-22
>
> 上一版（v0.1）把 L8 写成了"安全大全"，把幻觉、合规、信创、HITL、多租户、Guardrails 全塞进来，导致每个主题都浅而散。v0.2 把 L8 收敛为 **AuthN/Z + Audit + Content Safety + 多租户编排** 这一层，深入展开；其它专题指向对应文档。

---

## 1. 本层职责

L8 是 **企业 Agent 平台的"准入证"** —— 没有这一层，所有客户的安全采购清单都过不去；做完这一层，业务方才"敢"把 Agent 接到 ERP / 工单 / 财务上。

### 1.1 五维安全模型

```
┌──────────────────────────────────────────────────┐
│  1. 身份  (Who)      —— AuthN / AuthZ            │
│  2. 数据  (What)     —— 加密 / 脱敏 / 不出域     │
│  3. 行为  (Action)   —— 审计 / 红线 / HITL 衔接  │
│  4. 内容  (Content)  —— 注入防御 / 输出审查      │
│  5. 隔离  (Tenant)   —— 多租户编排               │
└──────────────────────────────────────────────────┘
```

### 1.2 与相邻层的边界（避免重复）

| 主题 | 在哪里展开 | L8 在这里只做 |
|---|---|---|
| 幻觉控制（事实性、引用） | [L18 · 幻觉与可信度](./18-hallucination-and-trust.md) | 治理流程钩子（输出审查、置信门控） |
| HITL 审批门 | [L22 · 人机协同](./22-human-in-the-loop.md) | 高危操作触发 HITL 的策略 |
| 多租户隔离架构（DB / 向量 / 配额） | [L24 · 多租户](./24-multi-tenancy.md) | 跨层编排 + tenant_id 强制注入 |
| 合规法规清单（PIPL / DSL / 备案 / 出境） | [L25 · 合规](./25-compliance.md) | 落地实施（加密 / 审计 / 脱敏 / 删除权） |
| 信创 / 国密 / 等保 | [L36 · 信创与国密](./36-xinchuang-and-gm.md) | 在加密 / KMS 章节引用 |
| Guardrails 框架编排 | [L16 · Guardrails](./16-guardrails.md) | 编排时序 + 调用契约 |
| 真实安全事故案例（EchoLeak / Slack AI 等） | [L20 · 安全事故复盘](./20-security-incidents.md) | 防御措施引用案例 |

---

## 2. 身份认证（AuthN）

### 2.1 协议矩阵

| 协议 | 适用 | 备注 |
|---|---|---|
| **SAML 2.0** | 传统大企业 / 政企 | XML 重，但 IdP 普及度最高 |
| **OIDC** | 现代 SaaS / 跨厂商 | 推荐首选，JSON / JWT 友好 |
| **OAuth 2.0** | 第三方授权 / API 委托 | Authorization Code + PKCE |
| **LDAP / AD** | 政企 / 内网 | 老协议，必备适配 |
| **CAS** | 高校 / 部分国企 | 偶现，需要兼容 |

### 2.2 IdP 集成清单

| IdP | 协议 | 重点坑 |
|---|---|---|
| 钉钉 | OAuth 2.0 + 自有 API | 扫码登录是用户预期，corpId/agentId 一套；接口 QPS 限制 |
| 飞书 | OIDC + 自有 API | tenant_key 和 user_open_id 区分；H5 vs 桌面回调不同 |
| 企业微信 | OAuth 2.0 + 自有 API | 内外用户区分；外部联系人单独鉴权 |
| Azure AD / Entra ID | SAML / OIDC | tenant_id 多个；条件访问策略可能阻塞机器人 |
| Okta | SAML / OIDC | 标准好接；SCIM 同步用户/组 |
| LDAP / OpenLDAP / AD | LDAP v3 | DN 结构客户千差万别；密码策略 / 锁定策略需读取 |
| CAS 3.x | SAML-like | 高校常见；ticket 一次性，时钟敏感 |

### 2.3 中国 IdP 真实坑

- **钉钉/飞书/企微的"用户唯一标识"在不同接口里是不同字段** —— 必须在适配层统一映射 `external_id`
- IdP 之间用户重叠（同一员工有钉钉账号也有 AD 账号）—— 需要 **身份合并策略**（admin 显式合并，不要自动猜）
- 私有化部署不能联外网 → 钉钉/飞书的"在线扫码"走不通 → 必须支持降级到 LDAP/CAS
- "扫码登录"的 callback 在反向代理后域名不对 → 要做 X-Forwarded-Host 处理

### 2.4 MFA / Session / API Key

| 项 | 要点 |
|---|---|
| MFA | OTP（TOTP）、短信、硬件 token（Yubikey / 国密 USB Key） |
| Session | 超时（默认 8h）、强制下线、并发会话上限、IP 绑定可选 |
| API Key | 服务间 / 开发者；必须支持 **轮换 + 作用域限定 + 速率配额** |
| Token | JWT 推荐，含 tenant_id / role 声明；refresh token 可撤销 |
| 设备指纹 | 高风险租户开启；异常设备触发二次认证 |

---

## 3. 权限授权（AuthZ）

### 3.1 RBAC（基础）

```
User ─┬─> Role ─┬─> Permission ─┬─> Resource
      │         │                │
      └ N:N ────┘                └─ {action, scope, condition}
```

典型角色：`super_admin / tenant_admin / developer / operator / user / auditor / read_only`

### 3.2 ABAC（精细）

适用：跨部门、敏感数据、动态规则、按时间段开放等

```rego
# OPA 策略示例
allow if {
    input.user.dept == input.resource.dept
    input.action in {"read", "list"}
}
allow if {
    input.user.level >= 5
    input.resource.classification in {"public", "internal"}
    time.now_ns() < input.user.access_expires_at
}
```

### 3.3 工具级权限（与 [L4 · 工具系统](./04-tool-system.md) 联动）

| 维度 | 说明 |
|---|---|
| **可见性** | 用户在 Agent 工具列表中能否看到（影响 LLM 的 tool catalog） |
| **可调用** | 看到不一定能调用，二次校验在 tool dispatcher |
| **参数约束** | 如 SQL 工具仅允许 `SELECT`、仅允许指定库；HTTP 工具仅允许白名单域名 |
| **副作用门控** | 写操作 / 删除 / 转账 → 强制 HITL（[L22](./22-human-in-the-loop.md)） |
| **配额** | 单工具 QPS / 日上限 / 单次成本上限 |

### 3.4 数据级权限（贯穿到 RAG）

这是 Agent 平台 **最容易出事** 的权限点。普通 RBAC 管不到"知识库里的某一段文字 user A 能不能看"。

实现要点：

1. **行级**：DB / 向量库每条记录有 `acl_subjects` 字段（user/role/dept 列表）
2. **字段级**：HR 的 `salary` 字段对普通员工返回 `***`
3. **检索时强制 filter**（不是检索后过滤）：
   ```sql
   SELECT ... FROM kb_chunks
   WHERE tenant_id = :tid
     AND (acl_subjects && ARRAY[:user_subjects])
     AND embedding <#> :query_vec < 0.3
   ```
4. **召回后二次校验**：检索引擎可能因为索引漂移漏 filter，业务层再过一道
5. **引用展示前过滤**：LLM 引用的原文，输出层再次按 ACL 截断

→ 详见 [L3 · 检索与知识库](./03-retrieval-and-knowledge.md) 的"权限感知检索"小节，与 [L24](./24-multi-tenancy.md) 的 tenant_id 强制注入合并实现。

### 3.5 工程实现选型

| 工具 | 模型 | 适用 |
|---|---|---|
| **Open Policy Agent (OPA)** | Rego DSL，决策与代码解耦 | 复杂 ABAC、跨服务统一策略 |
| **Casbin** | 多模型（RBAC/ABAC/RESTful） | 中小项目，Go/Python/Java 库齐全 |
| **Cerbos** | YAML 策略 + gRPC | 云原生 / K8s 友好 |
| **自研** | 业务 DSL | 行业深度定制（如金融的"四眼原则"） |

推荐：**OPA + 业务 DSL 包装**。OPA 做决策，业务侧用 DSL 表达"这个操作要走 HITL"等元规则。

---

## 4. 数据安全（实施层；法规清单见 [L25](./25-compliance.md)）

### 4.1 加密矩阵

| 位置 | 标准 | 国密对应（[L36](./36-xinchuang-and-gm.md)） |
|---|---|---|
| 传输 | TLS 1.3 | GMSSL（SM2 证书 + SM4 对称） |
| 静态（盘 / DB / 对象存储） | AES-256-GCM | SM4-GCM |
| 字段级（手机号 / 身份证 / 卡号） | AES-256-GCM + KMS | SM4 + 国密 KMS |
| 密码 | Argon2id / bcrypt | 同上 + SM3 摘要 |
| 签名 | Ed25519 / RSA-PSS | SM2 |
| 摘要 | SHA-256 | SM3 |

### 4.2 密钥管理

| 场景 | 方案 |
|---|---|
| 公有云 | AWS KMS / 阿里云 KMS / 华为 DEW |
| 私有化 | HashiCorp Vault（推荐）/ 国密硬件 HSM |
| 政企 | 国密 HSM（江南天安、三未信安、卫士通），通过 GMSSF 接口 |

KMS 必备能力：**密钥分级（KEK + DEK）、轮换策略、审计日志、应用 RBAC、Envelope Encryption**。

### 4.3 PII 检测与脱敏

> 工具选型详见 [L16 · Guardrails](./16-guardrails.md) 的 Presidio 章节；这里讲集成时机与中文坑。

| 时机 | 处理 |
|---|---|
| **入站** | 用户输入 → Presidio 识别 → 占位符替换（`<PHONE_1>`）→ 给 LLM；映射表存于 session 上下文，**不入 trace** |
| **出站** | LLM 输出 → 反向回填（视权限）/ 二次脱敏；引用片段也要过 |
| **存储** | trace / log / 对话历史落库前再过一遍，作为兜底 |
| **检索** | 向量化前的原文要存脱敏 / 非脱敏两份，检索按权限选 |

**中文 PII 识别器自定义**（Presidio 默认不带）：身份证（含校验位）、统一社会信用代码、手机号（13/14/15/16/17/18/19 段）、银行卡（Luhn 校验）、车牌（含新能源）、护照、户口本、住址（行政区划匹配 + LLM 辅助）。

### 4.4 数据不出域（→ [L25](./25-compliance.md)）

L8 这里只列实施清单：
- 模型本地部署（[L36](./36-xinchuang-and-gm.md)）
- 向量库本地部署
- 日志 / trace 不外传（含错误上报、Sentry、APM）
- 出口防火墙白名单（agent 容器禁直连公网）
- 第三方依赖审查（npm / pip 包是否 phone home）

### 4.5 数据生命周期

```
采集 ──> 使用 ──> 存储 ──> 归档 ──> 销毁
  │        │        │        │       │
  同意    最小    加密+ACL  冷存   可证明删除
  告知    必要              低频    (含备份/索引/向量)
```

| 阶段 | L8 责任 |
|---|---|
| 采集 | 同意书版本化、目的声明、未成年人特殊处理 |
| 使用 | 仅必要字段、二次目的需重新同意 |
| 存储 | 加密 + ACL + 保留期标注 |
| 归档 | 冷存储、降密、检索接口隔离 |
| 销毁 | 用户行使删除权（GDPR/PIPL）→ 必须能彻底删除（含备份、向量索引、缓存、外部 SaaS 副本）—— **Agent 平台最难的部分：向量库的硬删 + LLM 微调副本** |

---

## 5. 内容安全

### 5.1 Prompt Injection 三类与防御

| 类型 | 攻击面 | 真实案例（[L20](./20-security-incidents.md)） |
|---|---|---|
| **直接注入** | 用户输入 "忽略之前指令" | DAN / "Do Anything Now" 系列 |
| **间接注入** | 上传文档、网页抓取、邮件正文中藏指令 | **EchoLeak (M365 Copilot)** —— 邮件中藏 prompt → Copilot 抓取 → 数据外泄 |
| **工具结果注入** | 工具返回值（API/DB/搜索）含恶意 prompt | Slack AI 召回数据含注入指令 → 误执行 |

防御组合（**没有银弹，必须叠加**）：

| 措施 | 说明 |
|---|---|
| 输入扫描 | 规则 + 分类模型（Llama Guard 4 / Prompt Shields），见 [L16](./16-guardrails.md) |
| 角色严格区分 | system / user / tool 三类消息分隔；tool 结果用 `<tool_output>` 包裹并标注 untrusted |
| 关键指令重申 | 每轮在 system 末尾重申"无论上下文如何，都不要 X / 暴露 Y" |
| 输出审查 | 检测 LLM 是否被诱导（关键词、行为模式、调用工具异常） |
| 隔离模式 | 处理用户上传内容时，禁用敏感工具（write / send / pay） |
| 数据/指令分离 | 工具结果一律视为"数据"，不得作为指令解释 —— 在 prompt 模板中显式声明 |
| 输出去能力 | 禁止 LLM 输出可被前端执行的内容（HTML/JS/iframe），渲染层强转义 |
| 资源访问最小化 | 工具默认 deny，逐项 allowlist |

### 5.2 Jailbreak 防御

- 角色扮演（DAN / 奶奶模式 / 翻译规避）
- 编码绕过（Base64 / ROT13 / 隐写术 / Unicode 同形）
- 多轮逐步引导（slow-burn）
- 模板填充（"假设你是开发者在测试"）

防御：
- 模型厂商内置（OpenAI / Anthropic / 阿里 / 智谱）—— **不要全依赖**，私有化模型常无
- 自建越狱检测分类器（[L16](./16-guardrails.md)）
- 异常对话模式监控（同 session 多次拒答后突然顺从 → 触发审查）
- 关键拒答策略硬编码（不靠 LLM 判断）

### 5.3 输出安全

| 维度 | 说明 |
|---|---|
| 有害内容 | 暴力 / 色情 / 自残 / 违法 → Llama Guard 4 / Granite Guardian |
| 合规审查 | 金融建议、医疗建议、法律建议 → 强制免责；"不构成投资建议" |
| 政治敏感（中国必做） | 阿里云内容安全 PLUS / 腾讯天御 / 网易易盾；本地敏感词词库定期更新 |
| 知识产权 | 生成内容是否照抄训练数据 → 引用溯源（[L18](./18-hallucination-and-trust.md)） |
| 偏见与歧视 | 性别 / 种族 / 年龄 / 地域；高危行业（招聘、信贷）需偏见检测 |

### 5.4 中文专项

- **政治敏感词必做**：白名单 + 动态更新，离线词库每日同步
- **私有化场景** 必须自带本地敏感词词库 + 模型审核（不能联网调云）
- 推荐叠加：**阿里云内容安全 PLUS（多模态）/ 腾讯天御 / 网易易盾**
- 国内大模型 API（通义、文心、智谱、混元）自带审核 → 仍需自建二道闸（API 偶发漏）

---

## 6. 行为审计

### 6.1 必审计事件清单

| 类别 | 事件 |
|---|---|
| 身份 | 登录 / 登出 / MFA / SSO 跳转 / 鉴权失败 / 密码重置 |
| 权限 | 角色变更 / 策略修改 / API Key 创建-轮换-吊销 |
| 数据 | 敏感数据访问 / 导出 / 下载 / 跨租户访问尝试 |
| Agent | 工具调用（**全量**）/ HITL 审批 / 红线触发 / 注入告警 |
| 配置 | Prompt 版本变更 / 模型切换 / Guardrails 策略调整 / 工具上下架 |
| 管理 | 管理员所有操作 / 跨租户切换 / 审计日志查询 |

### 6.2 不可篡改

| 方案 | 适用 |
|---|---|
| **WORM 存储** | S3 Object Lock / 阿里 OSS WORM / Azure Immutable Blob —— 推荐首选 |
| **Hash Chain** | 每条 log 含上一条 hash（轻量、易实现、常用兜底） |
| **区块链锚定** | 高合规场景（医疗 / 金融）—— 把每日 hash 摘要上链 |
| **TSA 时间戳** | 国密 TSA 时间戳服务（政企客户经常要求） |
| **多副本异地** | 与生产隔离的独立账号 / 区域 |

### 6.3 完整性（六要素）

```
{
  "who":    {user_id, tenant_id, role, ip, device_fp, session_id},
  "when":   {ts_utc, ts_local, monotonic_seq},
  "where":  {service, region, k8s_pod, app_version},
  "what":   {action, resource_type, resource_id, params_redacted},
  "why":    {trigger, request_id, parent_span, business_context},
  "result": {status, error_code, latency_ms, side_effects[]}
}
```

### 6.4 保留期

| 行业 | 最低 |
|---|---|
| 等保三级 | ≥ 6 月 |
| 金融（人行） | 5 年 |
| 医疗 | 5–15 年 |
| 通信 | 1 年（含元数据） |
| GDPR/PIPL（操作日志） | 与个人数据生命周期匹配 |

### 6.5 审计专用接口

- 独立角色 `auditor`，**只读**审计 / **不能**改业务数据
- 查询 API 与业务 API 物理隔离
- 导出格式：CSV / PDF（带签章和时间戳）/ 国密签章可选
- 自带 Web UI（很多客户的合规人员不会查 ES）

---

## 7. 多租户隔离编排（→ [L24](./24-multi-tenancy.md)）

L8 不重复隔离架构，只列 **跨层强制项**：

| 层 | L8 强制 |
|---|---|
| API Gateway | 解析 token → 注入 `X-Tenant-Id` header；下游不信任客户端 tenant 字段 |
| 服务层 | 每个 request 有 tenant context；ORM 拦截器强制 where tenant_id |
| RAG 检索 | tenant_id 是必传 filter，缺失即 reject |
| 模型调用 | tenant 级 LLM 配额；缓存 key 含 tenant_id |
| Trace / Log | tenant_id 落字段，便于审计与导出 |
| 缓存 | Redis key 含 tenant_id 前缀；防 key 碰撞 |

**真实坑**：见 [L24](./24-multi-tenancy.md) 的"SQL 漏写 WHERE / Redis key 跨租户 / 向量库 namespace 错配"三大事故。

---

## 8. Guardrails 编排（→ [L16](./16-guardrails.md)）

L8 是 Guardrails 的"调用方"，定义 **时序与契约**。L16 讲框架与产品对比。

```
┌─ User Input ────────────────────────────────────────────────────┐
│                                                                 │
│  [Input Scan]                                                   │
│    ├─ Presidio        → PII 识别 + 占位符化                     │
│    ├─ Llama Guard 4   → 有害 / 越狱 / 注入分类                  │
│    ├─ Prompt Shields  → MS 的 jailbreak/indirect-injection 检测 │
│    └─ 阿里/腾讯       → 中文政治敏感（中国部署必走）            │
│                                                                 │
│         ↓ block / sanitize / pass                               │
│                                                                 │
│  [Orchestrator: NeMo Guardrails]                                │
│    ├─ 对话流约束 (Colang)                                       │
│    ├─ 工具调用前置检查                                          │
│    └─ HITL 触发点                                               │
│                                                                 │
│         ↓                                                       │
│                                                                 │
│  [LLM + Tool Loop]                                              │
│    ├─ Granite Guardian → RAG groundedness 实时校验              │
│    └─ Tool result → 二次过 PII / 注入扫描                       │
│                                                                 │
│         ↓                                                       │
│                                                                 │
│  [Output Scan]                                                  │
│    ├─ Presidio        → 出站脱敏                                │
│    ├─ Granite/Llama   → 有害 / 合规                             │
│    ├─ Guardrails AI   → JSON Schema / 结构化校验                │
│    └─ 阿里/腾讯       → 政治敏感终审                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

调用契约（统一接口，方便切换厂商）：

```python
class Guard(Protocol):
    def check(self, payload: GuardPayload) -> GuardResult: ...

# GuardResult: {action: pass|sanitize|block|hitl, reasons[], evidence}
```

---

## 9. 可信 AI 治理

| 维度 | 落地 |
|---|---|
| **可解释** | 思考链可见（按角色脱敏后）；工具调用链路透明；决策依据展示 |
| **引用溯源** | 每条结论关联 chunk_id / source_url；前端可回跳 → 详见 [L18](./18-hallucination-and-trust.md) |
| **公平性** | 偏见检测（性别/种族/年龄/地域）；高危行业（招聘、信贷、保险）专项评估 |
| **Prompt 治理** | Prompt 版本化（Git）+ 评审（PR）+ A/B + 灰度（[L31](./31-experimentation.md)） |
| **模型变更评估** | 上新模型走评估集 + 回归 + 影响面公告 + 回滚预案 |
| **灰度发布** | 按租户 / 用户 / 流量百分比；影响面观察 ≥ 7 天再放量 |

---

## 10. 红线机制

### 10.1 永不能做（硬编码 deny，不靠 LLM 判断）

- 直接执行任意 SQL / Shell / Python（必须经审批工具）
- 调用财务转账 / 资金结算 API
- 删除任何用户数据（含批量更新到删除等价的 update）
- 修改 IAM / 权限 / 审计配置
- 跨租户读写
- 输出明文密码 / token / 私钥

### 10.2 经审批可做（HITL → [L22](./22-human-in-the-loop.md)）

- 写操作（DB update / 工单 create / 邮件 send）
- 单次成本 / 调用量超阈值
- 涉及外部第三方 API（合同、采购）
- 触及敏感数据集
- 模型自评置信 < 阈值

红线规则与 HITL 策略统一存于 **Policy Repo**，热加载，变更走审批 + 审计。

---

## 11. 红蓝对抗

| 项 | 频率 | 说明 |
|---|---|---|
| Prompt 注入测试集 | 每周回归 + 每发版 | 维护 ≥ 500 条样本（含中英、多模态） |
| 越权访问测试 | 每发版 | 跨租户、跨角色、跨字段 |
| 数据泄漏演练 | 季度 | 模拟内鬼、模拟外部攻击 |
| Tool 滥用 | 每发版 | 工具组合攻击（如 search→exfil） |
| 红队驻场 | 半年 / 大版本 | 雇专业 AI 红队（HiddenLayer / Robust Intelligence / 国内安恒、奇安信） |
| Bug Bounty | 持续 | SRC 公开通道（按严重度赏金） |

---

## 12. 漏洞响应（SRC）

```
报告 → 分级（P0–P3）→ 响应 → 修复 → 验证 → 复盘 → 公告
 │       │              │      │      │      │      │
 公开   P0=2h          应急    补丁   回归   ROOT   披露
 邮箱   P1=24h         小组    发布   测试   分析   策略
        P2=7d
        P3=30d
```

- CVE 跟踪：依赖每日扫描（Snyk / Trivy / 阿里云依赖检测）
- 应急预案：模型 API 中毒 / 厂商失约 / 关键 CVE 0-day → 写成 runbook
- 演练：每季度桌面 + 每年实战

---

## 13. 第三方依赖

| 项 | 工具 |
|---|---|
| **SBOM** | Syft / CycloneDX，每个交付物附带 |
| **依赖扫描** | Snyk / Trivy / Grype / Dependabot / GitHub Advanced Security |
| **License 合规** | FOSSA / ScanCode（GPL/AGPL 警告） |
| **模型供应商资质** | 备案号 / 合规证明 / 数据来源声明 / 安全审计报告 |
| **MCP / 第三方工具** | 沙箱执行 + 网络白名单 + 调用审计（[L4](./04-tool-system.md)） |

---

## 14. MVP 范围

| 模块 | MVP 必做 | 后置 |
|---|---|---|
| AuthN | OIDC + 钉钉/飞书登录 + Session + API Key | SAML / LDAP / 国密 USB Key |
| AuthZ | RBAC + 工具级权限 | 完整 ABAC / OPA |
| 数据级权限 | tenant_id 强制 + 行级 ACL | 字段级动态脱敏 |
| 加密 | TLS 1.3 + 静态 AES-256 + KMS | 国密 + HSM |
| PII | Presidio 入站/出站 + 中文识别器 | 多模态 PII |
| 内容安全 | Llama Guard 4 + 阿里云内容安全 + Prompt 注入基础防御 | NeMo 全流程编排 |
| 审计 | 全量事件 + WORM + Hash Chain | 区块链 / TSA 时间戳 |
| 多租户 | 共享 DB + tenant_id 强制 + 配额 | 独立 schema / 独立部署 |
| 红线 | 硬编码 deny 列表 + 写操作 HITL | 动态红线策略 |
| 等保 | 自查清单 | 测评 / 备案 |

---

## 15. 真实坑（→ [L20](./20-security-incidents.md) 案例）

1. **安全是后补不动的** —— Day 1 不设计，将来重构成本是新建的 5 倍
2. **合规清单看似 200 项，实际 5–10 项致命** —— 数据出境 / 算法备案 / 等保 / 个保影响评估 / 删除权
3. **政企客户安全检查表 100+** —— 销售要熟、售前要懂；做"标准应答库"减少响应时间
4. **私有化交付** —— 客户雇第三方驻场扫描（启明星辰 / 绿盟 / 安恒），漏洞百出 → 紧急加班；提前自扫
5. **国密 + 信创 + 等保是套装** —— 政府客户必谈，单独支持任一都不够（[L36](./36-xinchuang-and-gm.md)）
6. **Prompt 注入越来越严重** —— 模型越强越危险；EchoLeak 之后 M365 Copilot 全行业重审
7. **审计日志是诉讼证据** —— 法律级别的不可篡改 + 时间戳 + 多副本，不能图省事
8. **租户隔离一次失误 = 公司声誉** —— 一个 tenant_id 漏写引爆全国公关危机；测试必须覆盖
9. **删除权很难** —— 向量索引、LLM 微调副本、缓存、外部 SaaS 副本；要专门的"被遗忘权"工程
10. **Guardrails 不是装上就完事** —— 每条规则都要有 TP/FP/FN 监控（[L31](./31-experimentation.md)），否则用户体验会被误杀拖垮
11. **MFA 救命** —— 拿到 token 不等于全部失守，敏感操作再 MFA 一次
12. **模型供应商也是攻击面** —— SDK / API 端点 / 下载的权重都要校验签名

---

## 16. 待决议

- [ ] 国密 / 信创支持优先级（决定能否进政企，详 [L36](./36-xinchuang-and-gm.md)）
- [ ] 私有化部署的安全交付包（含等保自查 / SBOM / 渗透报告 / 应急预案 模板化）
- [ ] 是否申请 等保三级 / SOC2 Type II / ISO27001（详 [L25](./25-compliance.md)）
- [ ] 多租户隔离默认级别（共享 DB vs 独立 schema 决定整个架构，详 [L24](./24-multi-tenancy.md)）
- [ ] 内容安全：自建 vs 云厂商（成本 / 效果 / 数据出域三难）
- [ ] OPA vs Casbin vs 自研（决策延迟 / 维护成本 / 业务表达力）
- [ ] 审计日志后端：ES / ClickHouse / 对象存储 + 索引（成本与查询性能取舍）
- [ ] 红队预算与节奏（自建 vs 外包）

---

## 17. 关联文档

- [L3 · 检索与知识库](./03-retrieval-and-knowledge.md) —— 权限感知检索
- [L4 · 工具系统](./04-tool-system.md) —— 工具级权限 + 沙箱
- [L10 · 可观测性](./10-observability.md) —— 审计与可观测的边界
- [L16 · Guardrails](./16-guardrails.md) —— 框架对比与编排细节
- [L18 · 幻觉与可信度](./18-hallucination-and-trust.md) —— 引用溯源 / 事实性
- [L20 · 安全事故复盘](./20-security-incidents.md) —— EchoLeak / Slack AI 等案例
- [L22 · 人机协同（HITL）](./22-human-in-the-loop.md) —— 高危操作审批
- [L24 · 多租户](./24-multi-tenancy.md) —— 隔离架构
- [L25 · 合规](./25-compliance.md) —— 法规清单 / 数据出境 / 国内法规
- [L31 · 实验与灰度](./31-experimentation.md) —— Guardrails 的 TP/FP 监控、模型变更评估
- [L36 · 信创与国密](./36-xinchuang-and-gm.md) —— SM2/3/4 / 国密 HSM / 信创栈
