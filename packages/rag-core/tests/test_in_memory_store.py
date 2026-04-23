"""InMemoryStore + Hybrid 集成测试 (无 PG 依赖)."""

from uuid import uuid4

from rag_core.config import DEFAULT_PRINCIPALS, DEFAULT_TENANT_ID
from rag_core.embedding.hash_backend import HashEmbedding
from rag_core.reranker.hash_backend import HashReranker
from rag_core.retrieval.bm25 import BM25Retriever
from rag_core.retrieval.dense import DenseRetriever
from rag_core.retrieval.hybrid import HybridRetriever
from rag_core.storage.in_memory_store import InMemoryStore
from rag_core.tokenize.jieba_tokenizer import tokenize_for_bm25
from rag_core.types import Chunk


def _seed_store():
    store = InMemoryStore()
    emb = HashEmbedding()
    docs = [
        ("rag-core 怎么洗数据", "ingest 阶段做清洗 + 去重 + ACL 注入"),
        ("k8s 部署指南", "kubectl apply -f, kubernetes 集群部署"),
        ("React 渲染优化", "useMemo + useCallback + virtualization"),
    ]
    for title, body in docs:
        doc_id = store.add_doc(title=title, source_uri=f"doc:{title}", acl=DEFAULT_PRINCIPALS)
        embeddings = emb.encode([body])
        store.add_chunks([
            Chunk(
                id=uuid4(), doc_id=doc_id, tenant_id=DEFAULT_TENANT_ID,
                chunk_seq=0, doc_version=1, content=body,
                content_hash="0" * 64, embedding=embeddings[0],
                bm25_tokens=tokenize_for_bm25(body),
            ),
        ])
    return store, emb


def test_acl_blocks_unauthorized():
    store, emb = _seed_store()
    hits = DenseRetriever(store, emb).search(
        query="k8s", tenant_id=DEFAULT_TENANT_ID,
        principals=["user:no-access"], k=5,
    )
    assert hits == []


def test_bm25_finds_keyword():
    store, _ = _seed_store()
    hits = BM25Retriever(store).search(
        query="kubernetes", tenant_id=DEFAULT_TENANT_ID,
        principals=DEFAULT_PRINCIPALS, k=5,
    )
    assert any("k8s" in (h.title or "") or "kubernetes" in h.chunk.content.lower()
               for h in hits)


def test_synonym_expansion_finds_kubernetes_via_k8s():
    store, _ = _seed_store()
    hits = BM25Retriever(store, expand_synonyms=True).search(
        query="k8s",  # 应该通过同义词找到 kubernetes 文档
        tenant_id=DEFAULT_TENANT_ID, principals=DEFAULT_PRINCIPALS, k=5,
    )
    titles = [h.title or "" for h in hits]
    assert any("k8s" in t or "kubernetes" in t.lower() for t in titles)


def test_hybrid_returns_result():
    store, emb = _seed_store()
    hr = HybridRetriever(store, emb, reranker=None, refusal_threshold=0.0)
    res = hr.search(
        query="kubernetes 怎么部署",
        tenant_id=DEFAULT_TENANT_ID, principals=DEFAULT_PRINCIPALS, k=3,
    )
    assert not res.refused
    assert len(res.hits) > 0
    assert res.n_dense > 0 or res.n_bm25 > 0


def test_hybrid_refusal_when_no_candidates():
    store, emb = _seed_store()
    hr = HybridRetriever(
        store, emb, reranker=HashReranker(), refusal_threshold=0.99,
    )
    res = hr.search(
        query="some random query",
        tenant_id=DEFAULT_TENANT_ID, principals=DEFAULT_PRINCIPALS, k=3,
    )
    # 阈值 0.99 几乎不可能命中, 应该拒答
    assert res.refused
    assert res.refusal_reason is not None
