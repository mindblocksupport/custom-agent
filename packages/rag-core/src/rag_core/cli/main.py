"""rag CLI: ingest / query / status

用法:
    rag ingest <path> [--tenant TENANT_ID] [--acl 'user:U1,group:G2']
    rag query "搜索语句" [--k 5]
    rag status   # 显示 db_url + embedding backend + chunk 配置

环境变量:
    RAG_DB_URL              postgresql://agent:agent@localhost:5432/agent
    RAG_EMBED_BACKEND       hash | qwen3
    RAG_EMBED_MODEL         Qwen/Qwen3-Embedding-0.6B
    RAG_CHUNK_TARGET        1024
    RAG_CHUNK_OVERLAP       100
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

import click

from rag_core.chunking.parent_child import ParentChildChunker
from rag_core.config import (
    DEFAULT_PRINCIPALS,
    DEFAULT_TENANT_ID,
    Settings,
    make_embedder,
    make_reranker,
)
from rag_core.ingest.pipeline import IngestPipeline, ingest_file
from rag_core.retrieval.bm25 import BM25Retriever
from rag_core.retrieval.dense import DenseRetriever
from rag_core.retrieval.hybrid import HybridRetriever
from rag_core.storage.pgvector_store import PgVectorStore


def _build(settings: Settings, *, parent_child: bool = False):
    store = PgVectorStore(settings.db_url)
    embedder = make_embedder(settings)
    pc = ParentChildChunker() if parent_child else None
    pipeline = IngestPipeline(store, embedder, parent_child_chunker=pc)
    return store, pipeline, embedder


@click.group()
def cli() -> None:
    """rag-core CLI."""


@cli.command()
def status() -> None:
    s = Settings.from_env()
    click.echo(f"db_url               = {s.db_url}")
    click.echo(f"embedding_backend    = {s.embedding_backend}")
    click.echo(f"embedding_model      = {s.embedding_model_id}")
    click.echo(f"reranker_backend     = {s.reranker_backend}")
    click.echo(f"reranker_model       = {s.reranker_model_id}")
    click.echo(f"chunk_target/overlap = {s.default_target_chars}/{s.default_overlap_chars}")
    click.echo(f"refusal_threshold    = {s.refusal_threshold}")
    click.echo(f"candidate_pool       = {s.candidate_pool}")
    click.echo(f"rrf_k                = {s.rrf_k}")


@cli.command()
@click.argument("path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--tenant", default=str(DEFAULT_TENANT_ID), show_default=True,
    help="tenant_id (UUID)",
)
@click.option(
    "--acl", default=",".join(DEFAULT_PRINCIPALS), show_default=True,
    help="逗号分隔, e.g. 'user:U1,group:G2'",
)
@click.option("--parent-child/--flat", default=False, show_default=True,
              help="父子分级切分 (Day 12); 关命中子块入 prompt 用父块")
def ingest(path: Path, tenant: str, acl: str, parent_child: bool) -> None:
    """把单个文件 ingest 进 KB."""
    settings = Settings.from_env()
    _, pipeline, _ = _build(settings, parent_child=parent_child)
    acl_list = [a.strip() for a in acl.split(",") if a.strip()]
    try:
        report = ingest_file(pipeline, path, tenant_id=UUID(tenant), acl=acl_list)
    except NotImplementedError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(2)
    click.echo(
        f"✅ {path.name} → doc {report.doc_id} "
        f"(v{report.version}, +{report.chunks_created} new, "
        f"{report.chunks_reused} reused, mode={'parent-child' if parent_child else 'flat'})"
    )


@cli.command()
@click.argument("query")
@click.option("--k", default=5, show_default=True)
@click.option(
    "--mode", type=click.Choice(["dense", "bm25", "hybrid"]), default="hybrid",
    show_default=True,
)
@click.option("--rerank/--no-rerank", default=False, show_default=True,
              help="hybrid 模式启用重排 (用 RAG_RERANK_BACKEND 配置的 reranker)")
@click.option("--tenant", default=str(DEFAULT_TENANT_ID), show_default=True)
@click.option(
    "--acl", default=",".join(DEFAULT_PRINCIPALS), show_default=True,
    help="同 ingest --acl",
)
def query(query: str, k: int, mode: str, rerank: bool, tenant: str, acl: str) -> None:
    """对 KB 做检索, 打印 top-k 片段."""
    settings = Settings.from_env()
    store, _, embedder = _build(settings)
    principals = [a.strip() for a in acl.split(",") if a.strip()]
    tid = UUID(tenant)

    if mode == "dense":
        hits = DenseRetriever(store, embedder).search(
            query=query, tenant_id=tid, principals=principals, k=k,
        )
        _print_hits(hits, refused=False)
        return
    if mode == "bm25":
        hits = BM25Retriever(store).search(
            query=query, tenant_id=tid, principals=principals, k=k,
        )
        _print_hits(hits, refused=False)
        return

    # hybrid
    reranker = make_reranker(settings) if rerank else None
    hr = HybridRetriever(
        store, embedder, reranker=reranker,
        rrf_k=settings.rrf_k,
        candidate_pool=settings.candidate_pool,
        refusal_threshold=settings.refusal_threshold,
    )
    result = hr.search(
        query=query, tenant_id=tid, principals=principals, k=k,
    )
    click.echo(
        f"(dense={result.n_dense}, bm25={result.n_bm25}, "
        f"rerank_in={result.n_rerank_in}, refused={result.refused})"
    )
    if result.refused:
        click.echo(f"❌ 拒答: {result.refusal_reason}")
        click.echo("(向用户回复: 知识库无相关内容, 建议改写问题或转人工)")
        return
    _print_hits(result.hits, refused=False)


def _print_hits(hits, refused: bool) -> None:
    if not hits:
        click.echo("(no hits — KB 为空或 ACL 拦截)")
        return
    for i, h in enumerate(hits, 1):
        snippet = h.chunk.content[:120].replace("\n", " ")
        click.echo(
            f"\n[{i}] score={h.score:.4f}  doc={h.title or h.source_uri}"
            f"  chunk_seq={h.chunk.chunk_seq}\n    {snippet}…"
        )


if __name__ == "__main__":
    cli()
