# L29 · 客户 90 天 Onboarding 套件

> 状态：**讨论中** · v0.1 · 2026-04-22 · 决定续约的关键

## 0. 为什么独立成章
- **time-to-value 决定续约**——SaaS 第一年必须见效
- Sierra / Cresta 都 4-6 周交付——已是行业 benchmark
- 没 SOP / 工具 / 模板 = 每客户从零，规模化死
- 销售拍胸脯说 4 周 → 实际 6 月 → 客户怒退

## 1. 90 天分阶段总览

```
Day 0       Day 14      Day 45       Day 75       Day 90
  │           │           │             │            │
[Discovery] [Codify]   [Pilot]      [Scale]     [Handover]
  ↓           ↓           ↓             ↓            ↓
KPI 定义   30-50 skill  10% 灰度    25% 灰度    100% 生产
合同确定   golden set   shadow→live  KPI 校验    持续运营
SOW 签     L4 acl 接   HITL 工作   skill 扩展  客户独立
```

## 2. Phase 0: Discovery (Day 1-14)

### 输出物
- ✅ **业务场景 SOW**：哪些 use case，TopN 优先级
- ✅ **数据源 inventory**：connector 清单 + 权限
- ✅ **安全 / 合规 review**：等保 / SOC2 / 数据出境 / 客户机房还是云
- ✅ **成功 KPI** 定义：任务完成率 / CSAT / 成本 / FTE 节省
- ✅ **HITL 节点**：哪些操作必须人审 (L22)
- ✅ **Stakeholder map**：决策人 / 审批 / 执行 / 反对者

### 必备会议
- Kick-off (项目启动)
- 业务方 workshop x 2
- IT / Security review
- Legal / Compliance review
- 用户访谈 (5-10 个 future user)

### 我们交付
- Discovery report
- 90 天 plan + milestones
- 风险登记
- 沟通节奏（weekly status / biweekly steering）

## 3. Phase 1: MVP / Codify (Day 15-45)

### 知识工程冲刺（核心）
按 L15 的方法：
- 与 1-2 SME embed (think-aloud)
- 屏幕录制 + 决策点抽取
- LLM 起草 SOP → SME 验证
- 30-50 SKILL.md 入 registry
- 80% scenario 覆盖

### 技术接入
- ✅ SSO 集成（OIDC / SAML / 钉钉 / 飞书）
- ✅ Connector：top 3 数据源
- ✅ RAG：核心知识库 ingestion + 解析 (RAGFlow DeepDoc)
- ✅ Tools：5-10 业务工具接入
- ✅ Multi-tenant 隔离验证 (L24)
- ✅ 合规配置 (L25)
- ✅ 观测接入 (Langfuse)

### Eval Set
- 200+ golden test case (业务方提供 + 我们扩展)
- pass rate >95% 才能 ship

## 4. Phase 2: Pilot / Shadow → 10% Canary (Day 46-60)

### Shadow Mode (先不返用户)
- Agent 跑但不发到客户面前
- 人工评 quality
- 收 ground truth
- prompt / skill 优化

### 10% Canary
- 选 user cohort (内部员工 / 友好客户)
- 实时 KPI 监控
- HITL 队列饱和度监控
- 成本 burn rate
- Kill switch 测过 (必)
- Daily standup 处理 bad case

## 5. Phase 3: 25% → 75% Scale (Day 61-80)

### 25% (Day 61-70)
- KPI 持平或好于 baseline
- 客户内部 ops hardening
- 客服 / SRE 培训

### 75% (Day 71-80)
- 业务 case review
- 长尾失败模式发现
- skill library 扩展
- HITL 频率优化（trust 提升）

## 6. Phase 4: Handover (Day 81-90)

### 100% 生产 + 持续运营
- ✅ 业务 SLA 锁定
- ✅ 成本 / 质量 weekly review 机制
- ✅ Skill 衰减监控
- ✅ 客户内部 admin 培训完
- ✅ 客户 knowledge engineer 上岗
- ✅ Quarterly red team 计划
- ✅ 模型升级窗口（季度）
- ✅ 续约对话启动

### 交付物
- Handover doc
- Runbook (AI on-call)
- Admin / End-user 培训材料
- 月度报告模板
- 紧急联系矩阵

## 7. 必备工具 / 模板包

我们提供给每客户：

| 工具 | 用途 |
|---|---|
| **Discovery Workbook** | 业务场景 / 数据源 / KPI 模板 |
| **Skill Authoring Kit** | SKILL.md 模板 + LLM-assisted SOP 生成 |
| **Eval Test Generator** | 从客户历史数据自动生成测试 case |
| **Connector Library** | 50+ 预置 SaaS 接入 |
| **HITL UI Templates** | 钉钉 / 飞书 / Web 卡片 |
| **Onboarding Dashboard** | 进度跟踪 + KPI 仪表盘 |
| **Runbook Generator** | 基于配置自动生成运维手册 |

## 8. 真实参考节奏

| 厂商 | 实施周期 |
|---|---|
| Sierra | 4-6 周 |
| Cresta | 4-6 周 |
| Decagon | 4-8 周 |
| Glean | 8-12 周（更复杂） |

我们目标：**MVP 4 周 + Pilot 4 周 + Scale 4 周 = 12 周完整 = 90 天**

## 9. 客户成功 (CS) 团队结构

| 角色 | 比例 |
|---|---|
| **Solutions Architect** (SA) | 1 : 5-10 客户 |
| **Forward Deployed Engineer** (FDE) | 1 : 1-2 客户 (高价值) |
| **Customer Success Manager** (CSM) | 1 : 10-20 客户 |
| **Knowledge Engineer** | 1 : 1-2 Agent (build), 1 : 5-10 (steady) |

## 10. 红线 / 风险信号

🚨 立即升级：
- Day 30 还没 SSO
- Day 45 KPI 不达基线
- Day 60 没 ship pilot
- HITL 队列堆积 >100 持续 1 周
- 成本超预算 50% 持续 3 天
- 客户停 weekly review

## 11. 续约对话 (Day 75 启动)

- ROI 报告 (节省 FTE / 提速 / CSAT 提升 / 收入增长)
- 续约 + 扩展机会 (新场景 / 新部门)
- Pricing review
- Multi-year discount

## 12. 实施清单
- [ ] Onboarding 团队组建 (SA + FDE + CSM + KE)
- [ ] 12 个工具 / 模板包准备齐全
- [ ] Discovery workshop 模板
- [ ] Skill authoring kit (LLM-assisted)
- [ ] Eval generator
- [ ] Connector library 50+
- [ ] Onboarding dashboard
- [ ] 90 天 master timeline 模板
- [ ] 客户培训材料（admin / end-user）
- [ ] Handover doc 模板
- [ ] 红线监控自动化
- [ ] 续约 SOP
