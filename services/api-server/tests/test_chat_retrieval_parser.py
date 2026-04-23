"""api-server: 验证 search_kb wrapped 文本 → CitationData 解析."""

from api_server.routes.chat import _parse_citations_from_search_kb


def test_empty_text_is_refusal():
    cs, refused = _parse_citations_from_search_kb("")
    assert cs == [] and refused is True


def test_refusal_string_is_refusal():
    cs, refused = _parse_citations_from_search_kb("知识库无相关内容。请改写问题或转人工。")
    assert cs == [] and refused is True


def test_single_citation_parsed():
    text = (
        "header...\n"
        '<retrieved_context source="doc:abc#chunk:c1" page="3" title="Doc A">\n'
        "片段一\n"
        "</retrieved_context>"
    )
    cs, refused = _parse_citations_from_search_kb(text)
    assert refused is False
    assert len(cs) == 1
    c = cs[0]
    assert c.doc_id == "abc" and c.chunk_id == "c1"
    assert c.page == 3 and c.title == "Doc A"
    assert "片段一" in c.snippet


def test_two_citations_parsed_in_order():
    text = (
        '<retrieved_context source="doc:a#chunk:1">A1</retrieved_context>\n'
        '<retrieved_context source="doc:b#chunk:2">B2</retrieved_context>'
    )
    cs, refused = _parse_citations_from_search_kb(text)
    assert refused is False
    assert [c.doc_id for c in cs] == ["a", "b"]
    assert [c.chunk_id for c in cs] == ["1", "2"]


def test_malformed_source_skipped():
    text = (
        '<retrieved_context source="garbage">x</retrieved_context>\n'
        '<retrieved_context source="doc:ok#chunk:1">y</retrieved_context>'
    )
    cs, _ = _parse_citations_from_search_kb(text)
    # 第一个被跳过, 第二个保留
    assert len(cs) == 1 and cs[0].doc_id == "ok"
