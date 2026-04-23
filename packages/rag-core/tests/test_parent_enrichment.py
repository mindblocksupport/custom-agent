"""HybridRetriever.enrich_parents + InMemoryStore.fetch_parents 联调."""

from uuid import uuid4

from rag_core.config import DEFAULT_PRINCIPALS, DEFAULT_TENANT_ID
from rag_core.embedding.hash_backend import HashEmbedding
from rag_core.retrieval.hybrid import HybridRetriever
from rag_core.storage.in_memory_store import InMemoryStore
from rag_core.tokenize.jieba_tokenizer import tokenize_for_bm25
from rag_core.types import Chunk


def _seed_pc_store():
    """造一个 doc, 1 父 + 2 子, parent_id 已连."""
    store = InMemoryStore()
    emb = HashEmbedding()
    doc_id = store.add_doc(title="父子文档", source_uri="doc:pc",
                            acl=DEFAULT_PRINCIPALS)
    parent_id = uuid4()
    parent_content = "父块: 这是关于 kubernetes 部署的完整章节, 包括 namespace 和 service."
    children_text = ["kubernetes 部署需要 namespace.", "service 暴露 ClusterIP."]
    parent_chunk = Chunk(
        id=parent_id, doc_id=doc_id, tenant_id=DEFAULT_TENANT_ID,
        chunk_seq=0, doc_version=1, content=parent_content,
        content_hash="0" * 64, embedding=None, bm25_tokens=None,
        metadata={"role": "parent"},
    )
    store.add_chunks([parent_chunk])
    child_chunks = []
    for i, t in enumerate(children_text):
        emb_v = emb.encode([t])[0]
        child_chunks.append(Chunk(
            doc_id=doc_id, tenant_id=DEFAULT_TENANT_ID,
            chunk_seq=1 + i, parent_id=parent_id, doc_version=1,
            content=t, content_hash="0" * 64, embedding=emb_v,
            bm25_tokens=tokenize_for_bm25(t),
            metadata={"role": "child"},
        ))
    store.add_chunks(child_chunks)
    return store, emb


def test_fetch_parents_returns_parent_content():
    store, _ = _seed_pc_store()
    children = [c for c in store.chunks if c.metadata.get("role") == "child"]
    cids = [c.id for c in children]
    out = store.fetch_parents(cids)
    assert len(out) == 2
    for cid in cids:
        assert "父块" in out[cid]


def test_hybrid_enriches_parent_content():
    store, emb = _seed_pc_store()
    hr = HybridRetriever(
        store, emb, reranker=None, refusal_threshold=0.0,
        enrich_parents=True,
    )
    res = hr.search(
        query="kubernetes namespace",
        tenant_id=DEFAULT_TENANT_ID, principals=DEFAULT_PRINCIPALS, k=2,
    )
    assert res.hits, "expected at least one hit"
    # 至少一个命中 child 已经被填了 parent_content
    has_parent = any(h.parent_content and "父块" in h.parent_content for h in res.hits)
    assert has_parent


def test_hybrid_skip_enrichment_when_disabled():
    store, emb = _seed_pc_store()
    hr = HybridRetriever(
        store, emb, reranker=None, refusal_threshold=0.0,
        enrich_parents=False,
    )
    res = hr.search(
        query="kubernetes",
        tenant_id=DEFAULT_TENANT_ID, principals=DEFAULT_PRINCIPALS, k=2,
    )
    assert res.hits
    assert all(h.parent_content is None for h in res.hits)


def test_citation_uses_parent_when_present():
    """SearchHit.to_citation 应优先用 parent_content 做 snippet."""
    store, emb = _seed_pc_store()
    hr = HybridRetriever(store, emb, reranker=None, refusal_threshold=0.0)
    res = hr.search(query="kubernetes", tenant_id=DEFAULT_TENANT_ID,
                    principals=DEFAULT_PRINCIPALS, k=1)
    assert res.hits
    cit = res.hits[0].to_citation()
    if res.hits[0].parent_content:
        assert "父块" in cit.snippet
