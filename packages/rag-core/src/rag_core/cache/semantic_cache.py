"""Semantic cache (L37 §1 Q4 + Day 13).

两层匹配 (省钱顺序):
1. 精确 key: sha256(tenant|query_norm|acl_hash) → 完全相同 query, 不 embed 不查库
2. 近邻 key: 对 query embedding 做 cosine, top1 > threshold (默认 0.97)

key 必须含 tenant_id + acl_hash, 否则 A 租户的答案漏给 B (越权).

存储: rag_query_cache 表 (Day 9 schema), 字段:
    cache_key, tenant_id, query_text, query_embedding, answer, citations,
    hit_count, expires_at, created_at
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import UUID

from rag_core.tokenize.jieba_tokenizer import tokenize_for_bm25


def _normalize_query(q: str) -> str:
    """词序无关归一化: jieba 分词 + 去重 + 排序 (空格 join)."""
    toks = sorted(set(tokenize_for_bm25(q).split()))
    return " ".join(toks)


def _hash_acl(principals: list[str]) -> str:
    return hashlib.sha256(
        ",".join(sorted(set(principals))).encode("utf-8")
    ).hexdigest()


def make_cache_key(*, tenant_id: UUID, query: str, principals: list[str]) -> str:
    """统一 cache_key 算法 (sha256 hex 64 chars). 必须含 tenant + acl 防越权."""
    payload = f"{tenant_id}|{_normalize_query(query)}|{_hash_acl(principals)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class SemanticCacheEntry:
    cache_key: str
    tenant_id: UUID
    query_text: str
    query_embedding: list[float]
    answer: str                              # 完整 LLM 答案 (chat-level cache 用) 或 wrapped citations 文本
    citations: list[dict[str, Any]] = field(default_factory=list)
    hit_count: int = 0
    expires_at: datetime | None = None
    created_at: datetime | None = None


class SemanticCache(Protocol):
    """两阶段语义缓存."""

    threshold: float
    ttl_hours: int

    def get(
        self, *, cache_key: str, query_embedding: list[float] | None,
        tenant_id: UUID,
    ) -> SemanticCacheEntry | None: ...

    def put(self, entry: SemanticCacheEntry) -> None: ...

    def evict_expired(self) -> int:
        """清理过期, 返回清理数."""
        ...


# ============================================================
# In-memory impl (CI / 单测)
# ============================================================
class InMemorySemanticCache:
    threshold: float = 0.97
    ttl_hours: int = 24

    def __init__(
        self,
        *,
        threshold: float = 0.97,
        ttl_hours: int = 24,
    ) -> None:
        self.threshold = threshold
        self.ttl_hours = ttl_hours
        self._by_key: dict[str, SemanticCacheEntry] = {}

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def get(
        self, *, cache_key: str, query_embedding: list[float] | None,
        tenant_id: UUID,
    ) -> SemanticCacheEntry | None:
        # 1) 精确命中
        ent = self._by_key.get(cache_key)
        if ent and (ent.expires_at is None or ent.expires_at > self._now()):
            if ent.tenant_id != tenant_id:
                return None  # 防越权 (理论上 cache_key 已含 tenant, 双保险)
            ent.hit_count += 1
            return ent

        # 2) 近邻 (按 cosine, 仅同 tenant)
        if query_embedding is None:
            return None
        best: tuple[float, SemanticCacheEntry] | None = None
        for e in self._by_key.values():
            if e.tenant_id != tenant_id:
                continue
            if e.expires_at is not None and e.expires_at <= self._now():
                continue
            cos = sum(a * b for a, b in zip(query_embedding, e.query_embedding))
            # 假设 embedding 已 normalize, cos∈[-1,1]
            if best is None or cos > best[0]:
                best = (cos, e)
        if best and best[0] >= self.threshold:
            best[1].hit_count += 1
            return best[1]
        return None

    def put(self, entry: SemanticCacheEntry) -> None:
        if entry.expires_at is None:
            entry.expires_at = self._now() + timedelta(hours=self.ttl_hours)
        if entry.created_at is None:
            entry.created_at = self._now()
        self._by_key[entry.cache_key] = entry

    def evict_expired(self) -> int:
        now = self._now()
        keys = [k for k, v in self._by_key.items()
                if v.expires_at is not None and v.expires_at <= now]
        for k in keys:
            del self._by_key[k]
        return len(keys)

    def size(self) -> int:
        return len(self._by_key)


# ============================================================
# Postgres impl (生产; 用 Day 9 schema rag_query_cache)
# ============================================================
class PgSemanticCache:
    threshold: float = 0.97
    ttl_hours: int = 24

    def __init__(
        self,
        db_url: str,
        *,
        threshold: float = 0.97,
        ttl_hours: int = 24,
    ) -> None:
        self.db_url = db_url
        self.threshold = threshold
        self.ttl_hours = ttl_hours

    def _conn(self):
        import psycopg
        from pgvector.psycopg import register_vector
        from psycopg.rows import dict_row

        conn = psycopg.connect(self.db_url, row_factory=dict_row)
        register_vector(conn)
        return conn

    def get(
        self, *, cache_key: str, query_embedding: list[float] | None,
        tenant_id: UUID,
    ) -> SemanticCacheEntry | None:
        with self._conn() as conn, conn.cursor() as cur:
            # 1) 精确命中
            cur.execute(
                """
                SELECT cache_key, tenant_id, query_text, query_embedding,
                       answer, citations, hit_count, expires_at, created_at
                FROM rag_query_cache
                WHERE cache_key = %s AND tenant_id = %s AND expires_at > now()
                """,
                (cache_key, str(tenant_id)),
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE rag_query_cache SET hit_count = hit_count + 1 WHERE cache_key = %s",
                    (cache_key,),
                )
                conn.commit()
                return self._row_to_entry(row)

            # 2) 近邻 (仅同 tenant, 未过期)
            if query_embedding is None:
                return None
            cur.execute(
                """
                SELECT cache_key, tenant_id, query_text, query_embedding,
                       answer, citations, hit_count, expires_at, created_at,
                       1 - (query_embedding <=> %s::vector) AS sim
                FROM rag_query_cache
                WHERE tenant_id = %s AND expires_at > now()
                ORDER BY query_embedding <=> %s::vector
                LIMIT 1
                """,
                (query_embedding, str(tenant_id), query_embedding),
            )
            row = cur.fetchone()
            if not row or float(row["sim"]) < self.threshold:
                return None
            cur.execute(
                "UPDATE rag_query_cache SET hit_count = hit_count + 1 WHERE cache_key = %s",
                (row["cache_key"],),
            )
            conn.commit()
            return self._row_to_entry(row)

    def put(self, entry: SemanticCacheEntry) -> None:
        if entry.expires_at is None:
            entry.expires_at = datetime.now(timezone.utc) + timedelta(
                hours=self.ttl_hours
            )
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rag_query_cache
                  (cache_key, tenant_id, query_text, query_embedding, answer,
                   citations, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (cache_key) DO UPDATE SET
                  answer = EXCLUDED.answer,
                  citations = EXCLUDED.citations,
                  expires_at = EXCLUDED.expires_at
                """,
                (
                    entry.cache_key, str(entry.tenant_id), entry.query_text,
                    entry.query_embedding, entry.answer,
                    json.dumps(entry.citations, ensure_ascii=False),
                    entry.expires_at,
                ),
            )
            conn.commit()

    def evict_expired(self) -> int:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM rag_query_cache WHERE expires_at <= now()")
            n = cur.rowcount
            conn.commit()
            return n

    @staticmethod
    def _row_to_entry(row: dict) -> SemanticCacheEntry:
        cits = row["citations"]
        if isinstance(cits, str):
            cits = json.loads(cits)
        emb = row["query_embedding"]
        # pgvector returns numpy array; accept either
        if hasattr(emb, "tolist"):
            emb = emb.tolist()
        return SemanticCacheEntry(
            cache_key=row["cache_key"],
            tenant_id=UUID(str(row["tenant_id"])),
            query_text=row["query_text"],
            query_embedding=list(emb),
            answer=row["answer"],
            citations=list(cits or []),
            hit_count=int(row.get("hit_count", 0) or 0),
            expires_at=row.get("expires_at"),
            created_at=row.get("created_at"),
        )


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """L2-normalized cosine (假设双方已 normalize, 即 dot product). 通用版本带分母."""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)
