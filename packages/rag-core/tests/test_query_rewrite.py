"""HyDE + MultiQuery 用 StubLLMClient 跑通 (不联网)."""

import asyncio
from uuid import uuid4

from rag_core.config import DEFAULT_PRINCIPALS, DEFAULT_TENANT_ID
from rag_core.embedding.hash_backend import HashEmbedding
from rag_core.llm.stub_backend import StubLLMClient
from rag_core.retrieval.hybrid import HybridRetriever
from rag_core.retrieval.hyde import HyDERetriever
from rag_core.retrieval.multi_query import MultiQueryRetriever
from rag_core.storage.in_memory_store import InMemoryStore
from rag_core.tokenize.jieba_tokenizer import tokenize_for_bm25
from rag_core.types import Chunk


def _seed():
    store = InMemoryStore()
    emb = HashEmbedding()
    doc_id = store.add_doc(title="d", source_uri="x", acl=DEFAULT_PRINCIPALS)
    chunks = []
    for i, t in enumerate(["kubernetes deploy", "RAG retrieval", "prompt engineering"]):
        ev = emb.encode([t])[0]
        chunks.append(Chunk(
            id=uuid4(), doc_id=doc_id, tenant_id=DEFAULT_TENANT_ID,
            chunk_seq=i, doc_version=1, content=t,
            content_hash="0" * 64, embedding=ev,
            bm25_tokens=tokenize_for_bm25(t),
        ))
    store.add_chunks(chunks)
    return store, emb


def test_hyde_calls_llm_and_returns_hits():
    store, emb = _seed()
    llm = StubLLMClient(default_text="hypothetical: kubernetes deployment guide")
    hyde = HyDERetriever(store=store, embedder=emb, llm=llm, model="stub")
    hits = asyncio.run(hyde.search(
        query="how to deploy k8s",
        tenant_id=DEFAULT_TENANT_ID, principals=DEFAULT_PRINCIPALS, k=3,
    ))
    assert isinstance(hits, list)
    assert len(llm.calls) == 1


def test_multiquery_generates_variants_and_fuses():
    store, emb = _seed()
    base = HybridRetriever(store, emb, reranker=None, refusal_threshold=0.0)
    llm = StubLLMClient()  # stub returns "变体一\n变体二\n变体三"
    mq = MultiQueryRetriever(base=base, llm=llm, model="stub", num_variants=3)
    res = asyncio.run(mq.search(
        query="rewrite this please",   # stub picks "rewrite" branch
        tenant_id=DEFAULT_TENANT_ID, principals=DEFAULT_PRINCIPALS, k=2,
    ))
    # 4 次检索 (1 原 + 3 变体)
    assert len(llm.calls) == 1     # 1 LLM call to generate variants
    assert isinstance(res.hits, list)
