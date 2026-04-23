"""SemanticCache (InMemory) 测试."""

import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

from rag_core.cache.semantic_cache import (
    InMemorySemanticCache,
    SemanticCacheEntry,
    make_cache_key,
)

T1 = UUID("00000000-0000-0000-0000-000000000001")
T2 = UUID("00000000-0000-0000-0000-000000000002")


def _entry(*, key: str, tenant: UUID = T1, vec=None, answer="cached") -> SemanticCacheEntry:
    return SemanticCacheEntry(
        cache_key=key, tenant_id=tenant,
        query_text="q", query_embedding=vec or [1.0] + [0.0] * 1023,
        answer=answer,
    )


def test_cache_key_stable_for_same_inputs():
    k1 = make_cache_key(tenant_id=T1, query="hello world", principals=["user:U1"])
    k2 = make_cache_key(tenant_id=T1, query="hello world", principals=["user:U1"])
    assert k1 == k2 and len(k1) == 64


def test_cache_key_differs_when_tenant_or_acl_differs():
    base_q = "same query"
    k_t1_acl1 = make_cache_key(tenant_id=T1, query=base_q, principals=["a"])
    k_t2_acl1 = make_cache_key(tenant_id=T2, query=base_q, principals=["a"])
    k_t1_acl2 = make_cache_key(tenant_id=T1, query=base_q, principals=["b"])
    assert len({k_t1_acl1, k_t2_acl1, k_t1_acl2}) == 3


def test_cache_key_word_order_irrelevant():
    a = make_cache_key(tenant_id=T1, query="hello world", principals=["x"])
    b = make_cache_key(tenant_id=T1, query="world hello", principals=["x"])
    assert a == b


def test_exact_hit_returns_entry_and_bumps_count():
    c = InMemorySemanticCache()
    e = _entry(key="k1")
    c.put(e)
    out = c.get(cache_key="k1", query_embedding=None, tenant_id=T1)
    assert out is not None and out.answer == "cached"
    assert out.hit_count == 1


def test_exact_miss_then_approximate_hit():
    c = InMemorySemanticCache(threshold=0.97)
    v = [1.0] + [0.0] * 1023      # 已 normalize
    c.put(_entry(key="k1", vec=v))
    # 不同 key 但近邻向量
    out = c.get(cache_key="other_key", query_embedding=v, tenant_id=T1)
    assert out is not None and out.cache_key == "k1"


def test_approximate_below_threshold_misses():
    c = InMemorySemanticCache(threshold=0.97)
    v1 = [1.0] + [0.0] * 1023
    v2 = [0.0, 1.0] + [0.0] * 1022       # 正交
    c.put(_entry(key="k1", vec=v1))
    out = c.get(cache_key="other", query_embedding=v2, tenant_id=T1)
    assert out is None


def test_tenant_isolation_blocks_cross_tenant_hit():
    c = InMemorySemanticCache()
    v = [1.0] + [0.0] * 1023
    c.put(_entry(key="k1", tenant=T1, vec=v))
    # T2 用同样 key OR 同样 vec, 都不应命中
    assert c.get(cache_key="k1", query_embedding=None, tenant_id=T2) is None
    assert c.get(cache_key="other", query_embedding=v, tenant_id=T2) is None


def test_eviction_clears_expired():
    c = InMemorySemanticCache()
    e = _entry(key="k1")
    e.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    c.put(e)
    # put 会重置 expires_at; 我们要 bypass 它
    c._by_key["k1"].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    n = c.evict_expired()
    assert n == 1 and c.size() == 0


def test_expired_entry_is_not_returned():
    c = InMemorySemanticCache()
    e = _entry(key="k1")
    c.put(e)
    c._by_key["k1"].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    out = c.get(cache_key="k1", query_embedding=None, tenant_id=T1)
    assert out is None
