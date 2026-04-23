# MinerU Sandbox · 研究区 (AGPL 隔离)

> ⚠️ **License 警示**: MinerU 主包 (`magic-pdf`) 是 **AGPL-3.0**.
> 商用代码若 import 它, 整个调用链就会被 AGPL 传染.
> 本目录是**纯研究**沙箱: 只用来对比 MinerU vs PaddleOCR-VL 的解析效果.
> **绝不可** 把本目录的代码 import 进 `services/` 或 `packages/` 任何模块.

## 目的

按 [L37 v1.1 §7](../../docs/37-rag-implementation-plan.md#7-已确认决策2026-04-23):
> MinerU 作为**研究备选, 主路径 PaddleOCR-VL 1.5**

让我们能在 50 篇代表性 PDF 上**离线对比** OmniDocBench 子集分数, 给法务背书.

## 物理隔离

- 独立 venv, **不**进 uv workspace
- 输出落 `research/mineru-sandbox/results/`, 已 gitignore
- workspace 主仓 (`packages/*` / `services/*`) 的 pyproject 都 **不**依赖 magic-pdf
- CI `license-scan` 阻止 AGPL 进入生产

## 安装 (本地 only)

```bash
cd research/mineru-sandbox
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # 含 magic-pdf (AGPL) + paddleocr + benchmark deps
```

## 跑对比

```bash
python run_compare.py \
    --pdfs ./pdfs/*.pdf \
    --out ./results/compare-$(date +%F).md
```

输出会更新 [eval/parser_comparison.md](../../eval/parser_comparison.md) 的对比表.
报告需要送法务确认才能决定是否替换主路径.

## 评分维度

- OmniDocBench v1.6 子集 (50 篇)
- 表格还原准确率 (cell-level F1)
- 阅读顺序正确率
- 中文扫描件 OCR 字符错误率
- 单 PDF 解析延迟 P95
- 内存峰值 (16G 笔记本能跑否)
