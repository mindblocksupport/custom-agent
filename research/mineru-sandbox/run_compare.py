"""MinerU vs PaddleOCR-VL 对比评测 (研究沙箱, AGPL 隔离).

用法:
    python run_compare.py --pdfs ./pdfs/*.pdf --out ./results/compare.md

不依赖主仓 venv. 运行前请先 `pip install -r requirements.txt`.

不参与 CI; 由人工跑, 结果写入 eval/parser_comparison.md.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def parse_with_mineru(pdf_path: Path) -> tuple[str, float]:
    """返回 (markdown, elapsed_seconds). 加载失败时上抛."""
    # AGPL 区域: 仅在沙箱跑
    from magic_pdf.pipe.UNIPipe import UNIPipe          # type: ignore
    from magic_pdf.rw.DiskReaderWriter import DiskReaderWriter  # type: ignore

    t0 = time.perf_counter()
    image_writer = DiskReaderWriter(str(pdf_path.parent / "_mineru_imgs"))
    pdf_bytes = pdf_path.read_bytes()
    pipe = UNIPipe(pdf_bytes, jso_useful_key={"_pdf_type": "", "model_list": []},
                    image_writer=image_writer)
    pipe.pipe_classify()
    pipe.pipe_analyze()
    pipe.pipe_parse()
    md = pipe.pipe_mk_markdown(image_writer)
    return md, time.perf_counter() - t0


def parse_with_paddle(pdf_path: Path) -> tuple[str, float]:
    """PaddleOCR-VL 1.5 解析. 返回 (markdown, elapsed_seconds)."""
    from paddleocr import PPStructure                   # type: ignore

    t0 = time.perf_counter()
    structure_engine = PPStructure(table=True, ocr=True, show_log=False)
    result = structure_engine(str(pdf_path))
    md_lines = []
    for region in result:
        if region.get("type") == "title":
            md_lines.append(f"# {region.get('res', '')}")
        elif region.get("type") == "table":
            md_lines.append(region.get("res", {}).get("html", ""))
        else:
            md_lines.append(region.get("res", ""))
    return "\n\n".join(md_lines), time.perf_counter() - t0


def length_ratio_metric(md: str, expected_min: int = 100) -> dict:
    """非 ground-truth 时, 用文本长度作为 sanity 信号."""
    return {
        "char_count": len(md),
        "line_count": md.count("\n"),
        "has_table": "<table" in md.lower() or "|---" in md,
    }


def compare_one(pdf_path: Path) -> dict:
    out: dict = {"pdf": str(pdf_path)}
    for engine_name, fn in [("mineru", parse_with_mineru), ("paddle", parse_with_paddle)]:
        try:
            md, elapsed = fn(pdf_path)
            out[engine_name] = {
                "elapsed_s": round(elapsed, 2),
                "metrics": length_ratio_metric(md),
                "md_preview": md[:200],
            }
        except Exception as e:
            out[engine_name] = {"error": f"{type(e).__name__}: {e}"}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdfs", nargs="+", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    results = [compare_one(p) for p in args.pdfs]
    args.out.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\n→ wrote {args.out}")
    print("Next: 把数据填到 eval/parser_comparison.md")


if __name__ == "__main__":
    main()
