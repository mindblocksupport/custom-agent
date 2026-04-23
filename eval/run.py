"""Day 10/14 eval: A/B 对比 dense / bm25 / hybrid / hybrid+rerank.

跑法:
    python eval/run.py                                 # 默认 stdout
    python eval/run.py --strict --profile ci           # CI 卡口 (违阈 exit 1)
    python eval/run.py --json-out eval/results.json    # 写 JSON (CI artifact)

指标 (Day 14 完整版):
    - recall@5        gold doc 是否在 top-5
    - mrr@10          gold doc 的 rank 倒数 (top-10 内)
    - precision@1     top-1 citation 是否就是 gold doc (citation 准确率代理)
    - refusal_tpr     gold=null 时成功拒答率
    - refusal_fpr     gold!=null 时误拒答率

不依赖 docker / PG: 用 InMemoryStore 跑.
切真 Qwen3 embedding: RAG_EMBED_BACKEND=qwen3 python eval/run.py (装 [embed])
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

from rag_core.chunking.recursive import chunk_text
from rag_core.config import (
    DEFAULT_PRINCIPALS,
    DEFAULT_TENANT_ID,
    Settings,
    make_embedder,
    make_reranker,
)
from rag_core.retrieval.bm25 import BM25Retriever
from rag_core.retrieval.dense import DenseRetriever
from rag_core.retrieval.hybrid import HybridRetriever
from rag_core.storage.in_memory_store import InMemoryStore
from rag_core.tokenize.jieba_tokenizer import tokenize_for_bm25
from rag_core.types import Chunk


def load_qa(path: Path) -> list[dict]:
    out = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        out.append(json.loads(line))
    return out


def build_corpus(store: InMemoryStore, embedder, files: list[Path]) -> dict[Path, str]:
    """ingest 文件列表, 返回 file→doc_id 映射 (用 source_uri 比对)."""
    file_to_uri: dict[Path, str] = {}
    for f in files:
        if not f.exists():
            print(f"  ⚠️  skipping {f} (not found)")
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        title = f.stem
        for line in text.splitlines():
            if line.startswith("#"):
                title = line.lstrip("#").strip()
                break
        doc_id = store.add_doc(title=title, source_uri=str(f), acl=DEFAULT_PRINCIPALS)
        spans = chunk_text(text, target_chars=512, overlap_chars=50)
        if not spans:
            continue
        embeddings = embedder.encode([s.content for s in spans])
        chunks = [
            Chunk(
                id=uuid4(),
                doc_id=doc_id,
                tenant_id=DEFAULT_TENANT_ID,
                chunk_seq=s.seq,
                doc_version=1,
                content=s.content,
                content_hash=s.content_hash,
                embedding=emb,
                embedding_model_version=embedder.name,
                bm25_tokens=tokenize_for_bm25(s.content),
                metadata={"heading_path": list(s.heading_path)},
                char_offset_start=s.char_offset_start,
                char_offset_end=s.char_offset_end,
            )
            for s, emb in zip(spans, embeddings, strict=True)
        ]
        store.add_chunks(chunks)
        file_to_uri[f] = str(f)
        print(f"  + {f.name:<40} ({len(chunks)} chunks)")
    return file_to_uri


def gold_doc_uri(qa_item: dict) -> str | None:
    g = qa_item.get("gold_doc")
    return str(Path(g).resolve()) if g else None


def evaluate(
    name: str,
    qa: list[dict],
    search_fn,                            # (query) -> (hits, refused)
) -> dict:
    recall5 = 0
    p1 = 0                  # precision@1: top-1 doc 就是 gold
    recall_eligible = 0     # gold!=null 的样本
    mrr_sum = 0.0
    mrr_eligible = 0
    refusal_correct = 0     # gold=null 且拒答 → TP
    refusal_should = 0      # gold=null 总数
    refusal_wrong = 0       # gold!=null 但被拒答 → FP

    for item in qa:
        gold = gold_doc_uri(item)
        hits, refused = search_fn(item["query"])
        if gold is None:
            refusal_should += 1
            if refused:
                refusal_correct += 1
        else:
            recall_eligible += 1
            mrr_eligible += 1
            if refused:
                refusal_wrong += 1
                continue
            uris = [str(Path(h.source_uri).resolve()) for h in hits if h.source_uri]
            if uris and uris[0] == gold:
                p1 += 1
            if gold in uris[:5]:
                recall5 += 1
            for rank, uri in enumerate(uris[:10], 1):
                if uri == gold:
                    mrr_sum += 1.0 / rank
                    break

    return {
        "name": name,
        "recall@5": (recall5 / recall_eligible if recall_eligible else 0.0),
        "mrr@10": (mrr_sum / mrr_eligible if mrr_eligible else 0.0),
        "precision@1": (p1 / recall_eligible if recall_eligible else 0.0),
        "refusal_tpr": (refusal_correct / refusal_should if refusal_should else 0.0),
        "refusal_fpr": (refusal_wrong / recall_eligible if recall_eligible else 0.0),
        "n": len(qa),
        "n_gold": recall_eligible,
        "n_negative": refusal_should,
    }


def load_thresholds(profile: str, path: Path) -> dict[str, dict[str, float]]:
    """加载 eval/thresholds.yml 中指定 profile 的阈值表 (mode → metric → minimum)."""
    if not path.exists():
        return {}
    try:
        import yaml
    except ImportError:
        print("WARN: pyyaml missing, skipping threshold check", file=sys.stderr)
        return {}
    data = yaml.safe_load(path.read_text())
    return ((data or {}).get(profile) or {}).get("thresholds") or {}


# yaml 阈值 key (recall_at_5) → 结果 dict key (recall@5)
_METRIC_KEY_MAP = {
    "recall_at_5": "recall@5",
    "mrr_at_10": "mrr@10",
    "precision_at_1": "precision@1",
    "refusal_tpr": "refusal_tpr",
    "refusal_fpr": "refusal_fpr",
}


def gate(results: list[dict], thresholds: dict[str, dict[str, float]]) -> list[str]:
    """对照阈值表, 返回违规列表 (空则全部通过)."""
    by_name = {_normalize_name(r["name"]): r for r in results}
    failures = []
    for mode_key, metric_map in thresholds.items():
        r = by_name.get(_normalize_name(mode_key))
        if r is None:
            continue
        for yaml_metric, minimum in metric_map.items():
            result_key = _METRIC_KEY_MAP.get(yaml_metric, yaml_metric)
            actual = r.get(result_key)
            if actual is None:
                continue
            # refusal_fpr 是 "越小越好" 方向, 其余是 "越大越好"
            ok = (
                actual <= minimum
                if yaml_metric == "refusal_fpr"
                else actual >= minimum
            )
            if not ok:
                op = "<=" if yaml_metric == "refusal_fpr" else ">="
                failures.append(
                    f"  ✗ {mode_key}.{yaml_metric} = {actual:.3f}, expected {op} {minimum}"
                )
    return failures


def _normalize_name(name: str) -> str:
    """把 'hybrid + rerank (hash, refuse<0.3)' 归一化为 'hybrid_rerank' 用于阈值匹配.

    注意: 'hybrid (no rerank)' 含 'rerank' 子串, 但前缀是 'no', 应归为 'hybrid'.
    """
    n = name.lower()
    if "no rerank" in n or "no-rerank" in n:
        return "hybrid"
    if "rerank" in n:
        return "hybrid_rerank"
    if "hybrid" in n:
        return "hybrid"
    if "bm25" in n:
        return "bm25"
    if "dense" in n:
        return "dense"
    return n.split()[0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--qa", type=Path, default=Path("eval/qa_baseline.jsonl"))
    ap.add_argument(
        "--corpus", nargs="+", type=Path,
        default=[Path("README.md")] + sorted(Path("docs").glob("*.md")),
    )
    ap.add_argument("--strict", action="store_true",
                    help="违反阈值即 exit 1 (CI 用)")
    ap.add_argument("--profile", default="ci",
                    choices=["ci", "nightly"],
                    help="阈值 profile (eval/thresholds.yml)")
    ap.add_argument("--thresholds", type=Path,
                    default=Path("eval/thresholds.yml"))
    ap.add_argument("--json-out", type=Path, default=None,
                    help="把全部 metric 写一份 JSON 报告 (CI artifact)")
    args = ap.parse_args()

    settings = Settings.from_env()
    print(f"=== eval ({settings.embedding_backend} embed, "
          f"{settings.reranker_backend} reranker) ===\n")

    print("[1] building corpus...")
    embedder = make_embedder(settings)
    store = InMemoryStore()
    build_corpus(store, embedder, args.corpus)
    print(f"  → {len(store.chunks)} chunks total\n")

    print("[2] loading QA...")
    qa = load_qa(args.qa)
    print(f"  → {len(qa)} QA items "
          f"({sum(1 for q in qa if q.get('gold_doc')) } with gold, "
          f"{sum(1 for q in qa if not q.get('gold_doc'))} negatives)\n")

    print("[3] evaluating modes...\n")
    tid, principals = DEFAULT_TENANT_ID, DEFAULT_PRINCIPALS

    # dense only
    dense = DenseRetriever(store, embedder)
    r_dense = evaluate("dense", qa, lambda q: (
        dense.search(query=q, tenant_id=tid, principals=principals, k=10), False))

    # bm25 only
    bm25 = BM25Retriever(store)
    r_bm25 = evaluate("bm25", qa, lambda q: (
        bm25.search(query=q, tenant_id=tid, principals=principals, k=10), False))

    # hybrid (no rerank)
    hr_no = HybridRetriever(
        store, embedder, reranker=None,
        rrf_k=settings.rrf_k, candidate_pool=settings.candidate_pool,
        refusal_threshold=0.0,  # 不开拒答, 测纯 hybrid 召回
    )
    def hybrid_no(q: str):
        res = hr_no.search(query=q, tenant_id=tid, principals=principals, k=10)
        return res.hits, res.refused
    r_hybrid = evaluate("hybrid (no rerank)", qa, hybrid_no)

    # hybrid + rerank + refusal
    reranker = make_reranker(settings)
    hr_re = HybridRetriever(
        store, embedder, reranker=reranker,
        rrf_k=settings.rrf_k, candidate_pool=settings.candidate_pool,
        refusal_threshold=settings.refusal_threshold,
    )
    def hybrid_re(q: str):
        res = hr_re.search(query=q, tenant_id=tid, principals=principals, k=10)
        return res.hits, res.refused
    r_rerank = evaluate(
        f"hybrid + rerank ({settings.reranker_backend}, refuse<{settings.refusal_threshold})",
        qa, hybrid_re,
    )

    # report
    results = [r_dense, r_bm25, r_hybrid, r_rerank]
    print("=" * 90)
    print(f"{'mode':<53} {'R@5':>5} {'P@1':>5} {'MRR':>6} {'refT':>6} {'refF':>6}")
    print("-" * 90)
    for r in results:
        print(
            f"{r['name']:<53} {r['recall@5']:>5.2f} {r['precision@1']:>5.2f} "
            f"{r['mrr@10']:>6.2f} {r['refusal_tpr']:>6.2f} {r['refusal_fpr']:>6.2f}"
        )
    print("=" * 90)

    # JSON 报告 (CI artifact)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps({
            "profile": args.profile,
            "embedding_backend": settings.embedding_backend,
            "reranker_backend": settings.reranker_backend,
            "results": results,
        }, indent=2, ensure_ascii=False))
        print(f"\n→ wrote JSON report: {args.json_out}")

    # 阈值卡口
    thresholds = load_thresholds(args.profile, args.thresholds)
    if thresholds:
        failures = gate(results, thresholds)
        if failures:
            print(f"\n❌ {args.profile} 阈值检查失败:")
            for f in failures:
                print(f)
            if args.strict:
                sys.exit(1)
        else:
            print(f"\n✅ {args.profile} 阈值全部通过")
    elif args.strict:
        print(f"❌ --strict 但 thresholds.yml 缺失或无 profile {args.profile}")
        sys.exit(2)


if __name__ == "__main__":
    main()
