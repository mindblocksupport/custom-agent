# L15 · 知识工程：把个人经验落地为标准化 AI

> 状态：**讨论中** · v0.1 · 2026-04-22 · ★ 用户点名要求 —— 企业 AI 落地真正难题

## 0. 为什么这是企业 Agent 落地的**真正难题**
Polanyi 经典："**we know more than we can tell**"——企业最大资产之一是专家经验，但 80%+ 在专家头脑里，**离职即蒸发**。

企业 RAG 实施 **40% 在生产失败**——首要原因不是模型差，是"把干净 PDF 倒进 vector DB"，没有把专家**判断 / 经验 / 直觉**编码下来。NVIDIA 2024 实测：仅 chunking 策略差异就有 **9% 召回 gap** —— **语料质量 > 模型选择**。

**这一层是差异化和护城河**——别人能买到 GPT-5 / Claude，但买不到你客户的 50 个老员工 20 年的判断。

## 1. 理论基础

### 1.1 SECI 模型 (Nonaka & Takeuchi)
```
Tacit ────Externalization───→ Explicit
  ↑                              │
  │                              │
Internalization              Combination
  │                              │
  └─── Tacit ←──Socialization── Explicit
```

### 1.2 GRAI 框架 (2025 *VINE Journal* 更新)
**Generative, Receptive AI** 把 SECI 每个象限分裂成 **8 种人机交互场域**，把 LLM 作为**主动 epistemic 伙伴**——LLM 不是被动存储，而是**面试 / 观察 / 总结 / 反提模式**。

**结论**：tacit 知识不再只是人 → 人转移，是**与 AI 共演化**。

## 2. 知识捕获 8 种方法

| # | 方法 | 适用 | 工具 |
|---|---|---|---|
| 1 | **结构化专家访谈 / 决策树挖掘** | 高频确定型决策 | LLM 自动 interview chatbot |
| 2 | **学徒制 / shadowing** | 复杂判断密集 | Sierra APX 18 月轮转：9 月 Agent Engineer + 9 月 Agent PM，2 周 Bootcamp |
| 3 | **同步 think-aloud (CTA)** | 实操过程 | 截屏 + 旁白；Autodesk 2024 研究：**3-5× 比回顾访谈丰富** |
| 4 | **屏幕录制 + LLM 标注** | UI 工作流 | LLM 转录 + 决策点抽取 |
| 5 | **对话挖掘** | 客服 / 销售 | Klarna：年 Slack/Zendesk/通话 → 知识图 |
| 6 | **决策点 logging** | 已数字化流程 | 工具内埋点；每个 approve/reject/override 是标注样本 |
| 7 | **case-based reasoning** | 类例丰富 | 100-500 代表性案例 + 推理链 |
| 8 | **AI 辅助 SOP 抽取** | 2025 前沿 | SOPStruct / SOP-Bench (12 域 2000+ 任务) / Grab SOP-driven LLM 框架 (>99.8% 准确)—— LLM 语音访谈专家 → 起草 SOP 决策树，专家**只验证**，省 ~10× 时间 |

## 3. 标准化形态（tacit → 什么）

| 形态 | 何时用 | AI 消费 |
|---|---|---|
| **SOP**（编号步骤） | 高频确定 | system prompt 章节 |
| **Playbook**（决策树） | 按条件分支 | skill / tool routing |
| **Skill / Macro** | 跨 Agent 复用 | SKILL.md (Anthropic) |
| **Checklist** | 质量门 | tool description |
| **Rule set** | 合规 / 硬约束 | guardrail layer |
| **BPMN-ish workflow** | 多人协作长流程 | orchestrator graph |
| **Few-shot 示例** | 难形容的风格 | 上下文示例 |
| **Prompt 模板** | 可重复推理模式 | prompt registry |
| **Case 库** | 判例式推理 | RAG with reasoning chain |
| **知识图** | 实体关系查询 | GraphRAG |
| **Fine-tune 数据集** | 规模化风格 / 格式 | LoRA / SFT |

## 4. AI 可消费形态（2025 winners）

- **Anthropic Skills (SKILL.md)** ★ 2025-12-18 开标准，OpenAI/Microsoft/Cursor/GitHub/Atlassian/Figma 都已采纳
  - 文件夹 + `SKILL.md`，YAML frontmatter (`name`, `description`) + Markdown body
  - **Progressive disclosure**：仅 name+desc 预加载，body 按需加载，`/scripts /references /assets` 触发后才载——使 context "实际上无界"
- **CLAUDE.md** —— 项目级持久 context
  - HumanLayer 教训：**<300 行，理想 <60 行**——Claude system prompt 已吃 ~50/150-200 指令预算上限
  - 不放 lint 规则；放架构、build 命令、项目目的
- **Cursor `.cursor/rules/*.mdc`** —— 团队代码规范，git 版本化 MDC
  - **<500 行/规则，按主题分**，"看见 Agent 重复犯同一错误第二次才加规则"
- **Sierra Agent SDK skills** —— 可组合 skills "表达程序性知识——事情应当怎么做"，配确定性 API guardrails
- **Decagon AOPs (Agent Operating Procedures)** —— 自然语言 workflow，"业务变多快行为变多快"
- **Memory entries** —— Mem0 / Letta / Zep 存用户偏好与 session 模式
- **Fine-tune sets** —— 仅在规模 (>10K 干净示例) 划算时

## 5. 真实企业方法（实际 ship 的）

| 公司 | 模式 |
|---|---|
| **Sierra** | **Agent Development Lifecycle 4 阶段**：Development（可组合 skills）→ Release（code+prompts+models+KB 不可变快照）→ QA（SME **每日**在 Experience Manager 标注对话）→ Testing（每条标注对话 → mock API regression test）。**这是最规范的捕获-编码-测试闭环** |
| **Glean Verified Answers** | 专家 curated；280 企业 query 盲评：Glean 比 ChatGPT 偏好 **1.9×**，比 Claude 1.6× ——**verification step 是赢点** |
| **Klarna** | 知识图 = 画像 + 工单 + 消费 + 通话 transcripts；清了从未清过的 backlog，省 ~$40M，<2 min vs 11 min 解决。**注意**：2025 部分回退裁员策略——**capture 必须跟上 edge case 发现速度** |
| **Cresta** | 每职能微调多模型；识别**top performer**哪些行为驱动结果，作为实时 hint / checklist / 建议回复推送给所有 agent。**最干净的"编码最佳人类"循环** |
| **Decagon AOPs** | 自然语言 workflow + CRM/订单集成 |
| **Cursor `.cursor/rules`** | 团队代码风格作为已提交配置 |
| **CLAUDE.md** | per-repo 约定持久化 session 启动 |
| **OpenAI Custom GPTs** | 非工程 SME 编码 workflow → prompt + files + actions；零门槛，天花板低 |

## 6. "AI Trainer / Knowledge Engineer / Agent Engineer" 角色

3 个会聚的 title：

| 角色 | 职能 | 美国市场薪 |
|---|---|---|
| **AI Trainer** | 标注 + RLHF 反馈 | $19-$288/h（ZipRecruiter Apr 2026），中位 $84K |
| **Forward Deployed Engineer (FDE)** | Palantir 模式（"Deltas"）；至 2016 FDE > 软件工程师；OpenAI / Anthropic / Scale / Sierra 都招 | 前沿 lab $250-450K total comp |
| **Agent Engineer** (Sierra term) | PM + ML + 域知识混合；APX listing："前沿 AI 工具 + 客户共情 + 域专长" | - |

**组织位置**：Product Ops + ML Ops + Customer Success 杂交。
**Sierra/Cresta 经验**：build 期 **1 个 Agent Engineer 服务 1-2 个生产 Agent**；稳态 **1:5-10 维护**。

## 7. 工具栈

| 层 | 工具 |
|---|---|
| **Memory** | Mem0 (SaaS, vector + 3 层), Letta (开源, OS 风层), Zep (时序知识图——facts that change over time) |
| **Skills** | Anthropic Skills (SKILL.md), Sierra Agent SDK, OpenAI Codex Skills |
| **Prompt registry** | LangSmith Hub, PromptLayer, Maxim, PromptOps (git-native), Mirascope |
| **标注 / HITL** | Humanloop (LLM eval + RBAC + SOC2), Argilla (OSS, HF Hub), Label Studio (LLM-assisted) |
| **KG 构建** | Neo4j LLM Knowledge Graph Builder, GraphRAG (Microsoft), AEVS (provenance) |

## 8. 持续改进闭环（Sierra/Cresta/Decagon 都收敛在此）

```
1. 捕获用户纠正 ← 每次 override / "应该这样做"都 log
   ↓
2. 失败聚类（按根因每周）
   ↓
3. 提议 SOP/skill 更新（LLM 起草 SKILL.md diff，人审）
   ↓
4. 矛盾检测（同 scenario 跑多 skill, flag 冲突）
   ↓
5. Shadow / 模拟测试（Sierra Experience Manager 把每条标注对话变 mock API 回归测试；
                      OpenAI Eval Skills 模式：with vs without skill 跑 2 次测 delta）
   ↓
6. Skill 版本（semver + git；不可变 release）
   ↓
7. 过时知识 sunset（**显式删除指令** > 被动 deprecation；定时 review 最后使用日期）
```

## 9. 真实案例

- **客服**：Klarna 2.3M 询问/月，**80% 解决时长降**，**~700 FTE 等效**——基于 3+ 年工单/聊天蒸馏出的知识图
- **销售**：Cresta agent assist 捕获顶绩效话术 → 实时 hint 推所有 agent → 平均绩效向 top 五分位收敛
- **法律首过**：大律所内部知识 from senior partner 合同审查 → Custom GPTs / Skills；人复审 flagged 风险而非读全合同
- **工程 debug**：Cursor `.cursor/rules` + CLAUDE.md 持久化资深"代码库陷阱"，新人和 AI 都继承

## 10. 反模式（必须禁止）

1. ❌ **"把 1000 个 PDF 倒进 RAG"** —— 40% 失败率；chunking > vector DB 选择
2. ❌ **写一次永不更新** —— 知识快变域几个月就 stale
3. ❌ **一次性 prompt 调优** —— 没 git/registry，团队学习不积累
4. ❌ **AI 做文档替代** —— AI 编码经验，**不发明**经验
5. ❌ **忽略负面知识** —— **"NOT to do"** 往往比正面 SOP 更值钱，几乎从不被捕获
6. ❌ **自动生成 CLAUDE.md** —— 噪声吃指令预算
7. ❌ **Skill 静态** —— 没 sunset 流程，过时 skill 净害

## 11. 涌现方法论 / 框架

- **AI Knowledge Operations (KnOps)** —— MLOps/PromptOps 在知识工件层延伸
- **Domain-Specific AI** —— Cresta 风微调窄 Agent 在 contact center benchmark 击败横向通用
- **Agent SDLC / ADLC** —— Arthur AI + EPAM 5 阶段：Ideation → Inner-loop Dev → Test/Validate → Deploy → Monitor/Tune
- **PromptOps** —— prompts as code，git，breaking-change 检测 hook

## 12. 度量

- **知识覆盖率** = % 真实 scenario 有 codified handler（规模化前目标 >80%）
- **Skill 复用率** = 平均 #Agent 调用每 skill（低 = 碎片化）
- **time-to-codify** = 新 scenario 出现 → merged skill 小时（目标 <72h）
- **Skill 衰减率** = 30 天未调用 % skills（sunset 触发）
- **每 skill 月省专家工时**（**唯一 CFO 关心的 ROI 度量**）
- **regression-pass rate** on 对话测试套件（Sierra 风）

## 13. 推荐"知识工程模块"架构（6 层）

```
┌────────────────────────────────────────────────────────────────┐
│ L6: 改进闭环                                                    │
│  - 纠正 logger → 聚类 → LLM 起草 skill diff → 评审             │
│  - 衰减 scanner (cron) → sunset 队列                            │
├────────────────────────────────────────────────────────────────┤
│ L5: Eval & 模拟                                                 │
│  - 对话回放回归套件（Sierra 风）                                │
│  - skill A/B (with vs without) per OpenAI Eval Skills          │
├────────────────────────────────────────────────────────────────┤
│ L4: Skill / 知识 Registry                                       │
│  - SKILL.md 格式 (Anthropic 开标准)                             │
│  - Git 版本化, semver, 不可变 release                           │
│  - Progressive disclosure: name+desc → body → /references      │
├────────────────────────────────────────────────────────────────┤
│ L3: Memory 层                                                   │
│  - 短期: session context                                        │
│  - 中期: Mem0 风用户/团队偏好                                   │
│  - 长期: Zep 风时序知识图存 facts that change                  │
├────────────────────────────────────────────────────────────────┤
│ L2: Capture Workbench (给 Knowledge Engineer + SME)             │
│  - 结构化 interview chatbot (LLM 访谈专家)                      │
│  - 屏幕录制 + 转录 + 决策点抽取                                 │
│  - 工单/通话 miner → candidate skill 建议                       │
│  - SOP 起草生成器 (SOPStruct / Grab 风)                         │
├────────────────────────────────────────────────────────────────┤
│ L1: Source Connectors                                           │
│  - 工单 (Zendesk/Jira), 通话 (Gong), 聊天 (Slack/Teams),        │
│    Wiki (Confluence/Notion), CRM (Salesforce), 代码 (Git)       │
└────────────────────────────────────────────────────────────────┘
```

## 14. 90 天客户落地路径（具体执行）

| 阶段 | 时间 | 行动 |
|---|---|---|
| **embed** | Day 1-14 | FDE 风 Knowledge Engineer + 1-2 SME。Top 20 workflow 跑 think-aloud；通过 L2 capture workbench |
| **codify** | Day 15-45 | 转 30-50 SKILL.md 入 registry (L4)。每 skill 命名+描述+链接录音/transcript 作 `/references`。Top workflow 80% scenario 覆盖 |
| **eval** | Day 46-75 | 建对话回放套件 (L5)——200+ 历史案例作 mock API 回归测试。无 skill ship 不达 ≥95% pass |
| **loop** | Day 76-90 | 启用改进闭环 (L6)。SME 每日 ~30 min 在 Experience Manager 类工具评审 flagged session。衰减 scanner 夜跑 |

## 15. 与 Sierra/Decagon 差异化定位

**最大杠杆**：让**客户自己的非工程 SME 也能编/版本化 skill**（Cursor-rules / Custom-GPT 易用性），但 runtime 是**企业级带确定性 guardrails**（Sierra 级）。

"每 Agent 一个知识工程师"是瓶颈——**用我们 L2 capture workbench 把这个塌缩 5×**。

## 16. 真实坑总结
1. **80% 知识在头里** —— 文档化只能拿到 20%
2. **think-aloud > 回顾访谈 3-5×**
3. **专家不愿写 SOP** —— 用 AI 访谈让他们只验证
4. **Top performer 行为是金矿** —— Cresta 模式
5. **负面知识被忽视** —— "NOT to do"必须显式收集
6. **Skill 没有 sunset 是定时炸弹**
7. **知识捕获必须跟上业务变化速度** —— 否则 Klarna 类回退
8. **Verified Answers 比 raw RAG 强 2×** —— 人 curated 是杠杆
9. **AGPL/copyleft skill registry 绝对避免** —— 被绑死
10. **CLAUDE.md 越短越好** —— Anthropic system prompt 已吃 50 个指令预算
