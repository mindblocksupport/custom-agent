"""ContextualEnricher 用 stub LLM 测."""

import asyncio
from pathlib import Path

from rag_core.chunking.contextual import ContextualEnricher
from rag_core.chunking.recursive import chunk_text
from rag_core.llm.stub_backend import StubLLMClient


def test_enrich_prepends_context_to_each_chunk(tmp_path: Path):
    # 用各自独立内容, 避免 content_hash 重叠导致 cache 复用
    text = "# H\n" + "\n\n".join(f"chunk #{i} 独立内容. " + ("ABC " * 30)
                                  for i in range(4))
    spans = chunk_text(text, target_chars=120, overlap_chars=0)
    assert len(spans) >= 4

    llm = StubLLMClient()
    enricher = ContextualEnricher(
        llm=llm, model="stub", max_tokens=50,
        cache_dir=tmp_path / "ctx_cache", max_concurrent=2,
    )
    out = asyncio.run(enricher.enrich(
        doc_text=text, doc_checksum="checksum-abc", chunks=spans,
    ))
    assert len(out) == len(spans)
    for i, span in enumerate(out):
        assert span.content.endswith(spans[i].content)
        assert len(span.content) > len(spans[i].content)
    # 每条独立 content 应触发 1 次 LLM call (无 cache 命中)
    distinct_hashes = {s.content_hash for s in spans}
    assert len(llm.calls) == len(distinct_hashes)


def test_enrich_uses_cache_on_second_call(tmp_path: Path):
    text = "# H\nshort body"
    spans = chunk_text(text, target_chars=200)

    llm1 = StubLLMClient()
    enricher1 = ContextualEnricher(
        llm=llm1, model="stub", cache_dir=tmp_path / "ctx_cache",
    )
    asyncio.run(enricher1.enrich(
        doc_text=text, doc_checksum="cs", chunks=spans,
    ))
    n_calls_first = len(llm1.calls)
    assert n_calls_first == len(spans)

    # 二次跑相同 input → 应该全命中 cache, 0 LLM call
    llm2 = StubLLMClient()
    enricher2 = ContextualEnricher(
        llm=llm2, model="stub", cache_dir=tmp_path / "ctx_cache",
    )
    out = asyncio.run(enricher2.enrich(
        doc_text=text, doc_checksum="cs", chunks=spans,
    ))
    assert len(out) == len(spans)
    assert len(llm2.calls) == 0
