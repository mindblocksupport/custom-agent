-- Day n+: per-member budget
-- 业务: workspace 的 owner 给 Bob 限 $5/日, 给 CI bot 限 $50/月.
-- 之前预算只在 workspace 整体维度 (workspace.budget_daily_usd), 现在给到 actor 级.
-- chat 调用拦截优先级: actor budget > workspace budget.

ALTER TABLE workspace_members
  ADD COLUMN IF NOT EXISTS budget_daily_usd   NUMERIC(12,6),
  ADD COLUMN IF NOT EXISTS budget_monthly_usd NUMERIC(12,6);

-- 历史 member 默认 NULL = 不限 (与 workspace.budget_*=NULL 语义一致)
