"""rag-core 运行时配置 (env 优先, 给 CLI / MCP server 共用)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from uuid import UUID

# 默认租户 (Day 9 单租户), Day 11 之后由 MCP context 注入真实值
DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_ACTOR_ID = UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_PRINCIPALS = ["user:dev", "group:public"]


@dataclass(frozen=True)
class Settings:
    db_url: str
    embedding_backend: str              # 'qwen3' | 'hash'
    embedding_model_id: str
    reranker_backend: str               # 'bge' | 'hash' | 'none'
    reranker_model_id: str
    default_target_chars: int
    default_overlap_chars: int
    refusal_threshold: float
    candidate_pool: int
    rrf_k: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            db_url=os.environ.get(
                "RAG_DB_URL",
                "postgresql://agent:agent@localhost:5432/agent",
            ),
            embedding_backend=os.environ.get("RAG_EMBED_BACKEND", "hash"),
            embedding_model_id=os.environ.get(
                "RAG_EMBED_MODEL", "Qwen/Qwen3-Embedding-0.6B"
            ),
            reranker_backend=os.environ.get("RAG_RERANK_BACKEND", "hash"),
            reranker_model_id=os.environ.get(
                "RAG_RERANK_MODEL", "BAAI/bge-reranker-v2-m3"
            ),
            default_target_chars=int(os.environ.get("RAG_CHUNK_TARGET", "1024")),
            default_overlap_chars=int(os.environ.get("RAG_CHUNK_OVERLAP", "100")),
            refusal_threshold=float(os.environ.get("RAG_REFUSAL_THRESHOLD", "0.3")),
            candidate_pool=int(os.environ.get("RAG_CANDIDATE_POOL", "20")),
            rrf_k=int(os.environ.get("RAG_RRF_K", "60")),
        )


def make_embedder(settings: Settings):
    if settings.embedding_backend == "qwen3":
        from rag_core.embedding.qwen3 import Qwen3Embedding

        return Qwen3Embedding(model_id=settings.embedding_model_id)
    if settings.embedding_backend == "hash":
        from rag_core.embedding.hash_backend import HashEmbedding

        return HashEmbedding()
    raise ValueError(f"unknown embedding backend: {settings.embedding_backend}")


def make_reranker(settings: Settings):
    """返回 Reranker 实例或 None."""
    backend = settings.reranker_backend
    if backend == "none":
        return None
    if backend == "hash":
        from rag_core.reranker.hash_backend import HashReranker

        return HashReranker()
    if backend == "bge":
        from rag_core.reranker.bge_reranker import BgeReranker

        return BgeReranker(model_id=settings.reranker_model_id)
    raise ValueError(f"unknown reranker backend: {backend}")
