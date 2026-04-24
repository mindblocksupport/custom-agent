-- Day 1 (P0 #4): KB 多 collection + 异步 ingest jobs.
-- 设计要点:
-- - rag_docs / rag_chunks 加 collection 列, 兼容历史 (default)
-- - 复合索引 (tenant_id, collection, ...) 让多 KB 切换走索引
-- - ingest_jobs: PG 存任务状态, Arq 只做 Redis 队列; 状态查询走 SQL 一致性更强

ALTER TABLE rag_docs
  ADD COLUMN IF NOT EXISTS collection TEXT NOT NULL DEFAULT 'default';

ALTER TABLE rag_chunks
  ADD COLUMN IF NOT EXISTS collection TEXT NOT NULL DEFAULT 'default';

CREATE INDEX IF NOT EXISTS rag_docs_tenant_collection_idx
  ON rag_docs (tenant_id, collection, status)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS rag_chunks_tenant_collection_idx
  ON rag_chunks (tenant_id, collection)
  WHERE NOT is_deleted;

CREATE TABLE IF NOT EXISTS ingest_jobs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL,
  actor_id      TEXT NOT NULL,
  doc_id        UUID,                       -- 关联 rag_docs (parse 完之后填)
  collection    TEXT NOT NULL DEFAULT 'default',
  source_uri    TEXT NOT NULL,
  source_type   TEXT NOT NULL DEFAULT 'file',
  status        TEXT NOT NULL DEFAULT 'pending', -- pending|parsing|chunking|embedding|done|failed
  progress      INT NOT NULL DEFAULT 0,          -- 0-100
  stage         TEXT,
  error         TEXT,
  bytes_total   BIGINT,
  chunks_created INT NOT NULL DEFAULT 0,
  chunks_reused  INT NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ingest_jobs_tenant_status_idx
  ON ingest_jobs (tenant_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS ingest_jobs_doc_idx
  ON ingest_jobs (doc_id) WHERE doc_id IS NOT NULL;
