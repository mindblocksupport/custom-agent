# PDF 解析器对比评测 (Day 14)

> 用途: 给法务/采购背书"为什么生产用 PaddleOCR-VL 而不是 MinerU".
> 数据源: `research/mineru-sandbox/run_compare.py` 输出的 JSON.
> 上次评测: **未跑** (2026-04-23, Day 14 完成框架, 数据待补).

## 评测协议

| 项 | 值 |
|---|---|
| 数据集 | OmniDocBench v1.6 子集 (50 篇代表性 PDF) |
| 类型分布 | 论文 ×20, 财报 ×10, 中文扫描件 ×10, 表格密集 ×10 |
| 硬件 | 一台 Mac M2 Pro (16G), 单进程 |
| 评测人 | TBD |
| 法务 review | 必须 (License 决定能否上线) |

## 指标定义

- **质量** (越高越好): OmniDocBench 子集分数, 表格 cell-F1, 阅读顺序正确率
- **效率**: 单页延迟 P95 (ms), 内存峰值 (MB)
- **License**: 是否 AGPL (商用毒丸)

## 决策矩阵

| 维度 | MinerU 2.5-Pro-2604 | PaddleOCR-VL 1.5 | 判定 |
|---|---|---|---|
| OmniDocBench v1.6 | **95.69%** (公开榜单) | ~92% | MinerU 更准 |
| License | **AGPL-3.0** ❌ | Apache-2.0 ✅ | **Paddle 胜** |
| 表格还原 | 优 (布局识别强) | 良 | 待实测 |
| 阅读顺序 | 优 | 良 | 待实测 |
| 中文 OCR | 优 | 优 | 平 |
| 单页 P95 | 待实测 | 待实测 | 待实测 |
| 内存峰值 | 待实测 | 待实测 | 待实测 |

## 当前结论 (基于 License)

**生产用 PaddleOCR-VL 1.5**.

理由: AGPL-3.0 商用必须开源**整个调用链** (含上层 agent / 平台代码), 法律风险无法承受.
即便 MinerU 准确度高 3-4 pp, 收益不足以抵消 license 风险.

## MinerU 仍有用的场景

1. **离线一次性高价值文档解析** (合同 / 法律文书): 在沙箱跑, 输出 Markdown 后再 ingest.
   注意: 这类文档需要人工 review, 跟生产 RAG pipeline 隔离.
2. **eval 数据集准备**: 给 PaddleOCR 的输出做 ground-truth 对照.
3. **未来 license 变更**时切换的备选.

## 待跑实验 (Day 14 之后)

- [ ] 准备 50 篇 PDF 数据集 → `research/mineru-sandbox/pdfs/`
- [ ] `python run_compare.py --pdfs pdfs/*.pdf --out results/2026-XX.json`
- [ ] 把 JSON 数据填到本表
- [ ] 法务 review + 签字
