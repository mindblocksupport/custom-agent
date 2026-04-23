-- L37 RAG 5 表 schema (Day 9)
-- 与 docs/37-rag-implementation-plan.md §8.1 完全对齐
--
-- 运行方式 (新建库时):
--   docker compose exec postgres psql -U agent -d agent -f /docker-entrypoint-initdb.d/001_rag.sql
-- 或 (映射后) 容器启动自动加载

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;     -- gen_random_uuid()

-- ============================================================
-- 1. rag_docs : 文档主表 (doc 级元数据 + 软删 + ACL)
-- ============================================================
CREATE TABLE IF NOT EXISTS rag_docs (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL,
  source_uri      TEXT NOT NULL,
  source_type     TEXT NOT NULL,                 -- file / confluence / notion / ...
  title           TEXT,
  checksum        CHAR(64) NOT NULL,             -- 整文档 sha256
  current_version INT NOT NULL DEFAULT 1,
  status          TEXT NOT NULL DEFAULT 'published',  -- draft / published / archived
  acl             TEXT[] NOT NULL DEFAULT '{}',  -- ['user:U1','group:G2','role:R3']
  metadata        JSONB NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at      TIMESTAMPTZ,                   -- doc 级软删
  UNIQUE (tenant_id, source_uri)
);
CREATE INDEX IF NOT EXISTS rag_docs_tenant_status_idx
  ON rag_docs (tenant_id, status) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS rag_docs_acl_idx ON rag_docs USING gin (acl);

-- ============================================================
-- 2. rag_doc_versions : 文档历史版本 (支持回滚 N-1)
-- ============================================================
CREATE TABLE IF NOT EXISTS rag_doc_versions (
  doc_id      UUID NOT NULL REFERENCES rag_docs(id) ON DELETE CASCADE,
  version     INT NOT NULL,
  checksum    CHAR(64) NOT NULL,
  parsed_md   TEXT,                              -- 原始解析 markdown
  archived_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (doc_id, version)
);

-- ============================================================
-- 3. rag_chunks : chunk 表 (含 embedding + ACL + 增量 upsert key)
-- ============================================================
CREATE TABLE IF NOT EXISTS rag_chunks (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  doc_id                   UUID NOT NULL REFERENCES rag_docs(id) ON DELETE CASCADE,
  tenant_id                UUID NOT NULL,        -- 一等列, 索引分租户分区
  parent_id                UUID,                 -- 父块 id (parent-child, Day 12)
  chunk_seq                INT NOT NULL,         -- doc 内序号
  doc_version              INT NOT NULL,
  content                  TEXT NOT NULL,
  content_hash             CHAR(64) NOT NULL,    -- sha256(content), 增量 diff
  embedding_v1             VECTOR(1024),         -- Qwen3-Embedding-0.6B
  embedding_v2             VECTOR(2560),         -- Qwen3-Embedding-4B (升级时双写)
  embedding_model_version  TEXT NOT NULL DEFAULT 'qwen3-0.6b-v1',
  metadata                 JSONB NOT NULL DEFAULT '{}',
  page                     INT,                  -- PDF 页码 (引用结构)
  char_offset_start        INT,
  char_offset_end          INT,
  is_quarantined           BOOLEAN NOT NULL DEFAULT FALSE,  -- prompt injection 检出
  is_deleted               BOOLEAN NOT NULL DEFAULT FALSE,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (doc_id, chunk_seq, doc_version)
);

-- HNSW 索引 (cosine), 仅对未删 + 未隔离生效
CREATE INDEX IF NOT EXISTS rag_chunks_emb_v1_hnsw_idx
  ON rag_chunks USING hnsw (embedding_v1 vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS rag_chunks_tenant_doc_idx
  ON rag_chunks (tenant_id, doc_id) WHERE NOT is_deleted;

CREATE INDEX IF NOT EXISTS rag_chunks_metadata_gin_idx
  ON rag_chunks USING gin (metadata);

-- BM25 用 Postgres 原生 tsvector (Day 10 切 pgroonga + jieba)
ALTER TABLE rag_chunks ADD COLUMN IF NOT EXISTS tsv tsvector;
CREATE INDEX IF NOT EXISTS rag_chunks_tsv_idx ON rag_chunks USING gin (tsv);

CREATE OR REPLACE FUNCTION rag_chunks_tsv_trigger() RETURNS trigger AS $$
BEGIN
  NEW.tsv := to_tsvector('simple', COALESCE(NEW.content, ''));
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS rag_chunks_tsv_update ON rag_chunks;
CREATE TRIGGER rag_chunks_tsv_update
  BEFORE INSERT OR UPDATE OF content ON rag_chunks
  FOR EACH ROW EXECUTE FUNCTION rag_chunks_tsv_trigger();

-- ============================================================
-- 4. rag_query_cache : 语义缓存 (key 含 tenant_id + acl_hash 防越权)
-- ============================================================
CREATE TABLE IF NOT EXISTS rag_query_cache (
  cache_key       CHAR(64) PRIMARY KEY,         -- sha256(tenant_id|query_norm|acl_hash)
  tenant_id       UUID NOT NULL,
  query_text      TEXT NOT NULL,
  query_embedding VECTOR(1024) NOT NULL,
  answer          TEXT NOT NULL,
  citations       JSONB NOT NULL DEFAULT '[]',
  hit_count       INT NOT NULL DEFAULT 0,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at      TIMESTAMPTZ NOT NULL          -- TTL 24h
);
CREATE INDEX IF NOT EXISTS rag_query_cache_emb_hnsw_idx
  ON rag_query_cache USING hnsw (query_embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS rag_query_cache_expires_idx
  ON rag_query_cache (expires_at);

-- ============================================================
-- 5. rag_eval_badcases : 失败 case 自动归集 (周会 review)
-- ============================================================
CREATE TABLE IF NOT EXISTS rag_eval_badcases (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  trace_id            TEXT NOT NULL,
  tenant_id           UUID NOT NULL,
  query               TEXT NOT NULL,
  answer              TEXT NOT NULL,
  retrieved_chunk_ids UUID[] NOT NULL,
  faithfulness_score  REAL,
  user_feedback       TEXT,                     -- thumb_down / wrong_answer / ...
  reviewed            BOOLEAN NOT NULL DEFAULT FALSE,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS rag_eval_badcases_unreviewed_idx
  ON rag_eval_badcases (created_at) WHERE NOT reviewed;
