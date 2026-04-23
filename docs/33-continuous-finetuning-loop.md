# L33 · 持续微调闭环 / RLHF / 数据飞轮

> 状态：**讨论中** · v0.1 · 2026-04-22

## 0. 为什么独立成章
- 微调模型成本高，但**窄场景能比通用模型 +5-15pp**
- **数据飞轮**是企业 Agent 长期护城河
- 但 80% 团队**做不起来**——数据/工具/流程都缺

## 1. 飞轮总览

```
生产 trace (Langfuse)
    ↓
质量分类 (LLM judge + 人工)
    ↓
数据集准备
    ├─→ Golden set 增量 (回归测试)
    ├─→ SFT data (指令微调)
    ├─→ DPO/RLHF data (偏好对)
    └─→ 红队对抗 (safety)
    ↓
训练 / 评测 / 部署
    ↓
A/B vs 老版本
    ↓
胜出 → 替换；败 → 回炉
```

## 2. 微调时机判断

何时值得微调（满足任一）：
- 通用模型在特定任务**已 saturated**（>10% 错）
- 任务**重复性高**且**金额大**（per task 节省 > 训练成本）
- **数据敏感**不能调外部 API
- **延迟严苛**（<50ms 必须自部署小模型）
- **风格 / 格式**严格要求（few-shot 不够）
- **域专有语料丰富**（医 / 法 / 金融术语）

何时**不**微调：
- 通用模型够用
- 数据 < 1 万条
- prompt + RAG 能解决
- 领域常变（容易过拟合 stale）

## 3. 微调技术栈

### 3.1 SFT (Supervised Fine-Tuning)
- 入门，需求最大
- 工具：**LLaMA-Factory** / **Axolotl** / **trl**
- 数据：(instruction, response) 对
- 资源：7B 模型 8×A100 1 天

### 3.2 LoRA / QLoRA
- 参数高效，省 GPU 90%+
- 一个 base 模型多个 LoRA adapter (per 任务)
- IBM Granite Guardian 用此模式

### 3.3 DPO (Direct Preference Optimization)
- 取代 RLHF（更简单稳定）
- 数据：(prompt, chosen, rejected) 偏好对
- 来自用户 thumb up/down

### 3.4 ORPO / KTO
- DPO 进化版
- KTO 不需要 paired，单点足够

### 3.5 RLHF 经典
- PPO based
- 复杂，OpenAI / Anthropic 内部用
- 一般企业不用

## 4. 数据 pipeline

```
Production trace
    ↓ filter (high quality only)
Trace → labeled examples
    ↓ deduplicate
    ↓ PII 脱敏
    ↓ sensitivity check
    ↓ version
Dataset (versioned in DVC / Argilla)
    ↓
Training
```

工具：
- **Argilla** (开源 labeling)
- **Label Studio**
- **DVC** (数据版本)
- **Snorkel** (弱监督)
- **Cleanlab** (质量检测)

## 5. 数据质量胜过数量

- Anthropic 内部经验：**1k 高质量 > 10k 噪声**
- LLM judge + 人审组合
- 多样性 > 重复
- 边界 case 比 happy path 重要

## 6. Eval 必须先于训练

否则你不知道有没有进步：
- Golden set ≥ 200 case
- 多次 eval（temp>0 时多次 avg）
- 与 base 模型对比
- A/B 在小流量

## 7. AITL (Agent-in-the-Loop) 模式

2025 提出：
```
Live trace → annotation surface (pairwise / adoption / missing)
    → dataset → eval/fine-tune → deploy → loop
```
缩短从 月 → 周

## 8. 真实案例

- **Cresta**：每职能微调多模型；顶绩效话术 → SFT data
- **Decagon**：fine-tuned in-house models 服务于 Together AI
- **Cursor**：用 IDE telemetry (acceptance / edit / revert) 训 reward model
- **GitHub Copilot**：用接受率持续优化

## 9. 我们的策略

**不优先做**，但留口：
- Trace 收集时已带质量信号（thumb up/down）
- Skill version + outcome 关联
- 长期：当某垂直数据 >5 万 + outcome 可衡量，启动微调

**首选场景**：
- 客服特定品牌 tone
- 销售特定产品话术
- 法律特定文书

## 10. 成本估算

| 任务 | 资源 | 时间 | 美元 |
|---|---|---|---|
| 7B SFT (10k 样本) | 8×A100 | 1 day | $200 |
| 7B LoRA (10k) | 1×A100 | 6 hours | $20 |
| 70B SFT | 8×H100 | 3 days | $3,600 |
| 70B LoRA | 4×H100 | 1 day | $400 |
| 70B DPO | 8×H100 | 2 days | $2,400 |

vs API 节省（典型）：1M token Sonnet 4.6 = $3 + $15 = $18 → 自部署 70B 大致 $5；月省 $13K @ 1M task。**>5 万 task/月 才划算**。

## 11. 实施清单
- [ ] Trace 质量标注 pipeline
- [ ] 数据集 versioning (DVC)
- [ ] LLaMA-Factory / Axolotl 环境
- [ ] LoRA 多 adapter 服务架构
- [ ] Eval-first 流程（先 golden set 后训练）
- [ ] A/B 部署支持
- [ ] 模型 registry + 回滚
- [ ] 质量阈值自动 promote / revert
