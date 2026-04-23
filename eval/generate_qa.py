"""自动用 GPT-4 (或任意 LiteLLM 模型) 从文档生成 QA, 扩到 200 条 (Day 12 + 14).

用法:
    # 默认从 docs/ 抽 200 条 (40 个 doc × 5 条)
    python eval/generate_qa.py --out eval/qa_generated.jsonl --per-doc 5

    # 自定义 corpus 与模型
    python eval/generate_qa.py --corpus README.md --model deepseek/deepseek-chat \\
                               --per-doc 3 --out eval/qa_extra.jsonl

人工抽检流程 (L37 §7):
    1. 跑本脚本 → eval/qa_generated.jsonl (~200 条 candidates)
    2. 人工抽 50 条 review (改 query / 删伪问题 / 标 negative)
    3. 把 reviewed 的合并进 eval/qa_baseline.jsonl 作为 CI 卡口
    4. v2 从线上 trace 自动挖增量

要求: pip install rag-core[llm]; 设置对应 provider API key.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path

DEFAULT_PROMPT = """以下是知识库中的一段文档. 请为它生成 {n} 条**用户可能搜索的真实问题**.
要求:
- 每行一个问题, 不带编号, 不带前缀
- 短问题 (5-30 字符), 模拟搜索框输入
- 中英文混合可以, 跟原文风格保持一致
- 答案应该可以从这段文档找到
- 不要太宽泛 (避免"这个文档讲什么")

文档片段:
<doc>
{doc_text}
</doc>

{n} 个问题:"""


async def generate_for_doc(llm, model: str, doc_text: str, n: int) -> list[str]:
    resp = await llm.complete(
        messages=[{"role": "user", "content": DEFAULT_PROMPT.format(
            n=n, doc_text=doc_text[:8000])}],
        model=model, max_tokens=512, temperature=0.7,
    )
    lines = [
        re.sub(r"^[\d\.\-\)\(\s]+", "", line).strip()
        for line in resp.text.splitlines()
    ]
    return [l for l in lines if 4 <= len(l) <= 80][:n]


async def main_async() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--corpus", nargs="+", type=Path,
        default=sorted(Path("docs").glob("*.md")) + [Path("README.md")],
    )
    ap.add_argument("--out", type=Path, default=Path("eval/qa_generated.jsonl"))
    ap.add_argument("--model", default="deepseek/deepseek-chat")
    ap.add_argument("--per-doc", type=int, default=5)
    ap.add_argument("--max-docs", type=int, default=None,
                    help="上限 (调试用, 省 token)")
    args = ap.parse_args()

    try:
        from rag_core.llm.litellm_backend import LiteLLMClient
    except ImportError:
        print("ERROR: install rag-core[llm] first")
        return
    llm = LiteLLMClient()

    files = [f for f in args.corpus if f.exists()]
    if args.max_docs:
        files = files[: args.max_docs]
    print(f"generating from {len(files)} docs × {args.per_doc} questions")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with args.out.open("w") as f:
        for fp in files:
            try:
                text = fp.read_text(encoding="utf-8", errors="replace")
                qs = await generate_for_doc(llm, args.model, text, args.per_doc)
                for q in qs:
                    f.write(json.dumps(
                        {"query": q, "gold_doc": str(fp)},
                        ensure_ascii=False,
                    ) + "\n")
                    written += 1
                print(f"  ✓ {fp.name:<45} {len(qs)} qs")
            except Exception as e:
                print(f"  ✗ {fp.name}: {e}")
    print(f"\n→ {args.out} ({written} questions)")
    print("\n下一步: 人工抽 50 条 review, 合并进 eval/qa_baseline.jsonl")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
