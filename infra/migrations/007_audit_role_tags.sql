-- Day n+ : 审计日志 + API key 角色 + 会话标签 (3 件套)
--
-- 1. audit_logs: 谁/何时/对什么/做了什么 - 合规&排错刚需
-- 2. api_keys.role:  admin/editor/viewer - v1 仅做记录, v2 RBAC enforce
-- 3. chat_sessions.tags: 用户自定义标签 - sidebar 按 tag 筛选

-- ---------- audit_logs ----------
CREATE TABLE IF NOT EXISTS audit_logs (
  id           BIGSERIAL PRIMARY KEY,
  tenant_id    UUID NOT NULL,
  actor_id     TEXT NOT NULL,         -- 谁做的
  action       TEXT NOT NULL,         -- key.create / key.revoke / workspace.update / skill.delete / ...
  resource_type TEXT,                 -- 'api_key' / 'workspace' / 'skill' / 'session' / 'kb_doc' / ...
  resource_id  TEXT,                  -- ID (UUID 字符串 / hash / 自定义)
  detail       JSONB NOT NULL DEFAULT '{}',  -- 自由结构 (改前/改后, 标签等)
  ip           TEXT,                  -- 来源 IP (X-Forwarded-For / client.host)
  user_agent   TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_logs_tenant_time_idx
  ON audit_logs (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_logs_actor_time_idx
  ON audit_logs (tenant_id, actor_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_logs_resource_idx
  ON audit_logs (tenant_id, resource_type, resource_id);

-- ---------- api_keys.role ----------
ALTER TABLE api_keys
  ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'admin';
-- 历史 key 默认 admin (= 与之前行为一致); 新建可选

-- ---------- chat_sessions.tags ----------
ALTER TABLE chat_sessions
  ADD COLUMN IF NOT EXISTS tags TEXT[] NOT NULL DEFAULT '{}';
CREATE INDEX IF NOT EXISTS chat_sessions_tags_gin_idx
  ON chat_sessions USING gin (tags);
