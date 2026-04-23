"""中文 + 英文 BM25 预切分 (L37 §8.8).

策略:
- jieba 切中文 (HMM + 词典)
- 英文/数字保持原 token (jieba 默认会按空格切开)
- 输出空格分隔的 token 串, 喂给 PG 的 simple parser → tsvector

业务术语词典 (用户词典) 后续从 infra/userdict.txt 自动加载;
同义词字典做 query expansion (BM25 query 阶段, 不动 index)。

注:
- jieba 第一次 import 会构建词图, 慢一次 (~1s)
- thread-safety: jieba 全局单例, 多线程读取安全
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import jieba

# 业务/技术同义词 (BM25 query expansion 用)
# Day 10 占位; Day 14+ 从 infra/synonyms.json 加载
SYNONYMS: dict[str, list[str]] = {
    "k8s": ["kubernetes"],
    "kubernetes": ["k8s"],
    "rag": ["检索增强", "retrieval-augmented generation"],
    "llm": ["大语言模型", "大模型"],
    "agent": ["代理", "智能体"],
    "embedding": ["嵌入", "向量化"],
    "rerank": ["重排"],
    "重排": ["rerank"],
    "嵌入": ["embedding"],
    "向量": ["vector", "embedding"],
}

# 标点 / 空白 (切词后过滤)
_NOISE_RE = re.compile(r"^[\s\W_]+$", re.UNICODE)

_USER_DICT_LOADED = False


def _load_user_dict_once() -> None:
    """从 RAG_USER_DICT 环境变量指定的文件加载用户词典 (一次)."""
    global _USER_DICT_LOADED
    if _USER_DICT_LOADED:
        return
    path = os.environ.get("RAG_USER_DICT")
    if path and Path(path).exists():
        jieba.load_userdict(path)
    _USER_DICT_LOADED = True


def tokenize_for_bm25(text: str) -> str:
    """jieba 切词 + 过滤标点, 返回空格分隔的 token 串 (用于 to_tsvector('simple', ...))."""
    _load_user_dict_once()
    if not text:
        return ""
    tokens: list[str] = []
    for tok in jieba.cut_for_search(text):
        tok = tok.strip()
        if not tok or _NOISE_RE.match(tok):
            continue
        tokens.append(tok.lower())
    return " ".join(tokens)


def expand_query_with_synonyms(query: str, max_extra: int = 4) -> str:
    """对切完的 query token 做同义词扩展, 返回新 token 串.

    实现简化: 在切词后的 token 上查同义词表, 把找到的扩展拼到原 query 后面 (空格分隔).
    PG ts_rank 会把额外 token 计入相关度。
    """
    base = tokenize_for_bm25(query)
    if not base:
        return base
    extras: list[str] = []
    for tok in base.split():
        for syn in SYNONYMS.get(tok, []):
            extras.append(tokenize_for_bm25(syn))
            if len(extras) >= max_extra:
                break
        if len(extras) >= max_extra:
            break
    if extras:
        return base + " " + " ".join(extras)
    return base
