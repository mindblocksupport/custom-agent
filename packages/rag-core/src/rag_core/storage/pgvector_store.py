"""pgvector store: upsert (含增量 diff) + ACL-aware dense search.

设计要点 (L37 §8.1 / §8.2):
- doc 级 upsert: source_uri 唯一; 检测整文档 checksum 未变直接 noop (省 100% 工作)
- chunk 级 upsert: (doc_id, chunk_seq, doc_version) 唯一; content_hash 未变跳过 embed
- ACL filter: SQL 强制 `acl && principals` (与 principal 集合有交集)
- tenant_id: 强制 SQL 注入 (绝不让 caller 自行传)

Day 9 用 sync psycopg (CLI 场景); Day 11 MCP server 用 asyncio.to_thread 包一下即可。
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Iterator
from uuid import UUID

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from rag_core.types import Chunk, Doc, SearchHit


class PgVectorStore:
    def __init__(self, db_url: str) -> None:
        self.db_url = db_url

    @contextmanager
    def _conn(self) -> Iterator[psycopg.Connection]:
        with psycopg.connect(self.db_url, row_factory=dict_row) as conn:
            register_vector(conn)
            yield conn

    # ---------- doc ----------

    def upsert_doc(self, doc: Doc) -> tuple[UUID, int, bool]:
        """插入或更新文档, 返回 (doc_id, version, changed).

        - 同 (tenant_id, source_uri) 已有 doc 且 checksum 相同 → noop, changed=False
        - checksum 不同 → version+1, 写 rag_doc_versions, 旧 chunks 标 deleted
        - 不存在 → 新建 version=1
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, current_version, checksum
                FROM rag_docs
                WHERE tenant_id = %s AND source_uri = %s AND deleted_at IS NULL
                """,
                (str(doc.tenant_id), doc.source_uri),
            )
            existing = cur.fetchone()

            if existing and existing["checksum"] == doc.checksum:
                return existing["id"], existing["current_version"], False

            if existing:
                # 版本升级: 归档旧版, 软删旧 chunks (新 chunks 进来时新 doc_version)
                new_version = existing["current_version"] + 1
                cur.execute(
                    """
                    INSERT INTO rag_doc_versions (doc_id, version, checksum)
                    VALUES (%s, %s, %s)
                    """,
                    (existing["id"], existing["current_version"], existing["checksum"]),
                )
                cur.execute(
                    """
                    UPDATE rag_docs
                    SET checksum = %s, current_version = %s, title = %s,
                        metadata = %s, acl = %s, status = %s, updated_at = now()
                    WHERE id = %s
                    """,
                    (
                        doc.checksum, new_version, doc.title,
                        json.dumps(doc.metadata), doc.acl, doc.status,
                        existing["id"],
                    ),
                )
                cur.execute(
                    """
                    UPDATE rag_chunks
                    SET is_deleted = TRUE
                    WHERE doc_id = %s AND doc_version < %s
                    """,
                    (existing["id"], new_version),
                )
                conn.commit()
                return existing["id"], new_version, True

            # 新建
            cur.execute(
                """
                INSERT INTO rag_docs
                  (tenant_id, source_uri, source_type, title, checksum,
                   current_version, status, acl, metadata)
                VALUES (%s, %s, %s, %s, %s, 1, %s, %s, %s)
                RETURNING id
                """,
                (
                    str(doc.tenant_id), doc.source_uri, doc.source_type, doc.title,
                    doc.checksum, doc.status, doc.acl, json.dumps(doc.metadata),
                ),
            )
            new_id = cur.fetchone()["id"]
            conn.commit()
            return new_id, 1, True

    # ---------- chunk ----------

    def upsert_chunks(
        self, chunks: list[Chunk]
    ) -> tuple[int, int]:
        """批量 upsert chunks. 返回 (created, reused).

        增量策略 (L37 §8.1):
        - 同 (doc_id, chunk_seq, doc_version) 不存在 → 插入
        - 已存在且 content_hash 相同 → 跳过 (reused, 省 embed)
        - 已存在但 content_hash 不同 → 更新内容和向量
        """
        if not chunks:
            return 0, 0
        created = reused = 0
        with self._conn() as conn, conn.cursor() as cur:
            for c in chunks:
                cur.execute(
                    """
                    SELECT id, content_hash FROM rag_chunks
                    WHERE doc_id = %s AND chunk_seq = %s AND doc_version = %s
                    """,
                    (str(c.doc_id), c.chunk_seq, c.doc_version),
                )
                row = cur.fetchone()
                if row and row["content_hash"] == c.content_hash:
                    reused += 1
                    continue

                if row:
                    cur.execute(
                        """
                        UPDATE rag_chunks SET
                          content = %s, content_hash = %s, bm25_tokens = %s,
                          embedding_v1 = %s, embedding_model_version = %s,
                          metadata = %s, page = %s,
                          char_offset_start = %s, char_offset_end = %s,
                          parent_id = %s, is_quarantined = %s, is_deleted = FALSE
                        WHERE id = %s
                        """,
                        (
                            c.content, c.content_hash, c.bm25_tokens,
                            c.embedding, c.embedding_model_version,
                            json.dumps(c.metadata), c.page,
                            c.char_offset_start, c.char_offset_end,
                            str(c.parent_id) if c.parent_id else None,
                            c.is_quarantined, row["id"],
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO rag_chunks
                          (doc_id, tenant_id, parent_id, chunk_seq, doc_version,
                           content, content_hash, bm25_tokens,
                           embedding_v1, embedding_model_version,
                           metadata, page, char_offset_start, char_offset_end, is_quarantined)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(c.doc_id), str(c.tenant_id),
                            str(c.parent_id) if c.parent_id else None,
                            c.chunk_seq, c.doc_version,
                            c.content, c.content_hash, c.bm25_tokens,
                            c.embedding, c.embedding_model_version,
                            json.dumps(c.metadata), c.page,
                            c.char_offset_start, c.char_offset_end, c.is_quarantined,
                        ),
                    )
                created += 1
            conn.commit()
        return created, reused

    # ---------- search ----------

    def dense_search(
        self,
        *,
        tenant_id: UUID,
        query_embedding: list[float],
        principals: list[str],
        k: int = 5,
        filters: dict | None = None,
    ) -> list[SearchHit]:
        """ACL-aware dense 检索 (cosine).

        principals: 用户 + 组 + 角色展开后的字符串集合, e.g. ['user:U1', 'group:G2']
        filters: metadata JSONB 上的过滤 (业务字段, 已 strip 系统字段)
        """
        # cosine distance: <=> 操作符; 距离越小越相似
        # 强制 acl && principals (与用户 principal 集合有交集)
        # embedding_v1 IS NOT NULL → 自动排除父块 (parent-child 模式下父不 embed)
        sql = """
            SELECT
              c.id, c.doc_id, c.tenant_id, c.parent_id, c.chunk_seq, c.doc_version,
              c.content, c.content_hash, c.embedding_model_version,
              c.metadata, c.page, c.char_offset_start, c.char_offset_end,
              c.is_quarantined,
              d.source_uri, d.title,
              1 - (c.embedding_v1 <=> %s::vector) AS score
            FROM rag_chunks c
            JOIN rag_docs d ON d.id = c.doc_id
            WHERE c.tenant_id = %s
              AND c.is_deleted = FALSE
              AND c.is_quarantined = FALSE
              AND d.deleted_at IS NULL
              AND d.status = 'published'
              AND d.acl && %s::text[]
              AND c.embedding_v1 IS NOT NULL
        """
        params: list = [query_embedding, str(tenant_id), principals]

        if filters:
            sql += " AND c.metadata @> %s::jsonb"
            params.append(json.dumps(filters))

        sql += " ORDER BY c.embedding_v1 <=> %s::vector LIMIT %s"
        params.extend([query_embedding, k])

        return self._fetch_hits(sql, params)

    def bm25_search(
        self,
        *,
        tenant_id: UUID,
        query_tokens: str,                   # jieba 预切分后的空格分隔 token 串
        principals: list[str],
        k: int = 5,
        filters: dict | None = None,
    ) -> list[SearchHit]:
        """ACL-aware BM25 检索 (ts_rank).

        query_tokens 来自 tokenize_for_bm25(query) + 同义词扩展.
        用 plainto_tsquery('simple', ...) 防注入.
        """
        if not query_tokens.strip():
            return []
        sql = """
            SELECT
              c.id, c.doc_id, c.tenant_id, c.parent_id, c.chunk_seq, c.doc_version,
              c.content, c.content_hash, c.embedding_model_version,
              c.metadata, c.page, c.char_offset_start, c.char_offset_end,
              c.is_quarantined,
              d.source_uri, d.title,
              ts_rank_cd(c.tsv, plainto_tsquery('simple', %s)) AS score
            FROM rag_chunks c
            JOIN rag_docs d ON d.id = c.doc_id
            WHERE c.tenant_id = %s
              AND c.is_deleted = FALSE
              AND c.is_quarantined = FALSE
              AND d.deleted_at IS NULL
              AND d.status = 'published'
              AND d.acl && %s::text[]
              AND c.tsv @@ plainto_tsquery('simple', %s)
        """
        params: list = [query_tokens, str(tenant_id), principals, query_tokens]

        if filters:
            sql += " AND c.metadata @> %s::jsonb"
            params.append(json.dumps(filters))

        sql += " ORDER BY score DESC LIMIT %s"
        params.append(k)

        return self._fetch_hits(sql, params)

    def fetch_parents(self, chunk_ids: list[UUID]) -> dict[UUID, str]:
        """child chunk_id → parent content. (Day 12 父子模式)"""
        if not chunk_ids:
            return {}
        sql = """
            SELECT c.id AS child_id, p.content AS parent_content
            FROM rag_chunks c
            JOIN rag_chunks p ON p.id = c.parent_id
            WHERE c.id = ANY(%s::uuid[])
              AND p.is_deleted = FALSE
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, ([str(cid) for cid in chunk_ids],))
            return {row["child_id"]: row["parent_content"] for row in cur.fetchall()}

    def _fetch_hits(self, sql: str, params: list) -> list[SearchHit]:
        hits: list[SearchHit] = []
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            for row in cur.fetchall():
                hits.append(
                    SearchHit(
                        chunk=Chunk(
                            id=row["id"],
                            doc_id=row["doc_id"],
                            tenant_id=row["tenant_id"],
                            parent_id=row["parent_id"],
                            chunk_seq=row["chunk_seq"],
                            doc_version=row["doc_version"],
                            content=row["content"],
                            content_hash=row["content_hash"],
                            embedding_model_version=row["embedding_model_version"],
                            metadata=row["metadata"] or {},
                            page=row["page"],
                            char_offset_start=row["char_offset_start"],
                            char_offset_end=row["char_offset_end"],
                            is_quarantined=row["is_quarantined"],
                        ),
                        score=float(row["score"]),
                        source_uri=row["source_uri"],
                        title=row["title"],
                    )
                )
        return hits
