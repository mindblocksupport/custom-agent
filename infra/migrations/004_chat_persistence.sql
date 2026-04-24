-- Day 1 (P0 #7): chat 历史持久化 schema.
-- 设计要点 (KB UI + 持久化调研):
-- - chat_sessions: tenant 隔离 + 软删 + 计数缓存 (避免 COUNT(*) hot path)
-- - chat_messages: JSONB tool_calls (按 session 取最近 N 条, 不按 tool 维度查)
-- - sequence_no 是 session 内严格递增, UNIQUE 防双写
-- - trace_id TEXT 关联 Langfuse, cost/tokens 落每行便于 finops 聚合

CREATE TABLE IF NOT EXISTS chat_sessions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL,
  actor_id        TEXT NOT NULL,
  title           TEXT NOT NULL DEFAULT '',
  message_count   INT NOT NULL DEFAULT 0,
  total_cost_usd  NUMERIC(12, 6) NOT NULL DEFAULT 0,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS chat_sessions_tenant_actor_updated_idx
  ON chat_sessions (tenant_id, actor_id, updated_at DESC)
  WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS chat_messages (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id      UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  sequence_no     INT NOT NULL,
  role            TEXT NOT NULL,                  -- user / assistant / tool / system
  content         TEXT NOT NULL DEFAULT '',
  tool_calls      JSONB,                          -- assistant 行的 tool_calls 数组
  tool_call_id    TEXT,                           -- role=tool 时的关联 id
  tool_name       TEXT,                           -- role=tool 时的 tool name (便利字段)
  trace_id        TEXT,                           -- Langfuse trace 主键
  cost_usd        NUMERIC(12, 6) NOT NULL DEFAULT 0,
  input_tokens    INT NOT NULL DEFAULT 0,
  output_tokens   INT NOT NULL DEFAULT 0,
  model           TEXT,                           -- 实际 LLM (如 deepseek/deepseek-chat)
  metadata        JSONB NOT NULL DEFAULT '{}',    -- 附加: route_reason / refused / ...
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (session_id, sequence_no)
);

CREATE INDEX IF NOT EXISTS chat_messages_session_seq_idx
  ON chat_messages (session_id, sequence_no);

CREATE INDEX IF NOT EXISTS chat_messages_trace_idx
  ON chat_messages (trace_id) WHERE trace_id IS NOT NULL;
