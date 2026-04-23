"""人工 review CLI: 把 generated.jsonl 里 candidate QA 一条条人工筛.

用法:
    python eval/review.py \
      --in eval/qa_generated.jsonl \
      --out eval/qa_reviewed.jsonl \
      --max 50

按键:
    [enter] 接受
    e       编辑 query (现场改 query 文本)
    n       标 negative (gold_doc=null)
    s       skip (不写出)
    q       退出 (已 reviewed 的会保存)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", type=Path,
                    default=Path("eval/qa_generated.jsonl"))
    ap.add_argument("--out", type=Path, default=Path("eval/qa_reviewed.jsonl"))
    ap.add_argument("--max", type=int, default=50)
    args = ap.parse_args()

    if not args.inp.exists():
        print(f"❌ {args.inp} not found. 先跑 eval/generate_qa.py")
        sys.exit(1)

    items = [json.loads(l) for l in args.inp.read_text().splitlines() if l.strip()]
    print(f"loaded {len(items)} candidates from {args.inp}\n")
    print("按键: [enter]=接受  e=编辑  n=标 negative  s=skip  q=退出\n")

    reviewed: list[dict] = []
    for i, item in enumerate(items[: args.max], 1):
        q = item.get("query", "")
        gold = item.get("gold_doc")
        print(f"[{i}/{min(args.max, len(items))}]  gold: {gold}")
        print(f"  query: {q}")
        try:
            cmd = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n(quit)")
            break
        if cmd == "q":
            break
        if cmd == "s":
            continue
        if cmd == "e":
            new_q = input("  改写 query: ").strip()
            if new_q:
                item["query"] = new_q
        if cmd == "n":
            item["gold_doc"] = None
        item["reviewed"] = True
        reviewed.append(item)
        print()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as f:
        for it in reviewed:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"\n→ wrote {len(reviewed)} reviewed items to {args.out}")
    print("下一步: 把 reviewed 集合并进 eval/qa_baseline.jsonl 作 CI 卡口.")


if __name__ == "__main__":
    main()
