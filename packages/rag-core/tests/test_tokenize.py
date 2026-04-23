"""jieba 分词 + 同义词扩展测试."""

from rag_core.tokenize.jieba_tokenizer import (
    SYNONYMS,
    expand_query_with_synonyms,
    tokenize_for_bm25,
)


def test_chinese_basic():
    out = tokenize_for_bm25("我们用 RAG 来检索增强")
    toks = out.split()
    assert "rag" in toks  # lowercased


def test_punctuation_filtered():
    out = tokenize_for_bm25("hello, world! 你好。世界")
    toks = out.split()
    assert "," not in toks and "。" not in toks
    assert "hello" in toks and "world" in toks


def test_empty_string():
    assert tokenize_for_bm25("") == ""
    assert tokenize_for_bm25("   ") == ""


def test_synonym_expansion_finds_syn():
    expanded = expand_query_with_synonyms("k8s 部署")
    # 至少含 'kubernetes' 的某个 sub-token (jieba 切完可能是 'kubernetes')
    assert "kubernetes" in expanded


def test_synonym_expansion_no_match():
    base = "完全不在词典里的随机词xyz"
    expanded = expand_query_with_synonyms(base)
    # 没扩展时应等于 base 切词结果
    assert expanded == tokenize_for_bm25(base)


def test_synonym_dict_nonempty():
    assert SYNONYMS  # 至少有内容
