# L35 · Agent Simulation / 数字孪生平台

> 状态：**讨论中** · v0.1 · 2026-04-22 · 差异化能力

## 0. 为什么独立成章
- Sierra 内部有 **simulation** 系统（部署前用合成对话找级联失败）
- 没人卖好 → **市场空白**
- 客户上线前最大焦虑：**未知失败模式**
- Simulation = "Agent 数字孪生"

## 1. 价值

| 阶段 | 价值 |
|---|---|
| 开发期 | 加速 prompt / skill 迭代 |
| 上线前 | 发现级联失败 / 边界 case |
| 灰度期 | 与生产对比 |
| 持续运营 | 回归测试 / 安全 red team |
| 客户 demo | 让客户安心试 |

## 2. Simulation 技术栈

### 2.1 用户模拟器 (User Simulator)
- LLM 扮演用户
- 多种 persona（合作 / 困惑 / 抱怨 / 攻击者）
- 多轮对话，记忆持续

### 2.2 环境模拟器
- 模拟工具响应（mock API）
- 模拟数据库状态
- 模拟外部系统（CRM / ERP）

### 2.3 评分器 (Judge)
- LLM judge 打分
- 业务规则校验
- 多 dimension（任务完成 / 礼貌 / 准确 / 合规）

### 2.4 场景生成
- 从生产 trace 抽取 → 生成变体
- 边界 case 生成（fuzzing）
- 对抗 case 生成（red team）

## 3. Sierra 模式参考

```
1. 历史对话 → 解构成 user intent + 期望 outcome
2. 用 LLM 扮演 user，跑新 Agent 版本
3. 比较 outcome 与期望
4. 失败 case 入回归集
```

## 4. 与 eval 区别

| 维度 | Eval (Golden Set) | Simulation |
|---|---|---|
| 数据 | 静态 case | 动态生成 |
| 交互 | 单轮多 / 固定 | 多轮 / 可变 |
| 工具 | mock 简单 | 完整环境 |
| 用途 | 回归 | 探索 + 回归 |

两者**互补**，不是替代。

## 5. 实施

### 5.1 Phase 1: 基础 simulation
- LLM 扮演 user
- Mock tool
- 跑 100-1000 case / dim
- LLM judge 打分

### 5.2 Phase 2: 完整环境
- 真实 staging 环境
- Sandboxed tool 调用（不影响生产）
- 多 Agent 协作模拟

### 5.3 Phase 3: 持续 simulation
- 每 PR / 每天跑
- Production sample 持续 feed
- 异常自动 alert

## 6. 工具

- **OpenAI Evals** (基础 eval framework)
- **Inspect AI** (UK AISI, agent eval, MIT)
- **Promptfoo** (CI 友好)
- **DeepEval** (pytest 形)
- **TestSprite** (端到端 simulation)
- **AgentBench** (开源 benchmark 框架)
- **Sierra Agent OS**（不开源，参考）

## 7. 关键挑战

- **简谐振荡**：simulator 与 Agent 都是 LLM，相互"知道"对方思考方式 → 不真实
- **Mock 不准**：真实工具有奇怪边界
- **覆盖不全**：simulation 通过≠生产通过
- **成本**：N×LLM call (Agent + simulator + judge)

## 8. 客户价值

- **上线前 demo**：客户看 simulation 报告，建信任
- **持续质量保证**：每 prompt 改触发
- **合规 audit**：simulation log 作证据

## 9. 实施清单
- [ ] User simulator (LLM persona)
- [ ] Mock 工具环境
- [ ] LLM judge + business rule
- [ ] 场景生成器（从 trace + fuzzing）
- [ ] CI 集成
- [ ] 客户报告 dashboard
- [ ] 持续 production sample feed
