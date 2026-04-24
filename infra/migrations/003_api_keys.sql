-- Day 1 (P0 #3): api_keys 表 — API key 与 (tenant_id, actor_id, principals) 的绑定.
-- 设计要点 (L37 §8.2 + per-call ACL 调研):
-- - 只存 key 的 sha256, 永远不存明文 (即使 DB 泄漏也不能直接用)
-- - principals 是 text[] 直接进 ACL 过滤 (与 rag_docs.acl 同结构)
-- - revoked_at 软撤销, 不删行 (审计)

CREATE TABLE IF NOT EXISTS api_keys (
  key_hash    CHAR(64) PRIMARY KEY,                 -- sha256 hex of raw key
  tenant_id   UUID NOT NULL,
  actor_id    TEXT NOT NULL,                        -- 用户/服务账户 id
  principals  TEXT[] NOT NULL DEFAULT '{}',         -- ['user:U1','group:eng','role:viewer']
  label       TEXT,                                 -- 人类可读标签 (debug 用)
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_used_at TIMESTAMPTZ,
  revoked_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS api_keys_tenant_idx
  ON api_keys (tenant_id) WHERE revoked_at IS NULL;
