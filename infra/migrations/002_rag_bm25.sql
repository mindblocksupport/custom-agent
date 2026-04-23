-- Day 10: BM25 用 Python jieba 预切分, 落到 bm25_tokens 列
-- pgvector 镜像不带 zhparser/pgroonga; 走 simple parser + 空格分词的 token 串
-- L37 §8.8 长期方案: pgroonga + jieba tokenizer (需自定义 Dockerfile, v2 再换)

ALTER TABLE rag_chunks
  ADD COLUMN IF NOT EXISTS bm25_tokens TEXT;

-- 重建触发器: tsv 优先用 bm25_tokens, 兜底用 content
CREATE OR REPLACE FUNCTION rag_chunks_tsv_trigger() RETURNS trigger AS $$
BEGIN
  NEW.tsv := to_tsvector('simple', COALESCE(NEW.bm25_tokens, NEW.content, ''));
  RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS rag_chunks_tsv_update ON rag_chunks;
CREATE TRIGGER rag_chunks_tsv_update
  BEFORE INSERT OR UPDATE OF content, bm25_tokens ON rag_chunks
  FOR EACH ROW EXECUTE FUNCTION rag_chunks_tsv_trigger();
