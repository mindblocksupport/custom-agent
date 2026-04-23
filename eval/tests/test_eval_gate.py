"""eval/run.py 内部函数测试: 阈值卡口逻辑 + name 归一化."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run import _normalize_name, gate, load_thresholds  # noqa: E402


def test_normalize_name_buckets():
    assert _normalize_name("dense") == "dense"
    assert _normalize_name("bm25") == "bm25"
    assert _normalize_name("hybrid (no rerank)") == "hybrid"
    assert _normalize_name("hybrid + rerank (hash, refuse<0.3)") == "hybrid_rerank"


def test_gate_passes_when_above_threshold():
    results = [
        {"name": "bm25", "recall@5": 0.50, "precision@1": 0.4,
         "mrr@10": 0.3, "refusal_tpr": 0.0, "refusal_fpr": 0.0},
    ]
    thresholds = {"bm25": {"recall_at_5": 0.30}}
    fails = gate(results, thresholds)
    assert fails == []


def test_gate_fails_when_below_threshold():
    results = [
        {"name": "bm25", "recall@5": 0.10, "precision@1": 0.0,
         "mrr@10": 0.0, "refusal_tpr": 0.0, "refusal_fpr": 0.0},
    ]
    thresholds = {"bm25": {"recall_at_5": 0.30}}
    fails = gate(results, thresholds)
    assert len(fails) == 1
    assert "recall_at_5" in fails[0]


def test_gate_fpr_direction_inverted():
    """refusal_fpr 是 '越小越好', 触阈方向反."""
    results = [
        {"name": "hybrid + rerank", "recall@5": 1.0, "precision@1": 1.0,
         "mrr@10": 1.0, "refusal_tpr": 1.0, "refusal_fpr": 0.20},
    ]
    thresholds = {"hybrid_rerank": {"refusal_fpr": 0.10}}
    fails = gate(results, thresholds)
    assert len(fails) == 1 and "refusal_fpr" in fails[0]


def test_gate_skips_unknown_modes():
    results = [{"name": "dense", "recall@5": 0.05}]
    thresholds = {"hybrid_rerank": {"recall_at_5": 0.85}}
    assert gate(results, thresholds) == []


def test_load_thresholds_returns_empty_when_missing(tmp_path):
    out = load_thresholds("ci", tmp_path / "missing.yml")
    assert out == {}


def test_load_thresholds_parses_profile(tmp_path):
    p = tmp_path / "t.yml"
    p.write_text(
        "ci:\n"
        "  thresholds:\n"
        "    bm25:\n"
        "      recall_at_5: 0.30\n"
        "nightly:\n"
        "  thresholds:\n"
        "    hybrid_rerank:\n"
        "      recall_at_5: 0.85\n"
    )
    out = load_thresholds("ci", p)
    assert out == {"bm25": {"recall_at_5": 0.30}}
    out2 = load_thresholds("nightly", p)
    assert out2 == {"hybrid_rerank": {"recall_at_5": 0.85}}
