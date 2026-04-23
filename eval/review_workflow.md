# Eval QA 人工 review 工作流 (Day 14)

> 目标: 让 baseline 评测集**真正反映业务**, 不是 GPT-4 自嗨.
> 频次: v1 一次性 50 条, v2 每月增量 30 条.

## 流程

```
docs/* + uploaded files
        │
        ▼  eval/generate_qa.py (LLM 批量, ~$2)
qa_generated.jsonl  (200 条 candidates, gold_doc 自动填)
        │
        ▼  eval/review.py (人工, ~1 小时)
qa_reviewed.jsonl   (50 条 keep + 改写 + 部分标 negative)
        │
        ▼  人工合并 (cat + 去重)
qa_baseline.jsonl   (= CI 卡口)
        │
        ▼  PR 改 rag-core/** 时 GitHub Actions 自动跑
eval gate (CI profile)
```

## 一条 review 标准

接受 ([enter]):
- Query 像真实用户搜索框输入 (5-30 字符, 无书面化语气)
- gold_doc 真的能回答
- Query 不太宽泛 ("这文档讲什么")

改写 (`e`):
- 表述太书面化 → 改成口语 ("怎么解决 X" → "X 怎么搞")
- 太长 → 拆短

标 negative (`n`):
- Query 很真实但 KB 没答案 (训拒答能力)
- 错位的 gold_doc (LLM 标错了)

Skip (`s`):
- 表述不清 / 完全错误 / 重复

## 跑一次

```bash
# 1. 生成 (要 LLM API key)
DEEPSEEK_API_KEY=... uv run python eval/generate_qa.py \
    --per-doc 5 --out eval/qa_generated.jsonl

# 2. 人工 review (CLI 交互)
uv run python eval/review.py \
    --in eval/qa_generated.jsonl \
    --out eval/qa_reviewed.jsonl --max 50

# 3. 合并 (de-dup by query)
python -c "
import json
seen = set()
with open('eval/qa_baseline.jsonl', 'a') as out:
    for line in open('eval/qa_reviewed.jsonl'):
        q = json.loads(line)['query']
        if q not in seen:
            seen.add(q)
            out.write(line)
"

# 4. 提交 PR; CI 自动跑 eval, 阈值不达标卡 PR
```

## 阈值校准

如果 CI eval 一直红, 不是改阈值, 而是 root-cause:
1. **chunking 退化**? → `make rag-test` + 看 chunking 单测
2. **embedding 漂移**? → diff `embedding_model_version`
3. **KB 覆盖不够**? → 加文档进 `docs/`
4. **query 漂移**? → 评测集本身已过时, 重做 review

只有真有正当理由才改 `eval/thresholds.yml` (要走 PR + ADR).
