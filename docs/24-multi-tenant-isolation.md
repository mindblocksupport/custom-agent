# L24 · 多租户隔离深度

> 状态：**讨论中** · v0.1 · 2026-04-22 · SaaS 第一天就要做对的事

## 0. 为什么独立成章
**所有企业 To B SaaS 第一天就死在这**。一次跨租户泄露 = 公司声誉重创 + 客户清空 + 媒体报道。Glean / Sierra / Decagon 全都重金做这块。**RFP 第一关**。

## 1. 隔离级别选择

| 级别 | 描述 | 月成本 | 适用 |
|---|---|---|---|
| **L1 共享 DB + tenant_id** | 应用层隔离 | 1× | SMB 试用 |
| **L2 共享 DB + schema/namespace** | 中等隔离 | 1.2× | 中型客户 |
| **L3 独立 DB / cluster per tenant** | 强隔离 | 2-3× | 金融 / 大客户 |
| **L4 完全独立部署** | 物理隔离 | 5-10× | 政企 / 涉密 |

**经验**：起步 L1 + L2 混合（按 tenant tier 分），1-2 年后扩到 L3。

## 2. 必须隔离的 7 个维度

| 维度 | 隔离手段 |
|---|---|
| **数据存储** | row-level (tenant_id) + 字段加密 + 客户 KMS 密钥 |
| **向量库** | Qdrant collection / Milvus partition / Weaviate 多租户 namespace |
| **缓存** | Redis key 前缀 `tenant:{id}:...` + 独立 db |
| **对象存储** | S3 bucket per tenant 或 prefix per tenant + IAM |
| **计算** | K8s namespace per tenant（高 tier）；resource quota |
| **网络** | VPC / subnet / NetworkPolicy per tenant；出口流量审计 |
| **配额** | per-tenant API rate limit + token budget + storage quota + GPU quota |

## 3. 应用层强制 (Critical)

**最致命 bug**：SQL 漏写 `WHERE tenant_id = ?`。**必须从 ORM / Service 层强制**，不能靠工程师记忆。

### 3.1 ORM 强制
```python
# 推荐 SQLAlchemy + tenant scoped session
class TenantScopedSession:
    def query(self, model):
        return self.session.query(model).filter(
            model.tenant_id == current_tenant_id()
        )
# 工程师没法绕过
```

### 3.2 Postgres Row Level Security (RLS)
```sql
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON orders
  USING (tenant_id = current_setting('app.tenant_id')::uuid);
-- 即使应用 bug 漏写 WHERE，PG 自己拦
```

### 3.3 必备测试
```python
# 跨租户访问测试 - CI 必跑
def test_cross_tenant_isolation():
    tenant_a = create_tenant()
    tenant_b = create_tenant()
    order = create_order(tenant=tenant_a)
    
    with as_tenant(tenant_b):
        with pytest.raises(NotFound):
            Order.get(order.id)  # 必须看不见
```

## 4. 向量库隔离（特别坑）

| 库 | 推荐隔离 |
|---|---|
| **Qdrant** | Collection per tenant（小）→ Tiered Multitenancy（>1k tenant）+ 必带 filter |
| **Milvus** | Partition by tenant_id；高 tier 独立 collection |
| **Weaviate** | **Multi-tenancy** 是一等公民（50k tenant/node, 1M tenant/20-node cluster, lazy load, cold offload） |
| **pgvector** | RLS 强制 |

**严防"跨租户检索泄露"**：
- 检索时**强制注入** tenant filter
- 性能优化：tenant filter 必带索引
- 单元测试覆盖跨租户检索 = 必空

## 5. RAG 权限二次过滤（Glean 模式）

向量库隔离 + **业务级 ACL** 双层：
```
检索 (vector top 50)
  → tenant filter (强制)
  → ACL filter (用户实际可见的 doc_id)
  → 返回
```

ACL 数据：
```sql
-- 每文档 / chunk 带可见角色 / 用户
acl (resource_id, resource_type, principal_id, principal_type, permission)
-- 检索时 join 过滤
```

## 6. 计算 / 配额隔离

```yaml
# K8s ResourceQuota per namespace (tenant)
apiVersion: v1
kind: ResourceQuota
metadata:
  namespace: tenant-acme
spec:
  hard:
    requests.cpu: "20"
    requests.memory: 80Gi
    requests.nvidia.com/gpu: "2"
    persistentvolumeclaims: "10"
    services.loadbalancers: "2"
```

LLM 配额（per tenant）：
- TPM (tokens/min)
- RPM (requests/min)  
- 日预算 (¥)
- 月预算 (¥)
- 工具调用频率
- 并发 session 上限

## 7. 加密

| 数据类型 | 加密 |
|---|---|
| 传输 | TLS 1.3 端到端 |
| 静态（DB / 对象存储） | AES-256 at-rest |
| 字段级敏感（手机/身份证/卡号） | 应用层 + 客户 KMS |
| 密钥管理 | Vault / KMS；**客户管 KMS (BYOK)** for 大客户 |
| 国密 | SM2/SM3/SM4（政府要求） |

## 8. Audit Log per tenant

每租户独立审计流：
- 不可篡改 (append-only / WORM)
- 客户可导出（用于合规 audit）
- 保留期 ≥ 6 月（等保），金融 5 年

```sql
audit_log (
    id, tenant_id, ts, 
    actor_user_id, actor_role,
    action, resource_type, resource_id,
    before, after,  -- JSONB
    ip, user_agent, request_id
) PARTITION BY tenant_id, ts;  -- 物理分区
```

## 9. 跨租户共享场景（特殊处理）

某些场景需共享：
- 公共知识库（行业法规 / 公开文档）
- 模板 / skill 市场
- 跨租户协作（partner mode）

设计：
- `is_public` 标记的资源跳 tenant filter
- 显式同意流程（数据持有方明确同意才能跨）
- 共享层独立 DB，不放租户私有 DB

## 10. 灾难场景测试

定期演练（季度）：
- ✅ 跨租户 SQL 注入尝试
- ✅ 向量检索越权
- ✅ 缓存 key 冲突
- ✅ 配额耗尽不影响其他租户
- ✅ tenant 删除流程（GDPR right to be forgotten）级联清理
- ✅ tenant 数据导出完整性

## 11. tenant 生命周期

```
注册 → 试用 → 付费 → 升级 tier → ... → 解约
                                         ↓
                                   数据冻结 (30 天)
                                         ↓
                                   完整删除 (向量 + DB + 缓存 + 备份 + log)
                                         ↓
                                   合规归档 (法规要求保留期)
```

## 12. 反模式
1. ❌ 共享 DB + tenant_id 但漏写 WHERE
2. ❌ 向量库纯 metadata filter 不带 namespace
3. ❌ Redis key 不带 tenant 前缀
4. ❌ 工程师手写 query 绕过 ORM
5. ❌ 测试不覆盖跨租户
6. ❌ 配额不分租户，单租户打挂全站
7. ❌ Audit log 一锅炖
8. ❌ 升级 / 迁移时丢隔离
9. ❌ 跨租户共享资源没显式同意
10. ❌ 删除 tenant 不级联

## 13. 实施清单
- [ ] tenant 模型 + 强制 ORM 中间件
- [ ] Postgres RLS 启用所有业务表
- [ ] 向量库租户隔离（按选型）
- [ ] Redis key 前缀策略
- [ ] K8s namespace + ResourceQuota per high-tier
- [ ] LLM 配额引擎
- [ ] 字段级加密 + KMS 集成
- [ ] BYOK 支持（大客户）
- [ ] Audit log 物理分区
- [ ] 跨租户测试套件 (CI)
- [ ] tenant 删除级联 SOP
- [ ] 季度隔离演练
