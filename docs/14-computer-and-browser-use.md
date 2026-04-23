# L14 · 电脑 / 浏览器 Use 扩展能力

> 状态：**讨论中** · v0.1 · 2026-04-22 · ★ 用户点名要求加入的章节

## 0. 这是什么 / 为什么必须做
让 Agent 能像人一样**用键盘鼠标操作电脑和浏览器**，处理**没有 API、只有 UI** 的系统——本质是**下一代 RPA**。

商业价值（按 ROI 排序）：
1. **遗留系统集成**（Citrix / AS/400 / 老 Win32 / 政务系统 / 老 ERP）—— **最大蛋糕**
2. RPA 替代（UiPath / 自动化任意 / 蓝棱镜）—— G2 2025: 60% RPA 部署 underperform，2026 都在向 agentic 转
3. 端到端 QA 测试
4. 跨系统流程（CRM → ERP 数据搬运）
5. 表单批量填写（保险 / 房贷 / KYC）
6. 网站门户数据抽取（供应商门户、政府申报）
7. 客服 co-pilot（驱动 agent 的 CRM）
8. 研究 / 抓取

> G2 2025: 57% 公司有生产 Agent；79% live；**40% 企业应用预计 2026 末嵌入 Agent**

## 1. 主要实现方案

### 1.1 闭源前沿
| 方案 | 发布 | OSWorld | 价格 |
|---|---|---|---|
| **Anthropic Claude Computer Use** | 2024-10 beta → GA, `computer_use_2025-05-01` tool | Sonnet 4.5 **61.4%**, Opus 4.7 **78.0%** | Opus $5/$25, Sonnet $3/$15, Haiku $1/$5 |
| **OpenAI Operator / CUA → ChatGPT Agent** | 2025-01-23, 2025-07-17 整合 | 38.1% (CUA), GPT-5.4 75.0% | - |
| **Google Gemini 2.5 Computer Use** | 2025-10-07 preview, **仅浏览器** | - | 通过 Gemini API / Vertex AI |

### 1.2 中国生态
- **Manus** (Butterfly Effect, 2025-03)：autonomous "general agent"，包 Claude 3.5 + 微调 Qwen，"Manus's Computer" 可观察 VM。**Meta 收购于 2025-12**；2026-03 桌面应用
- **AutoGLM / Open-AutoGLM** (Zhipu, 2025-12-08 开源)：9B VLM，**手机**端 Android use（WeChat/Taobao/Meituan/50+ app），ADB 通道
- **UI-TARS / UI-TARS-2** (ByteDance, Apache 风)：原生 GUI VLM。1.5 (2025-04) 在多个 GUI benchmark 击败 Operator + Claude 3.7。`bytedance/UI-TARS-desktop` 部署客户端

### 1.3 开源（生产可用）
| 项目 | License | 特点 | Stars |
|---|---|---|---|
| **Browser-Use** | MIT | Python 主流框架；可插 LLM；79k+ 星 | 79k |
| **Skyvern** | **AGPL-3.0** ⚠️ | vision-LLM + Playwright；no-code 工作流 | - |
| **Stagehand** (Browserbase) | MIT | TS/Py SDK；4 原语 act/extract/observe/agent；v3 iframe 提速 44% | - |
| **OmniParser V2** (Microsoft) | MIT | YOLO 图标 + Florence2 描述 + PaddleOCR；Screen Spot Pro 39.5% | - |
| **Agent-S / S2 / S3** (simular-ai) | - | 分层规划 + ACI；GPT-5 + UI-TARS-1.5-7B grounder = OSWorld baseline +9.37% | - |
| **WebVoyager** | - | 学界基准 | - |
| **ScreenAgent** | - | VNC 计划-行动-反思 | - |

## 2. 技术架构 (4 种观察模式)

| 模式 | Token / step | 强 | 弱 |
|---|---|---|---|
| **纯视觉**（screenshot → VLM → click） | ~50K | 通用（Citrix/Win32/Flash） | 慢、贵、小字体脆 |
| **DOM-only** (HTML / a11y tree) | ~4K | 便宜、确定、快 | canvas / iframe / WebGL 失效 |
| **Set-of-Mark**（截图 + 编号 overlay） | ~50K + DOM | 消歧"点元素 5"可靠 | overlay 每步重渲 |
| **Hybrid (DOM 优先 + 视觉 fallback)** | 变化 | **生产最佳** | 最复杂 |

→ 干净 a11y tree ~4K vs 等效截图 ~50K。20 步流程混合模式赢成本和延迟。**Stagehand / Browser-Use / Skyvern 都默认 hybrid**。

## 3. Benchmark 2026-04 现状

### OSWorld-Verified
| 模型 | 分数 |
|---|---|
| Claude Mythos Preview | 79.6% |
| Holo3-122B-A10B | 78.8% |
| Claude Opus 4.7 | 78.0% |
| GPT-5.4 | 75.0%（自报）—— 首次声称超人 |
| **人类基线** | **72.4%** |
→ 顶级模型聚 1.6 pt 内，benchmark **饱和**

### 其他
- WebArena: IBM CUGA 61.7%；人类 ~78.2%
- WebVoyager: Operator 87% / Browser-Use ~89%——**已被认为泄漏**（Google Search baseline 51%）
- **Online-Mind2Web** (300 任务 / 136 站点) ★ 更接近生产：Operator **61.3% 人评 / 71.8% WebJudge**；其他多数 28-30%

### 生产现实（METR）
- Claude 3.7 Sonnet: 50% 成功率任务 ≤ **59 min**；80% 可靠率 ≤ **15 min**
- 错误每步累积 → 5-10 步可靠，20-30 步带分支状态时挣扎
- **时间地平线每 ~7 月翻倍**

## 4. 企业架构（推荐）

3 种部署形态：

### 4.1 浏览器模式（推荐默认）
- 容器内 headless Chromium，冷启或热池
- <500ms 启动，~$0.001/min 计算
- 覆盖 ~80% 企业 web 任务
- → Browserbase / Hyperbrowser / Steel.dev 都卖这个

### 4.2 桌面模式
- Linux 桌面在 Firecracker microVM，Xvfb + WM + VNC
- ~125ms VM 启（Firecracker），<5MiB VMM 开销，最高 150 microVM/s/host
- 慢但 Win32 / Citrix / 桌面 ERP 必须

### 4.3 混合
- 浏览器 primary；按需起桌面 microVM

**关键参数**：流式截图通过 WebSocket，单 action 延迟目标 <2s（Sonnet 级 vision call ~800-1200ms + click ~200ms + DOM settle ~500ms）

## 5. 真实成本 & 延迟

- **每任务**：简单填表 ~$0.05-0.15；"订机票" 8-15 步 $0.30-2（Claude Opus + ~50K token/视觉步）
- **prompt cache** 对截图复用降输入成本 ~90% / 延迟 ~75%
- **每任务延迟**：5-30 min 复杂多步；Codex/Devin 级可数小时
- **生产失败率**：长任务 30-50% 是诚实区间。Operator Online-Mind2Web 61.3% 意味着 ~4/10 失败。METR 指数衰减是正确心理模型——**预算重试，不是零失败**

## 6. 安全挑战（最大未解问题）

**Indirect prompt injection 是核心**——UK NCSC + OpenAI 2025-12 公开声明"AI 浏览器场景**可能永远无法完全解决**"。

### 2025 已记录攻击
- **Brave on Comet** (2025-08-20)：网页内容喂 LLM 不分源 → 外泄 Gmail/Calendar
- **LayerX "CometJacking"** (2025-08-27)：URL 查询字符串作为 Agent 指令
- **Brave "unseeable prompt injections"**：截图近不可见文本被解读为命令
- **ChatGPT Atlas** (2025-10-22)：上线数小时内 Google Docs prompt injection demo

### 其他风险
- 数据外泄（自动确认对话框）
- 存储凭证滥用
- 多 tenant 跨 session 泄露
- 截图合规（PII/GDPR/HIPAA）

## 7. 合规 & Audit（必备）

- **完整屏幕录制**（mp4 或帧流）每 session，按策略保留
- 结构化 action log（时间戳 / 工具 / 目标 / 前后 DOM hash）
- **HITL 审批 gate** 标记的高危操作：付款、发送、删除、权限/角色变更
- 截图存储前 PII redaction 通过（OmniParser 风检测 + 已知敏感字段类型 box-blur）
- per-session 凭证 scoping（短期 token，不存密码）

## 8. 与我们栈集成

**最佳模式：Computer Use 作为主 Agent 可调工具**（不是平级 Agent）。Orchestrator 拆任务，调
```python
computer_use({
  "goal": "...",
  "starting_url": "...",
  "max_steps": 20,
  "allow_payment": false
})
```
返回结构化 trajectory + 最终状态。这把主推理循环留在我们已有 harness 里，HITL 注入直接。

Standalone-agent 模式只在完全自治长 RPA 替代（夜间批量）时才合理。

## 9. 推荐栈（务实 2026 版）

```
Vision-Action 模型:  Claude Sonnet 4.6 默认 (72.5% OSWorld)
                    Opus 4.7 升级 (78%)
                    用 native computer_use_2025-05-01 tool
执行 runtime:        Browser-Use (MIT) 包 Claude
                    79k 星 + MIT > Skyvern AGPL
屏幕解析 fallback:   OmniParser V2 (MIT) 配 Claude vision
                    OmniTool 预制 Win11 VM 参考镜像
沙箱:                Firecracker microVM per session
                    deny-all egress + per-tenant 域 allowlist
                    jailer 启
                    暖 Chromium 池亚秒启
观察:                hybrid (a11y tree 优先，截图+SoM fallback)
                    每步成本降 ~10×
Audit:               mp4 + JSON action log + 写入前 PII redaction
HITL:                action 分类器（regex URL/element + LLM 不可逆判断）
                    付款 / 发送 / 删除前
```

## 10. 真实企业产品参考
- **Autotab** (YC, F500 部署)：录-放 + LLM，本地浏览器 SSO
- **Browserbase**：serverless Chromium 基建；ships Stagehand (MIT) + Open Operator template
- **Hyperbrowser** (YC)：stealth + concurrency 远程浏览器 API
- **Scrapybara**：远程浏览器 for 抓取/Agent
- **Steel.dev**：企业级，开源组件，公开 AI Agent Benchmark Index
- **UiPath / Automation Anywhere**：incumbents 转型（UiPath Agent Builder 2025-04, AA Process Reasoning Engine）
- **Multi-on / Reflect** —— 消费侧

## 11. 模块架构图

```
                    ┌────────────────────────────────┐
                    │  主 Agent（我们 orchestrator）  │
                    └──────────────┬─────────────────┘
                                   │ tool: computer_use(goal, url, policy)
                    ┌──────────────▼─────────────────┐
                    │  Computer-Use Service (gRPC)   │
                    │  • 策略检查 / HITL gate         │
                    │  • session 路由                 │
                    │  • cost & step-budget guard    │
                    └──────┬───────────────┬─────────┘
                           │               │
              ┌────────────▼──┐      ┌─────▼──────────┐
              │ 浏览器池      │      │ 桌面池         │
              │ (Firecracker  │      │ (Firecracker   │
              │  + headless   │      │  + Xvfb +      │
              │  Chromium)    │      │  Win11/Linux)  │
              └────────┬──────┘      └──────┬─────────┘
                       │                    │
                ┌──────▼────────────────────▼──────┐
                │  per-session Agent loop          │
                │  1. observe: a11y tree           │
                │  2. 模糊时: screenshot + SoM     │
                │  3. plan: Claude Sonnet 4.6      │
                │     (重试时升 Opus 4.7)           │
                │  4. act: Playwright / pyautogui  │
                │  5. verify: DOM hash + screenshot│
                │  6. record: mp4 + jsonl          │
                └──────┬───────────────────────────┘
                       │
                ┌──────▼──────────┐    ┌──────────────┐
                │ Audit store     │    │ HITL queue   │
                │ (mp4, jsonl,    │    │ (审批 UI     │
                │  PII-redacted)  │    │  for 高危)   │
                └─────────────────┘    └──────────────┘
```

## 12. MVP 范围
- 浏览器池（Firecracker + Chromium）
- Browser-Use 包 Claude Sonnet 4.6 + native computer use
- 1 个真实场景（如填政府表单）
- mp4 录屏 + jsonl action log
- 简单 HITL（付款 / 提交按钮 → 推送审批）

## 13. 真实坑总结
1. **OSWorld 等 benchmark 已饱和**，Online-Mind2Web 是更诚实的预期
2. **生产失败率 30-50%**——架构必须假设失败，重试 + HITL 兜底
3. **prompt injection 没有银弹**，假设网页内容敌对
4. **Markdown link / 自动取图必须加固**
5. **截图含 PII**——存储前必须脱敏
6. **凭证 scoping**：短期 token 给单 session，不存密码
7. **Anthropic computer_use_2025-05-01 是最好测过的 API**——别自己造
8. **Skyvern AGPL-3.0** —— 嵌入商业产品有许可陷阱，慎用
9. **OmniParser V2 是最好开源屏幕解析**——legacy 桌面必备
10. **Firecracker > gVisor > Docker** 用于 untrusted Agent 代码
