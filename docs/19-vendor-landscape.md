# L19 · 企业 Agent 竞品 / 厂商 / 市场全景

> 状态：**讨论中** · v0.1 · 2026-04-22 · 选竞品借鉴 + 找差异化

## 1. 横向 / 知识平台

| 厂商 | 估值 / ARR | 定位 | 可借鉴 |
|---|---|---|---|
| **Glean** | **$200M+ ARR** (Dec 2025), $7.2B valuation | 企业搜索 + Agent；100+ connector；permission-aware retrieval；20T tokens/yr | ★★★ ACL retrieval 模式必学 |
| **Writer** | $200M Series C (Nov 2024), $1.9B | 自有 Palmyra X5 (1M ctx) + graph RAG + 无代码 Agent builder + AI HQ；customer: Accenture/Vanguard/Uber | 模型 + Agent 垂直整合 |
| **Cohere** | $150-200M ARR | **North** (Aug 2025 GA): VPC / 离网友好；customer: RBC/Bell/LG/Dell/Palantir | 主权 / 监管市场专攻 |
| **AI21** | - | **Maestro**: 多路径并行 + 验证；2025-12 Bedrock GA | 验证执行模式 |
| **IBM watsonx Orchestrate** | - | 80+ 企业 app；HR/Procurement/Finance Domain Agent on Granite | "Agent 系统记录"概念 |
| **Microsoft Copilot Studio + Azure AI Foundry** | M365 几千万座位 | low-code (Studio) + pro-code (Foundry); 2025 Build 加多 Agent + M365 Copilot Tuning | 巨头分发力 |
| **Google Vertex AI Agent Builder** | - | ADK 7M+ download + Agent Engine + Garden + A2A | 开框架 + 托管 runtime 模式 |
| **AWS Bedrock AgentCore** | 2025-10 GA | 模块化: Runtime/Memory/Gateway/Identity/Observability；framework + 模型 agnostic | 中性基板 |
| **Databricks Mosaic AI / Agent Bricks** | beta 2025 | 描述任务 → 自动合成 data + eval + 优化；Lakehouse + Unity Catalog 治理 | data-platform native |

## 2. 客服

| 厂商 | 估值 / ARR | 模式 | 可借鉴 |
|---|---|---|---|
| **Sierra** (Bret Taylor) | **$10B 估值, $100M ARR (21 月)** | outcome-based 计费 per resolved；customer: ADT/Cigna/SiriusXM/Discord/Ramp/Rivian/SoFi | ★★★★★ outcome 计费 + Agent OS + simulation |
| **Decagon** | **Series C $131M @ $1.5B** (Jun 2025), Series D ~$250M @ $4-5B (Jan 2026) | per-conversation 或 per-resolution；customer: Notion/Duolingo/Rippling/Bilt | 高增长 SaaS 攻 |
| **Ada** | $200M+ raised @ $1.2B (2021) | pre-LLM 玩家转 agentic | 转型样本 |
| **Forethought** | **Zendesk 2026-03 收购** | 处理 1B+ 交互/月；customer: Upwork/Grammarly/Airtable/Datadog | 被收购信号——incumbent 买入 |
| **Cresta** | **$125M Series D** (late 2024), $270M+ total | **agent assist for 人 + virtual agent**；4× ARR 2 年 | 顶绩效话术 codify 模式 ★ |
| **Ultimate AI** | Zendesk 2024 收购 | 欧多语客服 | - |

## 3. 编程

| 厂商 | 估值 / ARR | 模式 | 可借鉴 |
|---|---|---|---|
| **Cursor** (Anysphere) | **$2B ARR (Feb 2026)**, $50B 估值 | $20 Pro / $40 Business / $200 Ultra；70% F1000；60% 收入 corporate | 极致 UX + 模型供应商 margin 风险 |
| **Cognition Devin** | $1M → $73M ARR (9M) | 67% PR merge (vs 34%)；2025-12 收购 Windsurf $250M | 自动化层 |
| **Windsurf (Codeium)** | 收购前 $82M ARR | 350+ enterprise；FedRAMP High 第一 IDE | 合规护城河 |
| **Anthropic Claude Code** | (Anthropic ARR $3B → $14B) | Feb 2026 重定价 $20/seat all-inclusive Enterprise；**最广企业 terminal coding agent** | 终端 + 订阅模式 |
| **GitHub Copilot Workspace / Coding Agent** | 90% F100 用 | 分配 issue → GHA sandbox → draft PR；BYOK + 多模型；Enterprise Managed Users | 分发护城河无敌 |
| **Replit Agent** | **$150M ARR (Sep 2025)**, $3B 估值 | effort-based pricing $0.06/run；58% business 用户**非工程**——拥消费 + "vibe-coding" | prosumer 定位 |
| **Aider** (OSS) | 40K+ star, 4.1M install | git-native CLI；polyglot leaderboard | OSS pair-programming 标杆 |

## 4. 销售 / 市场

| 厂商 | ARR | 模式 |
|---|---|---|
| **Clay** | **$100M ARR**, $3.1B Series C (Aug 2025) | data 富集 + waterfall + AI 个性化 |
| **Apollo** | **$150M ARR** (May 2025) | 200M+ contact 数据库 + AI SDR |
| **Tavus** | $40M Series B (Nov 2025) | AI video / digital humans → 转 "PALs" |
| **11x** | $50M Series B @ ~$350M | AI SDR Alice/Jordan；2025 churn 公开 |

## 5. 语音

| 厂商 | ARR | 价格 |
|---|---|---|
| **Bland AI** | $40M Series B (2025) | $0.09/min；自有 STT/LLM/TTS |
| **Vapi** | ~$25M, $20M Series A | base $0.05/min + components ($0.23-0.33 全包) |
| **Retell AI** | - | $0.07/min flat |

**$45B 市场转移；developer 平台收敛 ~3 winner，垂直 (sales/healthcare scheduling/debt collection) 在上层**。

## 6. 中国市场

| 厂商 | 状态 | 模式 |
|---|---|---|
| **Coze** (ByteDance) | **4.58M MAU CN** (Jun 2025) | 免费 + 无代码 + Doubao + MCP + Feishu 集成；Coze Studio 开源 |
| **Dify** | $30M Pre-A | **180K+ dev, 2000+ team, 280+ enterprise**, 1.4M 机器 175 国；51st GitHub star |
| **Kimi K2 / K2.6** (Moonshot) | - | K2.6 (2026-04): **300 sub-agent / 4000 步**；SWE-Bench Pro 领先；训练成本 ~$4.6M——成本颠覆 |
| **Doubao** (ByteDance) | **46.4% China 公有云 LLM 份额** | 16.4T tokens/day, 137× yoy；2024 Volcengine ¥12B → 目标 ¥100B 2030；80% 中国汽车 OEM + 70% 系统重要性银行 |
| **通义千问 Enterprise** (Alibaba) | **17.7%→32.1% 份额** (top) | Qwen3 全开权；Bailian 平台；DingTalk + Alibaba SaaS 集成 |
| **文心 ERNIE** (Baidu) | - | ERNIE 5.0 (Nov 2025) 2.4T MoE；Qianfan MaaS；GenFlow / Famou / Oreate / Miaoda |
| **Zhipu AutoGLM** | HKEX listed | **AutoGLM 2025-12 开源** —— 首个稳定**手机 use** Agent (WeChat/Meituan/Didi) |
| **DeepSeek** | - | R1 (Jan 2025) 匹配 o1，pennies on dollar；V3.1 (Aug 2025) 685B hybrid；20+ 中国汽车品牌 + top-5 手机 OEM 嵌入；**改变全球成本边界** |
| **万兴** (Wondershare) | A 股 (300624) | 万兴超媒 Agent (2025-07)；天幕 2.0 多媒体模型 |

## 7. 共同模式 (我们应该 steal 的)

1. **Tool/Memory/Runtime/Identity/Observability** = 标准分解 (AgentCore/watsonx/Foundry/Vertex 都收敛在此)
2. **Eval-driven dev** (Sierra Agent OS, Databricks Agent Bricks 自动合成 eval, AI21 Maestro 并行验证, MLflow 3.0)
3. **Model-agnostic + BYOK** 已是 table stakes
4. **Permission-aware retrieval** (Glean / Foundry / Mosaic + Unity Catalog) — 监管买家 unsexy moat
5. **Outcome / consumption pricing** 在客服 / 语音超过 per-seat (Sierra/Decagon/Ada/Bland/Replit effort-based)

## 8. 市场走向

- **垂直化**赢毛利：Sierra (客服) / Cursor (代码) / Clay (销售) 100× 收入倍数仅留给端到端拥工作流的垂直 Agent
- **多 Agent 编排是下一战场**：A2A / Copilot Studio 多 Agent / Kimi K2.6 300 sub-agent / watsonx Orchestrator / AgentCore 多 Agent
- **语音是最大空白**：$45B 转移，Bland/Vapi/Retell 竞速 + 垂直 wrapper
- **编码超额融资**：Cursor + Cognition + Windsurf + GitHub + Replit + Anthropic + OSS——margin 压缩不可避，差异化向 enterprise 合规 / 自治 / 自定义集成
- **M&A 浪**：Zendesk → Forethought, Cognition → Windsurf, Google reverse-acquihire；Agent eval + observability 工具是下一个

## 9. 差异化机会（gap）

1. **Agent 观测 + 治理** —— 生产团队还没 Datadog 等价物（Arize/Galileo/Braintrust 在啃）
2. **跨 Agent 身份 / "Agent ID + audit"** —— Workday ASOR + Microsoft Entra Agent ID 是暗示，无中性标准
3. **Agent simulation + 离线 eval at scale** —— Sierra 内部有，没人卖好
4. **垂直深集成 Agent**：法律 / 医疗 RCM / 保险理赔 / 会计 —— 仍欠建
5. **离网 / 主权 Agent stack** —— Cohere 唯一玩家；EU + 监管业巨大机会
6. **长 horizon coding agent + 显式成本 / 预算 control** —— Kimi K2.6 暗示，西方 incumbent 滞后

## 10. 中美差异

- **中国** = 开权 + 成本颠覆 + super-app 集成。DeepSeek/Kimi/Qwen/GLM 全开权，5-20× 便宜，深嵌 WeChat/Feishu/钉钉/Meituan + 端 (手机/车)
- **美国** = 闭源 + 高价 + 企业 SaaS。价值大多累在 frontier 模型层 (Anthropic/OpenAI) + 垂直 Agent 层 (Sierra/Cursor)
- **中国领先**手机 / 端 use Agent (AutoGLM/Coze Space)、消费集成
- **美国领先**企业垂直工作流 + 开发者工具深度

## 11. 我们要学 / steal 的 (10 条)

1. **选锐角 (垂直 / 工作流)** 而非"横向平台"。Sierra/Cursor/Clay/Decagon 全都窄起家
2. **Eval 基建作一等产品** (不是事后)。把 Agent 质量当 Datadog 待 observability ——内嵌 simulation / 回归检测 / 版本固定 eval suite。Sierra + Databricks 的 moat
3. **Outcome-based pricing 在防御得住的地方** —— 显著降买家阻力，与质量投资复利。新 category 已死 per-seat
4. **开框架 + 托管 runtime** (Vertex / AgentCore / Bedrock 模式)。OSS 框架赢开发者，runtime 收钱。闭源专有框架已死
5. **Permission-aware retrieval + 审计 log** Day 1 —— unsexy 企业成败点。每丢的企业 deal 都追溯到此
6. **认真做语音** 作主模态，不是补丁
7. **MCP / A2A 互操作** —— 别打协议，拥抱。互操是买家 #1 防锁定要求
8. **学中国成本纪律**。DeepSeek + Kimi 证明 frontier 质量 1/10 成本可达。西方企业越发要求类似经济。Day 1 token-efficient
9. **像 Writer/Cohere 捆模型 + Agent + control plane** —— 垂直整合买毛利和 quality 故事，即使 limit TAM
10. **分发 trumps tech** —— Microsoft Copilot Studio mediocre 但 ubiquitous；ByteDance Coze 通过 Doubao+Feishu 赢中国。**先规划分发再差异化**

## 12. 我们的定位草案

- **垂直**：先选 1-2 个垂直（推荐：客服 + 法务，或 销售 + 财务）
- **地理**：中国为主战场，海外（东南亚 / 中东）作扩展
- **价格**：客服走 outcome-based；销售 / 法务可订阅 + tier
- **差异化**：知识工程模块（L15）+ 电脑 Use（L14）+ 真正可私有化部署
- **OSS-first**：栈 100% OSS / 中性许可，企业可选客户云 / 自部署 / 我们 SaaS
