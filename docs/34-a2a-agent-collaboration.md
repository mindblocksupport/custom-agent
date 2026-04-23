# L34 · A2A 跨 Agent 协作协议

> 状态：**讨论中** · v0.1 · 2026-04-22 · 前瞻

## 0. 为什么独立成章
- **A2A** (Agent-to-Agent) 是 Google 推动的跨 vendor Agent 协作协议
- 2025-06 捐给 Linux Foundation；2026-04 v1.0 + Signed Agent Cards
- **150+ org** 加入；与 MCP 形成"工具 + 协作"双协议栈

## 1. 协议栈定位

```
┌────────────────────────────────┐
│ Application (业务逻辑)         │
├────────────────────────────────┤
│ A2A: Agent ↔ Agent 协作        │  ← Google 推动
├────────────────────────────────┤
│ MCP: Agent ↔ Tool/资源         │  ← Anthropic 推动
├────────────────────────────────┤
│ HTTP / JSON-RPC                │
└────────────────────────────────┘
```

## 2. A2A 核心概念

### 2.1 Agent Card
- 位置：`/.well-known/agent-card.json`
- 包含：能力 / 接口 / 认证 / 价格 / SLA
- v1.0 (2026-04) 加 **Signed Agent Cards** 防伪

### 2.2 Tasks
- 工作单元
- 异步 / 长时
- 状态机：pending → running → completed / failed
- v1.0 retry / expiry 语义

### 2.3 Discovery
- Agent registry（中心 / 分布式）
- 按能力查找
- 信任 / 评分

### 2.4 Authentication
- OAuth 2.1
- mTLS
- API key

## 3. 真实场景

### 3.1 跨企业协作
- 我们的销售 Agent → 客户的采购 Agent 询价
- 自动化 B2B 流程

### 3.2 内部多 Agent
- 不同部门 Agent 互调
- 法务 Agent 帮销售 Agent 审合同

### 3.3 行业 Agent 联邦
- 医疗：诊断 Agent + 药品 Agent + 保险 Agent
- 金融：风控 Agent + 客服 Agent

### 3.4 Agent Marketplace
- 类比 Slack App / GPT Store
- 跨 vendor 互通

## 4. MCP vs A2A

| 维度 | MCP | A2A |
|---|---|---|
| 范畴 | Agent ↔ Tool | Agent ↔ Agent |
| 主推 | Anthropic | Google |
| 状态 | 已成熟，普遍采用 | v1.0 (2026-04) 新 |
| 核心 | Tools / Resources / Prompts | Agent Card / Tasks |
| 适用 | 现在就用 | 前瞻准备 |

## 5. 安全挑战

- **Agent 假冒**：Signed Agent Card 缓解
- **跨 Agent prompt injection**：A 给 B 发恶意指令
- **数据泄露**：信息流跨 Agent 难追
- **责任界定**：A Agent 错了 B 跟着错

## 6. 我们的策略

**不立即做**（协议太新），但准备：
- Agent runtime 设计**留 A2A 接口**
- 未来作"Agent ID"管理
- 监控 A2A 生态成熟度

何时启动：
- A2A v1.0+ 有大客户实际部署 (12-18 月)
- 客户场景需要跨企业协作

## 7. 与现有架构融合

```
我们 Agent (LangGraph)
    ├─ 工具调用 → MCP servers
    └─ 协作 → A2A peer agents (其他公司)
```

## 8. 实施清单（前瞻）
- [ ] Agent ID 体系（每 Agent 唯一 + Signed）
- [ ] /.well-known/agent-card.json endpoint 支持
- [ ] Task 状态机扩展（兼容 A2A）
- [ ] Cross-agent audit log
- [ ] 信任 / 评分系统
- [ ] A2A v1.0+ 实际监控（市场动向）
