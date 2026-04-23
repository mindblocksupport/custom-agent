# L21 · LLM FinOps & 成本管理（前瞻）

> 状态：**讨论中** · v0.1 · 2026-04-22 · 大多数 Agent 项目失败 #1 原因 = 成本失控

## 0. 为什么独立成章
- **90% Agent 项目 30 天内失败**，#1 原因：成本失控
- **OpenAI 自己 2025 gross margin 40% → 33%**——平台都顶不住
- 真实事故：$0.08 任务飙到 $12（150×）；10K 重试循环；某团队 6 周 $4,600 Cursor 费用
- FinOps for LLM 是**新岗位**，工具栈不成熟

## 1. 成本结构（拆解）

```
┌────────────────────────────────────────────────────────┐
│ 总成本 = Token 成本 + Infra 成本 + 运营成本           │
├────────────────────────────────────────────────────────┤
│ Token 成本 (60-80%)                                    │
│   ├ Input tokens (绝大部分驱动)                         │
│   ├ Output tokens                                       │
│   ├ Cached input (5-10× 便宜)                          │
│   └ Reasoning tokens (思考型模型)                       │
├────────────────────────────────────────────────────────┤
│ Infra 成本 (10-25%)                                    │
│   ├ K8s + GPU                                           │
│   ├ Vector DB                                           │
│   ├ Postgres + Redis                                    │
│   └ 观测 (Langfuse + ClickHouse)                        │
├────────────────────────────────────────────────────────┤
│ 运营成本 (5-15%)                                        │
│   ├ AI on-call                                          │
│   ├ Knowledge engineering                               │
│   ├ Eval / 标注                                         │
│   └ Customer success                                    │
└────────────────────────────────────────────────────────┘
```

## 2. 真实生产预算（参考）

| 厂商 | Year-1 预算 | 备注 |
|---|---|---|
| Sierra | **$200K-350K** ($150K base + $50-200K 实施) | "Agent OS" 入门费六位数 |
| Cursor 团队 | 6 周 **$4,600**（超去年全年 2 倍） | 个人 $350/周超额；Opus 级 $72K/年/座位 |
| Devin | **$2.25/ACU** (~15min 工作) | 简单前端任务 $2.25-4.50/PR |
| Klarna 客服 | (回退后) per-conversation 成本 | 取代 700 FTE 等效 |

## 3. 为什么 Agent 比单调用贵 10-100×

```
单调用 LLM:    1 次 input + 1 次 output      = 1×
20 轮 Agent: 每轮重发整个对话 + 工具结果 = ~20× input
              + 工具调用 / RAG / Memory      = +30-50%
              + 思考 token (推理模型)        = +20-50%
              = 大约 30-50× 等价
```

**输入 token 是主驱动**（不是输出）。20 轮 Agent 把同 50K-token 仓库读 20 次。

## 4. 成本控制工具栈（推荐）

### 4.1 Prompt Caching ★ 最高 ROI
| 厂商 | 折扣 | 阈值 |
|---|---|---|
| Anthropic | **90% off cached read**, 1.25× 5min write, 2× 1h write | 1024-4096 tokens 起 |
| OpenAI | **50% off auto cache** | >1024 tokens 自动 |
| Gemini | **90% off** explicit + 隐式 (2.5+) | - |

**Manus 报告**: cached input $0.30/MTok vs uncached $3.00/MTok = **10× 省钱**
**目标 cache 命中率 >80%**, 延迟降 85%

### 4.2 语义缓存
- GPTCache / Bifrost / Portkey
- FAQ 类**命中率 60-70%**
- **10× 省钱 + 100× 省延迟**
- 5000 DAU 客服场景实测**月省 ¥40K+ LLM 费**

### 4.3 Batch API
- OpenAI / Anthropic 非实时打 **5 折**
- 适合：夜间汇总、embedding 回填、合规扫描

### 4.4 错峰路由
- DeepSeek 16:30-00:30 GMT 最高 **-75%**
- 定时任务 / batch 排到此时段

### 4.5 模型分层 router
- 简单问 Haiku $1/$5；难问 Sonnet $3/$15；超难 Opus $5/$25
- 实测：80% 流量给中等价位可省 60-70% 成本而效果不掉

### 4.6 输出预算
- 任务级 max_tokens: 代码 2K, 对话 500, 分类 50

## 5. 预算 / 配额（必备）

```python
# 维度
- per API key
- per user
- per department
- per tenant
- per task type
- per model

# 阈值
- 软阈值 80% → 邮件告警
- 硬阈值 100% → 阻断 + 转人工
- 突发上限（防 single bad loop）

# 颗粒度
- 实时 token / cost 累计入 ClickHouse
- 每分钟 aggregate
- 超阈值 < 1s 拦截
```

## 6. 自部署 vs API 盈亏（已在 L11，此处摘要）

| 对比 | 盈亏点 |
|---|---|
| vs frontier API | **2-3M token/天** ≈ $7.5K-15K/月 → 8×H100 ($36K/月) 12 月摊销 |
| vs 最便宜开源 API | **15-20M token/天**, 24-36 月才回本 |
| 70B 自部署 (8×H100) 实际全成本 | $15-20K/月 |

## 7. 计费模式（给客户）

| 模式 | 适合 | 例 |
|---|---|---|
| **Token-based** (passthrough + markup) | 开发者 / 工具 | OpenAI 模式 |
| **Per-seat** | 内部生产力 | Cursor $20-200/座位 |
| **Per-conversation** | 客服 | Sierra ~$1-2/解决对话 |
| **Outcome-based** | 客服 / 销售 | 仅当结果产生才收 |
| **Per-task** | 自动化 | Devin $2.25/ACU |
| **Effort-based** | 复杂创作 | Replit $0.06/run |
| **订阅 + tier + 超额** | 混合 | 大部分 SaaS |

**经验**: Outcome-based 对客户阻力最低（与质量复利）；token-passthrough 对开发者透明；per-seat 内部最易接受。

## 8. 成本归因 / showback / chargeback

每 trace 标 metadata：
```python
metadata = {
    "tenant_id": "acme",
    "department": "support",
    "user_id": "u_123",
    "agent_id": "support_v2",
    "feature": "ticket_summary",
    "session_id": "s_abc",
    "biz_tag": "premium_customer",
}
```

按维度滚动报表：
- Daily / Weekly / Monthly
- Top 10 expensive features
- 异常 user 检测
- per-tenant invoice 自动化

## 9. 成本预测 / 预算计划

```python
# 基础公式
monthly_cost = (
    DAU × queries_per_user_per_day × 30
    × avg_input_tokens × (1 - cache_hit_rate) × input_price
    + ... output ...
    × markup
)
```

**关键 sensitivities**：
- DAU 增长率（增长越快，越要 cache）
- Cache 命中率（每提升 10pp = 省 ~7% 总成本）
- 模型选型（Opus → Sonnet 省 5×；Sonnet → Haiku 省 3×）

## 10. 异常检测（防失控）

| 信号 | 阈值 | 行动 |
|---|---|---|
| 单 task token > 平均 10× | 10× | 中断 + 告警 |
| 单 user 日 cost > 预算 80% | 80% | 软告警 |
| 单 user 日 cost > 预算 100% | 100% | 阻断 + 升级 |
| Tenant cost burn > 月 50% by 月中 | 50% | 销售/客户 review |
| 模型某 provider error rate > 5% | 5% | failover |
| Cache 命中率 < 60% | <60% | prompt 结构 review |
| 重试次数 > 3 | 3 | 工具 / 模型问题 |

## 11. 实施清单

- [ ] 每 trace 全 metadata 标
- [ ] ClickHouse 实时 aggregate
- [ ] 预算 / 配额引擎（per-tenant / per-user / per-task）
- [ ] 4 层 cache (exact / semantic / prompt cache / context cache)
- [ ] 模型分层 router（haiku → sonnet → opus）
- [ ] 异常检测 + 自动熔断
- [ ] 月度成本报告（per-tenant / per-feature）
- [ ] 客户 showback dashboard
- [ ] Cost-per-task SLO（如 客服 <$0.05）
- [ ] FinOps 责任人（不能只是工程兼职）

## 12. 前瞻：FinOps for AI 是新职业
2026 年 FinOps Foundation 正式加 "AI/LLM" 到核心实践：
- AI Cloud Cost Engineer（新 title）
- AI 负责人定期 review
- "Token economics" 成董事会议题（OpenAI margin 数字推动）
- 工具：TokenFence, Vantage AI, Datadog Cloud Cost LLM module 等出现
