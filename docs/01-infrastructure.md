# L1 · 基础设施层（Infrastructure）

> 状态：讨论中 · v0.2 · 2026-04-22 · 重写版

本层为 Agent 平台提供**计算 / 存储 / 网络 / 消息 / DR**底座，是所有上层（推理、上下文、知识、HITL、A2A）能否兑现 SLA 的物理前提。本文聚焦**部署模式选择 + 物理资源拓扑 + 真实成本**，不展开应用层语义。

相关层：
- 业务侧问题与上层指标定义见 [L10 现状问题](./10-current-issues.md)
- 模型选型/路由策略见 [L11 模型策略](./11-model-strategy.md)、API 协议见 [L12 API 协议](./12-api-protocol.md)
- 多租户隔离与命名空间策略见 [L24 多租户隔离](./24-multi-tenant.md)
- 数据合规与跨境见 [L25 数据合规](./25-data-compliance.md)
- 灾备 / 业务连续性总体方案见 [L26 DR/BCM](./26-dr-bcm.md)
- 信创全景（OS/CPU/DB/中间件/GPU）见 [L36 信创适配](./36-xinchuang.md)
- FinOps 与降本细则见 [L21 FinOps](./21-finops.md)、部署经验见 [L20 部署经验](./20-deployment-lessons.md)

---

## 1. 本层目标与 SLA 基线

| 维度 | 目标 | 测量 |
|---|---|---|
| 可用性 SLA | 业务面 ≥ 99.9%（年停机 ≤ 8.76h），核心金融场景 ≥ 99.95% | 蓝绿 + 多 AZ + L3 灾备 |
| 推理 P95 时延 | 短文本 ≤ 1.5s（首 token ≤ 800ms）、长上下文 ≤ 4s | vLLM/SGLang 引擎调优，详见 §3.2 |
| 弹性 | 5 分钟内承载 3× 突发流量，30 分钟内 10× | HPA + Cluster Autoscaler + GPU 预热池 |
| 数据合规 | 国内：等保三级 / 网信办备案 / 数据本地化；海外：SOC2 Type II + GDPR | 见 [L25](./25-data-compliance.md) |
| 3 年 TCO 偏差 | 实际 vs 预算 ±15% 以内 | FinOps 月度复盘，见 [L21](./21-finops.md) |
| 信创就绪 | 政企单可在 ≤ 4 周完成信创栈替换 | CI 双流水线，见 §11、[L36](./36-xinchuang.md) |

---

## 2. 部署模式选择（先定这个，再谈技术）

### 2.1 四种模式对比

| 模式 | 适用客户 | 月运营成本（1 万 DAU 含模型 API）| 一次性硬件 | 交付周期 | 我们交付占比（2025 实绩）|
|---|---|---|---|---|---|
| **公有云 SaaS（多租户）** | 海外 SMB、国内中小企业、数据非敏感 | ¥8–25 万 | 0 | 3–7 天 | 18% |
| **公有云 VPC 独立部署** | 中大型、行业客户、一般敏感 | ¥18–55 万 | 0 | 2–4 周 | 22% |
| **混合云**（管控/数据国内 + 推理出海或反之）| 跨境集团、数据分级 | ¥35–110 万 | 部分边缘节点 | 6–10 周 | 12% |
| **私有化（IDC / 客户机房）** | 政府 / 金融 / 军工 / 央企 / 大型国企 | ¥40–80 万（运维 + 折旧）| ¥300–2000 万 | 8–16 周 | **48%** |

> 经验值：To B 客户中 60%+ 最终落到 VPC 或私有化，**Day 1 必须按"可私有化"设计**：所有依赖必须支持离线安装、不依赖外网、镜像可导出、配置可托管。

### 2.2 决策树

```
客户问"能否私有化"
├─ 必须私有化（政企/军工/金融核心）→ 私有化 + 信创（见 [L36]）
├─ 可接受 VPC（数据不出客户云账号）→ 公有云 VPC
├─ 跨境业务 + 国内合规 → 混合云（见 [L25] 跨境）
└─ 海外 SMB / 国内创新业务 → SaaS 多租户
```

---

## 3. 计算

### 3.1 CPU 集群（业务面 / Agent 编排 / API Gateway）

| 项 | 推荐 | 备注 |
|---|---|---|
| K8s 版本 | **1.28 LTS / 1.30 LTS**（不追新；1.28 EOL 2026-10）| 私有化客户优先 1.28；公有云托管可上 1.30 |
| 控制面 | 公有云用托管（ACK Pro / EKS / TKE / CCE）；私有化用 kubeadm + 3 master HA | 私有化场景控制面拆 etcd 单独 SSD 节点 |
| 节点规格（通用）| **32C128G / NVMe 500GB**（业务）；**16C64G**（边车/Sidecar 池）| 32C128G 是 2026 年 sweet spot |
| ARM 节点池 | AWS Graviton4 / 阿里倚天 710 / 华为鲲鹏 920 | 同等算力**便宜 30–42%**，Java/Go/Python 均稳定 |
| HPA | CPU + 内存 + 自定义指标（QPS、队列长度、GPU 队列等待）| 单纯 CPU HPA 在 LLM 业务下严重失真 |
| Cluster Autoscaler | 设上下限，缓冲池保留 2 节点（避免冷启动 90s+）| GPU 池单独配 CA，缓冲 ≥ 1 节点 |
| 多 AZ | **≥ 3 AZ**，节点反亲和性强制 | 阿里云"金融级 3AZ"必上；自建 IDC 至少同城双中心 |
| 节点池分组 | 通用 / GPU / 内存型（向量/Redis）/ ARM / 工作负载隔离（按租户）| 多租户隔离细节见 [L24](./24-multi-tenant.md) |

**单价参考（2026 Q1，包年含税）**

| 厂商 | 32C128G ECS | 月单价（¥）|
|---|---|---|
| 阿里云 ECS g7（Intel）| ecs.g7.8xlarge | 2,650 |
| 阿里云 ECS g8y（倚天 ARM）| ecs.g8y.8xlarge | 1,580 |
| 腾讯云 SA5（AMD）| SA5.8XLARGE128 | 2,480 |
| 华为云 kc1（鲲鹏 ARM）| kc1.8xlarge.2 | 1,620 |
| AWS Graviton4 c8g | c8g.8xlarge | $1,180 |

### 3.2 GPU 集群（推理）

#### 3.2.1 GPU 卡型与 2026 Q1 月价（含税，国内公有云）

| 卡型 | 显存 | 公有云月价（¥）| 私有化采购单价（¥）| 适合模型 |
|---|---|---|---|---|
| RTX 4090 24G | 24GB | 5,800–8,500 | 18,000（灰度供货）| 7B 全精度 / 13B INT4 |
| L20 48G | 48GB | 9,500–13,000 | 56,000 | 14B–32B INT8 |
| A10 24G | 24GB | 6,500–9,000 | 22,000 | 7B–13B 推理 |
| L40S 48G | 48GB | 14,000–19,000 | 78,000 | 32B 推理、轻训练 |
| A100 80G PCIe | 80GB | 32,000–46,000 | 220,000–280,000 | 32B–72B 推理 |
| A100 80G SXM4（8 卡机）| 640GB | 280,000–360,000/机 | 2,100,000/8 卡机 | 200B 推理 / 微调 |
| H100 80G SXM5（8 卡机）| 640GB | 580,000–780,000/机 | 4,500,000/8 卡机 | DeepSeek-R1 671B / Llama 405B |
| H20 96G（国内特供）| 96GB | 38,000–52,000 | 320,000 | 国内合规、72B 推理首选 |
| **昇腾 910B3 64G** | 64GB | 28,000–35,000（华为云）| 180,000–240,000 | 信创首选；详见 [L36](./36-xinchuang.md) |
| **海光 DCU Z100** | 64GB | 31,000–38,000 | 210,000 | 信创备选；详见 [L36](./36-xinchuang.md) |
| **寒武纪 MLU370-X8** | 48GB | 22,000–28,000 | 145,000 | 信创备选 |

> H100 / B200 在国内**仅水货 + 灰度渠道**，企业采购走 H20 / 昇腾 / 海光。详见 [L36 信创适配](./36-xinchuang.md)。

#### 3.2.2 推理引擎选择矩阵

| 引擎 | 优势 | 劣势 | 推荐场景 |
|---|---|---|---|
| **vLLM 0.7+** | PagedAttention、生态最强、多模态成熟、支持 FP8 | 长上下文显存占用偏高 | **默认首选**；NVIDIA 卡通用 |
| **SGLang 0.4+** | RadixAttention（前缀缓存命中 ↑40%）、结构化输出强、JSON 模式快 | 生态比 vLLM 小 | 多轮对话密集、Agent 工具调用密集场景 |
| **TensorRT-LLM 0.18+** | 极致吞吐（vLLM 的 1.4–1.8×）、INT4/FP8 优化好 | 工程门槛高、新模型滞后 2–6 周 | 稳态大流量场景（客服 / 搜索）|
| **TGI 3.x** | HF 官方、易用 | 性能略弱于 vLLM | HF 生态绑定 |
| **MindIE 1.0+（昇腾）** | 昇腾 910B 原生最佳 | 仅昇腾 | 昇腾集群必上，详见 [L36](./36-xinchuang.md) |
| **vLLM-Ascend / DeepSpeed-Ascend** | 兼容 vLLM API + 昇腾后端 | 性能比 MindIE 差 10–25% | 想保留 vLLM 调用习惯 |

#### 3.2.3 容量规划公式（必背）

```
需要的 GPU 卡数 = ⌈(峰值 QPS × 平均输出 tokens × 平均输入 tokens 系数)
                 ÷ (单卡有效 throughput × 0.7 安全系数 × KV cache 命中率修正)⌉
```

**真实例子（某 SaaS 客服平台）**：
- 5,000 用户/天 × 每人 8 轮 × 平均输出 380 tokens = 15.2M tokens/天
- 高峰 4 小时集中 60% 流量 → **1,580 tokens/sec 峰值**
- 单卡 H20 跑 Qwen2.5-32B-Instruct（FP8，vLLM 0.7）实测 **520 tok/s**
- 计算：1,580 ÷ (520 × 0.7) ≈ **4.34 → 5 张 H20**（含余量 + 1 张冷备）
- 月成本：5 × ¥45,000 = **¥22.5 万**
- 对比纯 API（同等 token）≈ ¥38 万 → **自建省 41%**，盈亏平衡线约 ≥ 800 DAU

---

## 4. 存储

### 4.1 关系库（Postgres / 国产）

| 维度 | 公有云 / 海外 | 私有化 / 信创 |
|---|---|---|
| 默认 | **PostgreSQL 16/17**（RDS）| 达梦 DM8 / 人大金仓 KingbaseES V9 / OceanBase 4.x |
| 复制 | 流复制 + 同步副本，RPO < 30s | 达梦 DSC / 金仓读写分离集群 |
| 分库 | Citus / pg_partman 按租户 | 详见 [L24](./24-multi-tenant.md) |
| 容量基准 | 每 DAU ~10MB/天（含审计/上下文摘要）；1 万 DAU/年 ≈ 3.6TB | 同上 |
| 备份 | WAL-G → S3/OSS，RPO < 5min | XTrabackup-like，落对象存储 |
| 信创替换信号 | 政企招标书"国产化数据库" / "等保三级 + 安可"硬性条款 | 详见 [L36](./36-xinchuang.md) |

### 4.2 向量库选型

详细对比与 RAG 工程化见 [L16 知识工程](./16-knowledge-engineering.md) §3。本层只给基础设施侧选型表：

| 选型 | 规模 | 公有云月成本（3 节点）| 私有化资源 | 备注 |
|---|---|---|---|---|
| **pgvector 0.7+** | < 2,000 万向量 | 复用 RDS | 复用 PG 节点 | MVP 默认 |
| **Qdrant 1.12+** | 1 千万–2 亿 | ¥12,000–25,000 | 3 × 16C64G + 2TB NVMe | Rust 性能优、混合检索好 |
| **Milvus 2.5** | 1 亿+ | ¥35,000–80,000 | 5+ 节点（含 etcd/Pulsar）| 工业级，运维重 |
| **Weaviate 1.27** | 1 亿内 | ¥20,000–40,000 | 3+ 节点 | GraphQL 友好 |
| **Elastic 8.15+ KNN** | 已有 ES | 复用 ES | 复用 ES | 资源消耗高，混合检索强 |

经验：**先 pgvector 后迁 Qdrant**，过早上 Milvus 浪费 30% 预算。

### 4.3 对象存储

| 场景 | 公有云 | 私有化 |
|---|---|---|
| 文档原文 / 模型 ckpt / 备份 | 阿里 OSS、腾讯 COS、AWS S3 | **MinIO RELEASE.2025**（S3 兼容）+ 纠删码 4+2 |
| 价格（标准存储） | ¥0.12/GB/月（OSS）；¥0.10/GB/月（COS）| 自建约 ¥0.04/GB/月（含硬件折旧）|
| 归档 | OSS 归档 ¥0.015/GB/月 | MinIO + 蓝光库或磁带 |
| 模型权重缓存 | OSS + JuiceFS / Alluxio | MinIO + JuiceFS |

### 4.4 Redis（缓存 / 分布式锁 / 语义缓存）

- Cluster 模式，**3 主 3 从起步**，单分片 16–32GB
- 用途：Session、限流计数、**LLM 语义缓存（命中率 25–45% 直接降本）**、分布式锁、轻量队列
- 信创替换：Tendis（腾讯）/ Tair（阿里）/ KeyDB / 国产 GoldenDB-Redis
- 公有云月价参考：阿里云 Tair 集群版 64GB 约 ¥6,800/月

### 4.5 消息队列

| MQ | 用途 | 推荐版本 | 月价（公有云 3 节点）|
|---|---|---|---|
| **Kafka 3.7+** / **Confluent / 自建** | 日志、事件流、Agent 步骤事件、A2A 异步消息 | KRaft 模式去 ZK | ¥18,000–32,000 |
| **RabbitMQ 4.x** | 业务消息、复杂路由 | 集群 + 镜像队列 | ¥6,000–12,000 |
| **Pulsar 3.3** | 多租户 + 计算存储分离 | 与 [L24](./24-multi-tenant.md) 配合 | ¥25,000–48,000 |
| **RocketMQ 5.x（信创）** | 阿里系 / 信创合规 | Controller 模式 | ¥12,000–22,000 |
| **Redis Stream** | 轻量异步、Agent 任务队列 | 复用 Redis | 复用 |

---

## 5. 网络

### 5.1 VPC 子网设计（标准模板）

```
VPC 10.0.0.0/16（生产）
├─ Public      10.0.0.0/22    → ALB / NLB / NAT Gateway / 堡垒机出口
├─ App-AZ-A    10.0.10.0/23   → K8s 业务节点
├─ App-AZ-B    10.0.12.0/23
├─ App-AZ-C    10.0.14.0/23
├─ GPU-AZ-A    10.0.20.0/23   → GPU 推理节点（带宽预留）
├─ GPU-AZ-B    10.0.22.0/23
├─ Data        10.0.30.0/22   → DB / Vector / Redis / Kafka
├─ Mgmt        10.0.40.0/24   → Prometheus / Grafana / 跳板机
└─ DR-Link     10.0.50.0/24   → 跨 Region/IDC 专线
```

**关键安全组规则**：
- App → LLM API 出口：**必经 NAT**，源 IP 白名单备案
- App ↔ Data：仅放行 PG/5432、Redis/6379、Qdrant/6334
- Mgmt → All：仅运维堡垒机，强制 MFA + 审计回放

### 5.2 入口（North-South）

| 组件 | 选型 | 说明 |
|---|---|---|
| L4 | NLB / SLB | TCP 接入 |
| L7 + DDoS | ALB + **WAF**（阿里云 WAF 3.0 / Cloudflare / F5）| WAF 必上，按 LLM 注入规则定制 |
| CDN | 阿里云 / 腾讯云 / Cloudflare / Akamai | 静态资源 + 模型 SSE 回源加速 |
| API Gateway | **Kong 3.7 / APISIX 3.x / Higress（阿里）** | LLM 路由策略见 [L11](./11-model-strategy.md)、[L12](./12-api-protocol.md) |
| 服务网格 | Istio 1.22 / Linkerd（轻量）| 多租户金丝雀 + 流量镜像 |

### 5.3 出口（LLM API / 第三方调用审计）

- 所有 LLM 厂商 API（OpenAI / Anthropic / Gemini / 通义 / 文心 / Kimi）**必经统一出口 NAT**
- 出口侧统一限流、计费、敏感词扫描、PII 脱敏（见 [L25](./25-data-compliance.md)）
- 公网出口默认拒绝，按目标域名白名单放行
- 国内 → 海外 LLM API：必走合规专线（如阿里云金融云 / 火山引擎合规出海），不可直连，详见 [L25](./25-data-compliance.md) §跨境

### 5.4 跨 Region / IDC（为 DR 准备）

- 公有云：CEN（阿里）/ TGW（腾讯）/ Transit Gateway（AWS），≥ 1Gbps，时延 < 30ms
- 私有化：MSTP / SD-WAN 双线（电信 + 联通），同城 ≤ 5ms，异地 ≤ 50ms
- 详细 DR 方案见 [L26](./26-dr-bcm.md)

---

## 6. 灾备（DR）等级

完整方案、演练、Runbook 见 [L26 DR/BCM](./26-dr-bcm.md)。本层定义资源开销基线：

| 等级 | RPO | RTO | 实现 | 成本系数 | 适用 |
|---|---|---|---|---|---|
| L1 普通 | 24h | 4h | 每日全备 + 对象存储 | 1.0× | 内部工具、测试 |
| **L2 重要** | 1h | 30min | 增量备份 + 主从 + 冷备 GPU 镜像 | 1.3× | **大多数 SaaS / VPC 业务（推荐）** |
| **L3 核心** | 5min | 5min | 流复制 + 自动切换 + GPU 双 AZ 热备 | 1.8× | **金融客服 / 政务办事（推荐）** |
| L4 金融级 | 0 | < 1min | 同城双活 + 异地灾备 + Multi-Region 推理 | 3.0× | 银行核心 / 监管要求 |

**我们默认推荐 L2–L3**：Agent 业务多为"准实时"，L4 边际成本不划算。L4 仅在监管硬性要求或客户明确买单时启用。

---

## 7. 多租户基础设施隔离

业务侧租户模型、配额、计费见 [L24 多租户隔离](./24-multi-tenant.md)。本层落实 K8s/网络层隔离：

| 维度 | 实现 |
|---|---|
| 命名空间 | `tenant-<id>-<env>`，每租户独立 ns |
| **ResourceQuota** | CPU/内存/GPU/存储硬上限；超额 Pod 被拒 |
| **LimitRange** | 单 Pod 默认/上限，防止单租户挤占 |
| NetworkPolicy | 默认 deny-all + 显式 allow，跨租户流量物理阻断 |
| 节点亲和 | 大客户独占节点池（`tenant=foo:NoSchedule` + nodeSelector）|
| StorageClass | 每租户独立 PV，带租户 label，跨租户 PVC 拒绝挂载 |
| GPU 隔离 | NVIDIA MIG（A100/H100 切片）或独占整卡；昇腾 vNPU 切片 |
| Secret 隔离 | 每租户独立 KMS Key（CMK），ETCD 加密静态数据 |
| 审计 | 每租户独立 audit log 流，落 ClickHouse + 客户可查 |

> 强隔离场景（金融、政务）：直接**集群级隔离**（每租户/每客户独立集群），避免 K8s 控制面共用风险。

---

## 8. 真实成本案例

### 8.1 国内公有云 · 5,000 DAU · 混合模型（推荐线）

| 项 | 规格 | 月成本（¥）|
|---|---|---|
| K8s 业务集群 | 12 节点 32C128G（含 ARM 4 节点）| 28,500 |
| GPU 推理 | 5 × H20 96G（Qwen2.5-32B FP8）| 225,000 |
| GPU 冷备 | 1 × H20（非高峰挂训练任务）| 38,000 |
| Postgres RDS | 高可用 8C32G + 1TB SSD | 9,800 |
| Qdrant 向量库 | 3 节点 16C64G + 2TB NVMe | 14,500 |
| Redis Tair | 64GB Cluster | 6,800 |
| Kafka | 3 节点 8C32G | 18,000 |
| 对象存储 OSS | 8TB 标准 + 2TB 归档 | 990 |
| 闭源 API（Claude/GPT-4o，30% 难任务流量）| 计费（详见 [L11](./11-model-strategy.md)）| 45,000–95,000 |
| CDN / 公网带宽 | 200Mbps + CDN 流量 | 8,500 |
| WAF + DDoS 高防 | 标准包 | 4,800 |
| 监控 / APM / 日志 | Prometheus + Loki + Grafana + 阿里云 SLS | 6,500 |
| 跨 AZ 流量 | 估 5TB | 2,500 |
| **合计** | | **¥40.9–48.9 万 / 月** |

> 同等业务规模国外（AWS us-east-1 + Anthropic API）大致 $58k–72k/月，约 ¥42–52 万。

### 8.2 私有化 · 5,000 DAU · 信创栈

| 项 | 规格 | 一次性（¥）| 月运营（¥）|
|---|---|---|---|
| 服务器（鲲鹏 + 海光 + 昇腾 910B × 8）| 12U 标准机柜 × 2 | 1,850,000 | — |
| 存储阵列（全闪 50TB）| Huawei OceanStor / 同有 | 720,000 | — |
| 交换机 + 防火墙（信创）| 华为 / 锐捷 | 280,000 | — |
| 机房托管 | 4U + 2 机柜 + 20A | — | 18,000 |
| 电费 | 估 22kW | — | 26,000 |
| 软件 License（达梦 + 麒麟 + 东方通）| 3 年 | 480,000 | — |
| 平台 License（我方）| 年 | — | 35,000 |
| 驻场实施（首年）| 1 名 + 远程支持 | — | 45,000 |
| **合计 3 年 TCO** | | **¥3,330,000 一次性** | **¥124,000/月 × 36 = ¥446 万** |
| **3 年合计** | | | **≈ ¥780 万**（公有云同期约 ¥520 万）|

> 私有化 3 年 TCO 约为公有云 1.5×，但**数据完全自主 + 信创合规 + 不依赖外部 API**——是政企客户买单的根本原因。

---

## 9. MVP 范围（4–6 周）

| 周 | 交付项 |
|---|---|
| W1 | 单 K8s 集群（公有云托管 ACK/EKS）+ VPC 标准模板 |
| W2 | 1 × GPU 节点（H20 或 4090，开发测试用）+ vLLM 部署 1 个模型 |
| W3 | Postgres + pgvector 单实例 + Redis 单实例 + MinIO |
| W4 | Kong/APISIX + WAF + CDN + 出口 NAT + 基础监控 Prometheus/Grafana |
| W5 | GitLab CI + ArgoCD + 镜像仓库 + 蓝绿/金丝雀 |
| W6 | 端到端验收 + 简单备份策略（每日 RDS + OSS）|

**MVP 不做**：异地灾备、信创、多租户隔离、L3+ DR、双活——按客户合同 Phase 2 启用。

---

## 10. 真实坑（务必提前防范）

### 10.1 GPU 供货周期 3–6 个月（致命）

- A100 / H100 国内合规渠道（H20 / 昇腾 910B）2026 Q1 仍**到货周期 12–24 周**
- **预付款 + 框架协议**：与华为云 / 阿里云签**预留实例**（RI），保证关键期算力
- 公有云作为**溢出池**：私有化客户应急时按小时租云上 GPU，按月租贵但能救命
- **业务侧降级方案**：大客户合同里写明"GPU 不可用时降级到云 API"

### 10.2 私有化离线包

- **客户内网无外网**是常态，不是例外
- 必须交付：
  - 离线镜像仓库（Harbor 离线包，含所有依赖）
  - OS 包（RPM/DEB 全家桶 + 依赖闭包）
  - Python / Node 包（pip / npm 私服）
  - 模型权重（OSS 离线导出，含 sha256）
  - 信创版镜像（OS × CPU 架构 × 信创 DB）
- 做一次"完全离线网络环境演练"是 P0，否则交付现场翻车

### 10.3 信创适配 RPM / 兼容矩阵

完整矩阵见 [L36 信创适配](./36-xinchuang.md)。最易踩坑：

- **OS × CPU × Python**：麒麟 V10 SP3 + 鲲鹏 + Python 3.11 是当前最稳组合，3.12 在 ARM 上仍有部分 wheel 缺失
- **CUDA 替换**：信创栈 NVIDIA 驱动**不允许**，必须 CANN（昇腾）或 ROCm（海光），代码层抽象推理后端
- **国密**：HTTPS 走 TLCP（非 TLS），客户经常临交付才提，Nginx 需换 TongHttpd 或 Tengine
- **中间件 License**：东方通 TongWeb / 金蝶 Apusic 的 License 与 CPU 序列号绑定，扩容时要重新申领

### 10.4 隐性带宽成本

- 跨 AZ 流量在公有云普遍 **¥0.05–0.10/GB**，向量库 + LLM 调用容易月增 ¥1–3 万
- 优化：同 AZ 部署调用密集组件（vLLM 与 Qdrant 同 AZ 可省 60%）

### 10.5 K8s 升级窗口

- 1.28 EOL 2026-10，私有化客户通常滞后 6–12 月，需在合同里明确"年度大版本升级窗口"
- 升级前**必跑**：CRD 兼容性扫描（kube-no-trouble）+ 镜像兼容回归

---

## 11. CI/CD

| 阶段 | 标准流水线 | 信创流水线（并行）|
|---|---|---|
| 源码 | GitLab CE/EE 16+ | 同 |
| 构建 | Docker BuildKit + 多架构（amd64 + arm64）| **再加**: linux/loong64 (龙芯)、linux/sw_64 (申威，按需) |
| 镜像仓库 | Harbor 2.11 / ACR / TCR | Harbor 部署在客户内网，离线同步 |
| 镜像扫描 | Trivy + 国产合规扫描（绿盟 / 奇安信）| 同 |
| 模型/数据 | DVC + S3，签 sha256 | MinIO |
| 部署 | **ArgoCD 2.13**（GitOps）| 同 + 离线 chart 包 |
| 渐进发布 | Argo Rollouts（金丝雀 / 蓝绿）| 同 |
| 流量切换 | Istio / Higress | Higress（阿里贡献，信创认证较好）|
| 测试基线 | k6 / Locust + LLM eval（详见 [L17](./17-prompt-engineering.md)、[L19](./19-vendor-landscape.md)）| 同 |
| 安全扫描 | SAST + DAST + 镜像 SBOM（CycloneDX）| 同 + **安可**等保扫描 |

**信创双流水线**：每次 PR 同时跑标准 + 信创流水线，信创 fail 不阻塞主线但**必须在交付前修复**，避免上线返工。

---

## 12. 可观测性基线（与 [L18 可观测性] 配合）

| 维度 | 默认栈 | 备注 |
|---|---|---|
| Metrics | Prometheus 2.55 + VictoriaMetrics（长存）| 私有化必上 VM，PG 指标量爆炸 |
| Logs | Loki 3.x / ClickHouse 24.x | 大规模选 ClickHouse，成本 ↓60% |
| Tracing | OpenTelemetry + Jaeger / Tempo | LLM trace 必含 prompt/response（脱敏后），见 [L13](./13-context-engineering.md) |
| GPU 监控 | DCGM Exporter + 自研 vLLM exporter | KV cache 命中率、queue depth 必须打点 |
| Dashboard | Grafana 11 | 标准模板：业务 / GPU / 成本三套 |
| 告警 | Alertmanager + PagerDuty / 飞书 / 钉钉 | 分级（P0–P3）+ 静默规则 |

---

## 13. 与上层文档的接口

| 上层 | 关系 |
|---|---|
| [L11 模型策略](./11-model-strategy.md) | GPU 池规模 = 模型矩阵 × QPS 反推 |
| [L12 API 协议](./12-api-protocol.md) | API Gateway 选型在本层；契约在 L12 |
| [L13 上下文工程](./13-context-engineering.md) | KV cache / 前缀缓存 → 推理引擎选型影响显存预算 |
| [L14 Computer Use](./14-computer-use.md) | 沙箱节点池（独立、强隔离）、出口流量管控 |
| [L16 知识工程](./16-knowledge-engineering.md) | 向量库选型 |
| [L17 Prompt 工程](./17-prompt-engineering.md) | 推理引擎决定能否用 JSON 模式 / Tool calling |
| [L21 FinOps](./21-finops.md) | 月度成本表来自本层埋点 |
| [L24 多租户](./24-multi-tenant.md) | 隔离实现 |
| [L25 数据合规](./25-data-compliance.md) | 出口审计、跨境专线、KMS |
| [L26 DR/BCM](./26-dr-bcm.md) | 灾备等级与切换 Runbook |
| [L27 语音](./27-voice.md) | 语音节点池（高网络 IO + GPU）独立设计 |
| [L31 边缘 AI](./31-edge-ai.md) | 边缘节点本层不展开 |
| [L33 持续微调](./33-continuous-finetune.md) | 训练池与推理池物理隔离 |
| [L34 A2A](./34-a2a.md) | Agent 间消息走 Kafka/Pulsar |
| [L36 信创](./36-xinchuang.md) | 全栈替换矩阵 |

---

## 14. 待决议

- [ ] **首选交付模式**：SaaS / VPC / 私有化优先级（影响产研排期 60%）
- [ ] **国内云厂商主备**：阿里云 / 腾讯云 / 华为云 / 火山引擎（影响 GPU 可得性、私有化路径）
- [ ] **是否做信创**：决定整套技术栈是否要二次构建（[L36](./36-xinchuang.md) 全量评估）
- [ ] **GPU 自建 vs 云租**：盈亏平衡线（约 800–1200 DAU），需结合销售预测
- [ ] **备份/归档保留期**：金融行业 ≥ 5 年，政务 ≥ 3 年，普通 ≥ 6 月（见 [L25](./25-data-compliance.md)）
- [ ] **GPU 集采 vs 灵活租**：是否签预留实例 RI（年付折扣 22–35%，但锁定风险）
- [ ] **海外节点**：是否预置 Singapore / Frankfurt / us-east-1（影响出海客户上线速度）
- [ ] **K8s 集群规模上限**：单集群 ≤ 500 节点 vs 多集群联邦（Karmada / KubeFed v2）
