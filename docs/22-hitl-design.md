# L22 · 人在回路（HITL）设计

> 状态：**讨论中** · v0.1 · 2026-04-22 · 真实落地的关键设计但常被简化

## 0. 为什么独立成章
- HITL 是 Agent **真正合规上线的关键**——监管、责任、不可逆操作必须有人
- **设计不好就成"卡死器"**：Air Canada 类事故就是因为没 HITL，Replit 删库就是因为没 HITL
- 但**设计过重就让 Agent 没价值**——平均每任务都要审 = 自动化失败

## 1. HITL 触发条件（不是越多越好）

| 条件 | 必 HITL? | 例 |
|---|---|---|
| **不可逆操作** | ✅ 必 | 删库, 转账, 发邮件, 改生产 config |
| **金额 > 阈值** | ✅ 必 | 大额订单, 退款 > $X |
| **跨多用户影响** | ✅ 必 | 群发通知, 批量改 |
| **法规要求** | ✅ 必 | KYC, 医疗诊断, 法律意见 |
| **模型置信度低** | ✅ 自适应 | confidence <0.7 → escalate |
| **用户主动要** | ✅ 是 | "let me confirm" 按钮 |
| **新 skill 灰度** | ✅ 临时 | 上线前 N 次 |
| **顶级 VIP 客户** | 可选 | 高价值客户 |
| **正常对话回复** | ❌ 不 | 否则失去自动化价值 |
| **只读查询** | ❌ 不 | - |

## 2. 风险分级矩阵

| 风险 | 操作类型 | 默认 HITL? | 例外 |
|---|---|---|---|
| **L0** | 只读查询 | 不 | - |
| **L1** | 计算 / 转换 | 不 | - |
| **L2** | 轻写入（草稿，发消息低敏） | 抽样 1-5% | 高频可降 |
| **L3** | 中写入（发邮件，建工单） | 是，可批量 | trusted user 可降 |
| **L4** | 重写入（改 DB，调资金 < 阈值） | **必单审** | - |
| **L5** | 致命（删数据，资金 > 阈值，发对外公告） | **必单审 + 高级权限** | 永不 auto |

## 3. 审批 UX（极其关键）

### 3.1 优秀审批界面要素
```
┌─────────────────────────────────────────────────┐
│ 待审批 #1234              紧急程度: ⚠️ HIGH    │
├─────────────────────────────────────────────────┤
│ 摘要 (1 句):                                     │
│ Agent 想删除订单 #5678 (金额 ¥2,580)           │
│                                                 │
│ 上下文:                                          │
│ 用户 zhang@acme.com 要求"取消上周耳机订单"     │
│ Agent 已检索：5 单匹配 → 选最近 1 单            │
│                                                 │
│ 风险:                                            │
│ ⚠️ 不可逆；金额超 ¥1000 阈值                    │
│                                                 │
│ Agent 推理:                                      │
│ [展开 trace ▼]                                  │
│                                                 │
│ 操作:                                            │
│ [✓ 批准]  [✗ 驳回]  [✎ 修改]  [→ 升级]         │
└─────────────────────────────────────────────────┘
```

### 3.2 必备元素
- **1 句话摘要**（先看）
- **明示风险**（颜色 + 图标）
- **上下文足够做决策**（user / 历史 / 业务规则）
- **Agent 推理可展开**（透明但默认折叠）
- **一键操作**（批准 / 驳回 / 修改 / 升级 / 委派）
- **附理由**（驳回必填）

### 3.3 移动端优先
- 推送通知 → 一键打开 → 30 秒内决策
- iOS / Android / 钉钉 / 飞书 / 企微 卡片
- 离线缓存 → 联网同步

## 4. 通知渠道（按场景）

| 场景 | 推荐渠道 |
|---|---|
| 工作时间 / 室内 | 钉钉 / 飞书 / Slack 卡片 |
| 紧急 | 短信 + 电话 |
| 出差 / 移动 | App push notification |
| 邮件汇总 | 每日摘要（低优先批量） |
| 自助 console | Web dashboard |

**多渠道协同**：
- 立即推一个主渠道
- 5 min 无响应 → 升级 (短信)
- 15 min 无响应 → 通知备选审批人
- 30 min 无响应 → 升级到主管

## 5. 超时策略（防卡死）

| 操作 | 默认超时 | 超时行为 |
|---|---|---|
| L3 中写入（邮件草稿） | 1 hour | 默认通过（可配置） |
| L4 重写入 | 4 hours | 默认拒绝 + 通知 |
| L5 致命 | 24 hours | 默认拒绝 + 升级 |
| 紧急流程 (生产事故) | 5 min | 升级 |
| HITL 队列 > 100 | - | 临时降阈值 + 告警值班 |

## 6. 审批人路由（RBAC + 委派）

```python
def find_approver(action, context):
    # 1. 业务规则路由
    if action.amount > 100000:
        return ROLE_FINANCE_DIRECTOR
    if action.type == "delete_user_data":
        return ROLE_DPO  # 数据保护官
    
    # 2. 委派 / 代理（休假时）
    primary = lookup_primary_approver(action.tenant)
    if primary.is_out_of_office():
        return primary.delegate_to
    
    # 3. 防"自审自批"
    if action.requested_by == primary.user_id:
        return primary.escalate_to  # 必须找上级
    
    # 4. 负载均衡（多审批人时）
    return round_robin_or_least_busy(eligible_approvers)
```

## 7. 批量审批（防 HITL 疲劳）

- **同类操作**自动 group：例 50 封个性化邮件 → 1 次审批
- **抽样审批**：随机 10% 详审 + 90% 一键全过
- **risk-based 抽样**：异常 / 边界 100% 审，常规 5%
- **trust building**：连续 N 次批准后调升 trust → 降 HITL 比例

## 8. 审计 trail（必备）

```sql
hitl_request (
    id, workflow_run_id, step_run_id,
    action_summary, risk_level,
    proposed_by_agent, proposed_at,
    approver_id, approver_role,
    decision (approve/reject/modify/escalate),
    decision_reason,
    decided_at, decision_latency_ms,
    metadata (mobile/web, ip, user_agent)
)
```

要求：
- ✅ **不可篡改** (WORM / append-only)
- ✅ **完整链** (谁请求 → 谁审 → 决策 / 理由 → 何时)
- ✅ 满足等保 / SOX / GDPR
- ✅ 可导出（PDF / CSV with 签章）
- ✅ 保留期：金融 5 年

## 9. 信任校准（动态降低 HITL 频率）

```python
trust_score = f(
    历史批准率,        # 高 → 降 HITL
    批准平均延迟,       # 短 = 重要 / 烦
    模型置信度趋势,     # 上升 → 降 HITL
    用户反馈,          # 点踩多 → 升 HITL
    业务影响,          # 大 → 升 HITL
    最近事件,          # 出过事 → 临时升 HITL
)
```

**示例**: 同 user 同类操作连续 50 次批准 → trust >0.95 → 降至抽样 10%。

## 10. 预算 / 队列健康

| 指标 | SLA |
|---|---|
| HITL 队列长度 | <50 |
| 平均决策延迟 | <30 min |
| 超时率 | <5% |
| 升级率 | <10% |
| 同类操作批量率 | >70% |

## 11. 反模式
1. ❌ **HITL everything** = 自动化死，用户失望
2. ❌ **HITL nothing** = Replit 删库类
3. ❌ **审批 UI 信息不全** = 拒批 / 误批
4. ❌ **不可批量** = 审批人疲劳
5. ❌ **无超时** = 永远卡住
6. ❌ **审批 = 自审** = 制衡失效
7. ❌ **不可委派** = 休假就停
8. ❌ **无审计** = 等保过不了

## 12. 实施清单
- [ ] 风险分级表（L0-L5）+ 业务方签字
- [ ] 审批 UX 设计（移动 + Web 卡片）
- [ ] 多通道通知（钉钉/飞书/邮件/短信）
- [ ] 超时升级链
- [ ] 委派 / 代理机制
- [ ] 批量 / 抽样 / trust 调度
- [ ] 不可篡改 audit log
- [ ] HITL 队列健康 dashboard
- [ ] 反"自审"防御
- [ ] 月度 HITL 报告（决策延迟 / 升级率 / 拒批理由聚类）

## 13. 前瞻
- **AI 审 AI**: 用 critic LLM 做第一道审，仅边界 case 升级人
- **可解释性强化**: trace + 风险评分自动可视化
- **责任溯源链**: 每决策上链或 hash chain，符合 EU AI Act 高风险 audit
- **预设 SOP 推荐**: 常见 case Agent 直接给"我建议这样审"
