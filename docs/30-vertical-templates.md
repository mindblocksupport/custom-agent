# L30 · 垂直行业模板

> 状态：**讨论中** · v0.1 · 2026-04-22 · 加速 GTM 的核心杠杆

## 0. 为什么独立成章
- 垂直 Agent 100× 收入倍数（Sierra / Cursor / Clay）
- 客户买的是"懂我们行业"，不是通用平台
- 模板 = onboarding 从 12 周 → 4 周

## 1. 模板组成（每垂直）

每垂直模板 = 6 件套：
1. **预置 Skill 库** (30-100 个)
2. **预置 Tool 集** (10-30 个企业系统接入)
3. **行业 Knowledge Base 模板** (法规 / 标准 / 模板文档)
4. **预置 Eval Set** (200-500 case)
5. **预置 HITL Workflow** (审批节点 + 通知模板)
6. **行业 Dashboard / 报表**

## 2. 客服 (Customer Support)

**对标**：Sierra / Decagon / Cresta / Ada

### Skills
- 订单查询 / 修改 / 取消
- 退换 / 退款（含金额阈值 HITL）
- 物流跟踪
- 投诉处理（情感识别 + 升级）
- 产品问答（基于产品 KB）
- 优惠券 / 积分查询
- 转人工（含 context 摘要）

### Tools
- CRM (Salesforce / 钉钉 CRM / 销售易)
- 工单 (Zendesk / Freshdesk / 工单系统)
- 物流 API
- 支付 / 退款 API
- 邮件 / 短信
- IM (微信 / 钉钉 / 飞书)

### KPI
- 一次解决率 (FCR)
- 平均处理时长 (AHT)
- CSAT / NPS
- 转人工率
- Cost per conversation
- 节省 FTE

### 合规
- 录音 / 录屏 + 保留
- PII 脱敏
- 投诉升级 SOP

## 3. 销售 / SDR

**对标**：Clay / Apollo / 11x / Tavus

### Skills
- 潜客挖掘 (web / LinkedIn / 公开数据)
- 资料丰富 (BD 信息 / 联系人 / 公司画像)
- 个性化外联 (邮件 / 话术生成)
- 客户分级 / 评分
- 报价 / 方案生成
- CRM 自动维护
- 会议纪要 / Action item 提取

### Tools
- LinkedIn Sales Nav / 脉脉
- 企查查 / Crunchbase
- CRM (Salesforce / HubSpot)
- 邮件 (Outlook / Gmail)
- 日历
- 视频会议 (Zoom / 飞书 / 腾讯会议)

### KPI
- 触达数 / 回复率 / 转化率
- pipeline 价值
- closed-won 率
- AE 节省时间

## 4. 法务 (Legal)

### Skills
- 合同审核（标准条款偏离 + 风险）
- 合同生成（基于模板）
- 案例查询（Westlaw / 北大法宝）
- 法规对照
- 法律研究备忘录
- 诉讼材料整理
- 知产监测

### Tools
- 合同管理系统
- 案例库 API (Westlaw / 北大法宝)
- 文档对比工具
- 电子签 (DocuSign / 法大大)
- 知产数据库

### 高风险 → HITL 必经
- 任何对外签字
- 重大合同（超额）
- 诉讼立场

### 合规
- 律师 client privilege
- 数据本地化（律所敏感）

## 5. 财务 / 会计

### Skills
- 发票 OCR + 录入
- 报销审批
- 对账（多系统）
- 财报生成
- 异常交易标记
- 税务计算
- 应收应付分析

### Tools
- ERP (SAP / 用友 / 金蝶 / Oracle)
- 银行 API
- 税务系统
- BI (Tableau / Power BI / 帆软)
- Excel 处理

### HITL
- 任何资金动作（无论金额）
- 报表对外发布
- 税务申报

### 合规
- 金融监管
- 国密
- 审计 trail 5+ 年

## 6. 医疗 (Healthcare)

### Skills
- 病历摘要
- 用药推荐（辅助，非诊断）
- 影像辅助阅片
- 预约 / 排班
- 保险核销
- 患者沟通
- 临床试验匹配

### Tools
- HIS / EMR 系统
- LIS (检验)
- PACS (影像)
- 医保 API
- 药品库

### 极高 HITL
- 任何诊断 / 处方 → 医生确认
- 用药建议 → 医生 review

### 合规
- HIPAA / PHI
- 中国医疗信息化标准
- 医师法
- 数据本地化（医疗数据出境严控）

## 7. 编程 / DevOps

**对标**：Cursor / Cognition / GitHub Copilot

### Skills
- 代码生成 / 改写
- bug 定位 + 修复
- code review
- 单元测试生成
- 文档生成
- 重构建议
- migration (Java 8 → 17 类)
- 故障诊断 (运维)
- 日志查询
- 监控告警关联
- runbook 自动化

### Tools
- Git / GitHub / GitLab
- IDE (VS Code / JetBrains)
- CI/CD (Jenkins / GitHub Actions / ArgoCD)
- 监控 (Prometheus / Datadog / Grafana)
- 日志 (ELK / Loki)
- 工单 (Jira)
- 配置管理 (Ansible / Terraform)

### HITL
- 生产部署
- 数据库 migration
- 删除 / 回滚操作

## 8. 人力资源 (HR)

### Skills
- JD 生成
- 简历筛选
- 面试安排
- 入离职手续
- 薪酬查询（敏感权限）
- 培训推荐
- 政策问答
- 考勤异常处理

### Tools
- HRIS (Workday / SAP SuccessFactors / 北森 / Moka)
- ATS (招聘系统)
- 考勤系统
- 培训平台
- IM

### HITL
- 招聘决定
- 薪酬调整
- 处罚 / 离职

## 9. 制造 / 供应链

### Skills
- 库存查询
- 采购单生成
- 供应商沟通
- 质检报告分析
- 生产计划辅助
- 物流跟踪
- 设备维护排程

### Tools
- ERP (SAP / 用友)
- MES (生产管理)
- WMS (仓储)
- TMS (运输)
- IoT 设备

### HITL
- 大额采购
- 紧急停产
- 供应商替换

## 10. 政务 / 公共服务

### Skills
- 政策问答
- 办事指南
- 表单填写辅助
- 投诉处理
- 数据查询（按权限）

### Tools
- 政务系统（信创栈）
- 民生数据库
- 公开数据 API

### 极严合规
- 等保三级 +
- 信创全栈
- 数据不出域
- 内容安全（GB/T 45654）
- 政治敏感词严控

## 11. 模板交付包结构

```
templates/
  ├─ customer_support/
  │   ├─ skills/         (30+ SKILL.md)
  │   ├─ tools/          (15+ tool config)
  │   ├─ knowledge/      (KB 模板)
  │   ├─ eval/           (300+ test case)
  │   ├─ hitl/           (workflow yaml)
  │   ├─ dashboard/      (Grafana / Superset)
  │   └─ README.md
  ├─ sales/
  ├─ legal/
  ├─ finance/
  ├─ healthcare/
  ├─ engineering/
  ├─ hr/
  ├─ manufacturing/
  └─ government/
```

## 12. 客户定制路径

```
通用模板
   ↓
客户 Discovery
   ↓
模板适配 (改 prompt / KB / tool)
   ↓
客户专属 skill (10-30 个)
   ↓
客户 eval set
   ↓
Pilot
```

## 13. 实施清单
- [ ] 选 2-3 个先行垂直 (建议: 客服 + 销售 / 编程)
- [ ] 每个垂直 6 件套齐全
- [ ] 内部 demo 跑通
- [ ] 1-2 友好客户 pilot
- [ ] 模板 vs 客户专属比例文档化（80/20 目标）
- [ ] 行业 SME 签约 (顾问 / 兼职)
- [ ] 定期模板升级（季度）
