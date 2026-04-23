# L26 · 灾备 (DR) & 业务连续性 (BCM)

> 状态：**讨论中** · v0.1 · 2026-04-22

## 0. 为什么独立成章
- 企业 SLA 99.9%+ 必须达到（年停机 < 8.7h）
- LLM vendor 宕机是常态（Anthropic / OpenAI 2024-2025 多次）
- AI 系统 DR 与传统不同：模型版本 / prompt cache / vector index 都要备

## 1. RTO / RPO 矩阵

| 等级 | RPO (数据丢失容忍) | RTO (恢复时间) | 实现 | 成本系数 |
|---|---|---|---|---|
| L1 普通 | 24h | 4h | 每日备份 | 1× |
| L2 重要 | 1h | 30min | 增量 + 主从 | 1.3× |
| **L3 核心** | 5min | 5min | 流复制 + 自动切换 | 1.8× |
| L4 金融级 | 0 | <1min | 同城双活 + 异地灾备 | 3× |

**Agent 系统典型 L2-L3**。

## 2. AI 系统 DR 特殊维度

不同于传统 IT，AI 系统还要备：

| 维度 | DR 策略 |
|---|---|
| **模型权重** | 自部署模型镜像跨 region；API 备 fallback 厂商 |
| **Prompt 库** | git 多 region；Langfuse Prompts 跨 region 复制 |
| **Vector index** | 向量库快照 + 跨 region 异步复制 |
| **Knowledge base** | 原始文档 + 解析后 chunk 都备份 |
| **Memory store** | per-tenant 备份 + 跨 region |
| **Skill library** | git + 镜像 |
| **Eval dataset** | git |
| **Trace / audit** | 长保留 + 异地 |
| **API key / 凭证** | KMS 跨 region |

## 3. 多 LLM Vendor Failover (实战)

```
Primary: Sonnet 4.6 (us-east via Anthropic)
  ├─ 健康探测: 30s 间隔, 5 次失败 → 切
  ├─ 自动切到: Sonnet 4.6 via AWS Bedrock (us-west)
  ├─ 再切到: GPT-5.4 (Azure OpenAI)
  ├─ 再切到: DeepSeek V3.2 (国内备份)
  └─ 全挂: 缓存响应 / 优雅降级 ("AI 暂时不可用")
```

**关键**：
- 提前接入至少 3 个 vendor
- 多云合同（Anthropic 直 + Bedrock + Vertex 同模型）
- Idempotency key 防重试时 vendor 切换导致双扣

## 4. 数据备份策略

| 数据 | 备份频率 | 保留 | 异地? |
|---|---|---|---|
| Postgres | 流复制 + 每日全 + 增量 | 30 天 | 是 |
| Vector DB | 每日快照 | 7 天 | 是 |
| Object storage | 跨 region 复制 | 永 | 是 |
| Redis | 仅 RDB 快照 | 1 天 | 否 (cache 可重建) |
| Audit log | 实时复制 | ≥ 6 月 / 5 年 | 是 |
| K8s config | git + ArgoCD | 永 | 是 |

## 5. 异地容灾架构

```
┌─────────────────────────────────────┐
│ Primary Region (北京 / us-east)     │
│  - 主业务流量                        │
│  - 主 DB (写)                       │
│  - 主向量库                          │
└────────────┬────────────────────────┘
             │ 异步复制
             │ (Kafka MirrorMaker / pg streaming)
             ▼
┌─────────────────────────────────────┐
│ DR Region (上海 / us-west)           │
│  - 热备 (待激活)                     │
│  - 从 DB (只读)                     │
│  - 向量库 replica                   │
└─────────────────────────────────────┘
```

切换流程：
1. 监控告警
2. 评估（可恢复? 多久?）
3. 决策切换（>30min 即切）
4. DNS 切换 / Global LB 切流量
5. 从 DB 升主
6. 验证业务
7. 通告客户

## 6. 同城双活（高 SLA）

```
两个 AZ 都跑生产流量
  ├─ DB: PG 主 + Patroni 自动选主 / OceanBase 多副本
  ├─ Vector: Qdrant cluster 跨 AZ
  ├─ Cache: Redis cluster sentinel
  └─ K8s: 跨 AZ 节点池
```

## 7. Chaos Engineering (定期演练)

季度演练：
- ✅ 主 DB 宕机 → 切从
- ✅ 主 LLM vendor 宕机 → failover
- ✅ Region 整个挂 → DR
- ✅ Vector DB 单节点挂
- ✅ 网络分区
- ✅ K8s 节点 evict
- ✅ Tenant 配额耗尽
- ✅ Prompt cache 全失效
- ✅ Audit log 写入故障

工具：Chaos Mesh / Litmus / Gremlin

## 8. Backup 验证

**关键**：备份必须定期**演练 restore**——很多公司发现备份是空的（只有出事才知道）。

季度 restore 演练：
- ✅ DB 全量 restore
- ✅ 向量索引 restore
- ✅ tenant 单独 restore
- ✅ 历史 audit log 查询
- ✅ Skill / Prompt 历史版本回滚

## 9. 业务连续性计划 (BCP)

```
事件 → 评估 → 决策 → 执行 → 沟通 → 复盘
```

必备文档：
- **联系矩阵**：On-call / 主管 / CISO / DPO / 法务 / 客户成功 / PR
- **决策权限**：什么级别能切换 region / 通告客户
- **客户沟通模板**（中英）
- **监管通报 SOP** (PIPL 72h, GDPR 72h)
- **第三方 vendor 联系**

## 10. 监控指标 (SLO)

| 指标 | SLO |
|---|---|
| 可用性 | 99.9% (年停机 <8.7h) |
| LLM 成功率 | >99.5% (含 vendor failover) |
| P95 延迟 | <3s |
| 数据丢失 | RPO < 5min (核心) |
| 恢复时间 | RTO < 5min (核心) |
| Backup 成功率 | 100% (失败立刻告警) |
| Restore 演练通过率 | 100% (季度) |
| Chaos 演练通过率 | 100% (季度) |

## 11. 实施清单
- [ ] RTO/RPO 业务方签字
- [ ] 多 LLM vendor 接入（≥3）
- [ ] 跨 region 数据复制
- [ ] DR region 热备
- [ ] DNS / Global LB 切换能力
- [ ] Backup 自动化 + 监控
- [ ] 季度 restore 演练
- [ ] 季度 Chaos 演练
- [ ] BCP 文档 + 联系矩阵
- [ ] 客户 / 监管沟通 SOP
- [ ] On-call rotation
