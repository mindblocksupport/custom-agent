-- v1.5 沉淀层: workspaces + workspace_members + skills
-- 设计参考 docs/PROJECT-OVERVIEW.md §六 v1.5
--
-- 模型:
--   Tenant > Workspace > [Skill, Collection, Session]
--   每个 workspace 一套 KB 范围/工具白名单/预算/成员
--   Skill 是复用配方 (system_prompt + 工具子集 + 默认 collections)

CREATE TABLE IF NOT EXISTS workspaces (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL,
  name            TEXT NOT NULL,
  description     TEXT NOT NULL DEFAULT '',
  default_model   TEXT NOT NULL DEFAULT 'auto',
  allowed_models  TEXT[] NOT NULL DEFAULT '{}',
  allowed_tools   TEXT[] NOT NULL DEFAULT '{}',
  default_collection  TEXT NOT NULL DEFAULT 'default',
  allowed_collections TEXT[] NOT NULL DEFAULT '{default}',
  budget_daily_usd    NUMERIC(12,4),
  budget_monthly_usd  NUMERIC(12,4),
  features        JSONB NOT NULL DEFAULT '{}',
  created_by      TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at      TIMESTAMPTZ,
  UNIQUE (tenant_id, name)
);
CREATE INDEX IF NOT EXISTS workspaces_tenant_idx
  ON workspaces (tenant_id) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS workspace_members (
  workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  actor_id        TEXT NOT NULL,
  role            TEXT NOT NULL DEFAULT 'viewer',  -- owner / editor / viewer
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (workspace_id, actor_id)
);
CREATE INDEX IF NOT EXISTS workspace_members_actor_idx
  ON workspace_members (actor_id);

CREATE TABLE IF NOT EXISTS skills (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name            TEXT NOT NULL,
  description     TEXT NOT NULL DEFAULT '',
  version         INT NOT NULL DEFAULT 1,
  system_prompt   TEXT NOT NULL DEFAULT '',
  allowed_tools   TEXT[] NOT NULL DEFAULT '{}',          -- 覆盖 workspace.allowed_tools
  default_collections TEXT[] NOT NULL DEFAULT '{}',
  starter_examples    TEXT[] NOT NULL DEFAULT '{}',
  visibility      TEXT NOT NULL DEFAULT 'workspace',     -- private / workspace / public
  budget_per_call_usd NUMERIC(12,6),
  tags            TEXT[] NOT NULL DEFAULT '{}',
  created_by      TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at      TIMESTAMPTZ,
  UNIQUE (workspace_id, name, version)
);
CREATE INDEX IF NOT EXISTS skills_workspace_idx
  ON skills (workspace_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS skills_public_idx
  ON skills (visibility) WHERE visibility = 'public' AND deleted_at IS NULL;

-- 已有表加 workspace_id 列 (允许 NULL, 默认走隐式 default workspace)
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS workspace_id UUID;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS skill_id     UUID;
ALTER TABLE rag_docs      ADD COLUMN IF NOT EXISTS workspace_id UUID;
ALTER TABLE ingest_jobs   ADD COLUMN IF NOT EXISTS workspace_id UUID;

CREATE INDEX IF NOT EXISTS chat_sessions_workspace_idx
  ON chat_sessions (workspace_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS rag_docs_workspace_idx
  ON rag_docs (workspace_id) WHERE deleted_at IS NULL;
