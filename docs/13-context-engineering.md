# L13 · 上下文工程（Context Engineering）

> 状态：**讨论中** · v0.1 · 2026-04-22 · 涵盖长上下文 / Memory / 压缩 / Cache 完整流程

## 0. 为什么独立成章
2025 年 Karpathy 与 Tobi Lütke 共同推动 **"Context Engineering"** 替代 "Prompt Engineering" 成为新工程学科：
- Prompt = 一句神奇话
- **Context Engineering = 把"下一步所需信息"用合理预算填进 context window 的工程**

包含：指令、few-shot、RAG、工具 schema、状态、多模态、**和保持总量在预算内的 compaction 策略**。

## 1. 上下文窗口现状（2026-Q1/Q2）

| 模型 | 标称 | 真实可用（RULER 50-65%） | 价格 |
|---|---|---|---|
| Claude Opus 4.6 / Sonnet 4.6 | **1M GA** | ~500-650K | Sonnet $3/$15；Anthropic 取消了 200K+ 的 2× 长上下文溢价 |
| GPT-5.4 | 1.05M | ~500K | $2.50/$15；**>272K 切到 $5/$22.50 长上下文档** |
| Gemini 2.5 Pro / 3 Pro | 1M / **10M** | 视任务 | 最便宜的 frontier；MRCRv2 1M 仅 26.3% |
| Qwen3 (YaRN) | 256K (1M) | 实际更短 | $0.7/$2.8 |
| DeepSeek V3.2 | 128K | - | $0.28/$0.42 |
| Kimi K2.5 | 256K | - | $0.6/$2.5 |

### Lost-in-the-Middle 实情
- **RULER (NVIDIA)**：实际可用 = 标称的 **50-65%**
- **NoLiMa (ICML 2025)**：去掉字面词重叠后，11 个 frontier 模型在 32K 已掉到 baseline 50% 以下；GPT-4o 99.3% → 69.7%
- **Chroma Context Rot (2025)**：18 个 frontier 模型测，长度增加性能**非线性下降，每个模型都恶化**

**实操规则**：
- 检索类任务：**≤50% 标称窗口**
- 多跳推理：**≤25% 标称窗口**
- 200K+ 任何任务都开始有"上下文锈"

## 2. 长上下文 vs RAG vs Memory 决策

**RAG 没死**。Gartner 2025-Q4 调查：71% 一开始用"context-stuffing"的团队 12 月内加了向量检索。

```
1M-token Sonnet 4.6 调用 ≈ $3 + 10-45s
RAG 查询 (~5K 检索 + rerank) ≈ $0.015 + ~1s
→ ~200× 便宜，~10-40× 快（前提：检索好）
```

| 场景 | 选 |
|---|---|
| 单文档深读 / 代码库 <300K / 跨文档综合 | 长上下文 |
| QPS >10/s / 语料 >2M token / 延迟 <3s p95 / 成本敏感 | RAG |
| **2026 主流模式：混合** | RAG 召回 30-100K → 长上下文模型推理 |

## 3. 上下文预算分配

```
┌─ 200K 预算示例 ──────────────────────────┐
│ system prompt + persona  3-8K   2-4%   静态 │
│ tool definitions         5-15K  3-8%   静态 │
│ few-shot 示例            2-6K   1-3%   静态 │
│ memory / 用户画像        1-3K  0.5-2%  静态 │
├─────────────────────────────────────────┤
│ RAG 检索结果             8-30K  4-15%  动态 │
│ 对话历史                 20-60K 10-30% 动态 │
│ 工具结果（当前循环）     10-40K 5-20%  动态 │
├─────────────────────────────────────────┤
│ 生成预留                 4-16K  安全   预留 │
│ Compaction 预留          15-20K 安全   预留 │
└─────────────────────────────────────────┘
```

### 真实生产数字
- **Claude Code** 在 ~83.5%（约 167K of 200K）触发 auto-compact，留 33K 给摘要本身
- **Codex CLI**：180K-244K 阈值（95% 有效窗口）
- **Cursor**：每 prompt 代码上下文 8-12K
- **Manus**：100:1 输入输出比

## 4. Prompt 模板设计

**Anthropic 标准**：XML 标签 + Markdown 骨架（Claude 训练时见过大量 XML）

```xml
<system>
  <role>You are a senior backend engineer assistant.</role>
  <behavior_instructions>
    - Cite sources with [1], [2] markers
    - If unsure, say "I don't know" — do not guess
    - Prefer minimal diffs
  </behavior_instructions>
  <tool_guidance>...</tool_guidance>
  <output_format>JSON {answer, citations, confidence}</output_format>
</system>

<documents>
  <document index="1">
    <source>oncall_runbook.md</source>
    <date>2026-03-14</date>
    <relevance_score>0.91</relevance_score>
    <content>...</content>
  </document>
</documents>

<conversation_history>
  <summary>之前讨论了 Redis cache eviction bug...</summary>
  <recent>
    <turn role="user">...</turn>
  </recent>
</conversation_history>

<user_query>How do I roll back the v2.7 deploy?</user_query>
```

**关键规则**（跨厂商验证）：
- 静态指令放**首位**（可缓存）
- 输出格式 spec 放 system 块**末尾**（接近末端 attention）
- "I don't know is allowed"——**实测降低幻觉**
- 关键约束在 prompt 头**和**尾各重复一次（mitigate lost-in-middle）

## 5. 历史管理

| 策略 | 何时用 |
|---|---|
| 滑动窗口（最近 N 轮） | 短 chatbot |
| 纯摘要 | 成本极敏感 |
| **混合（最近 verbatim + 旧摘要）** | **大多数生产** |
| Tool-result 清理（Anthropic `clear_tool_uses_20250919`） | 工具密集 Agent |
| Hash-pin 引用 | 代码 Agent（替换文件 dump 为 `[file_hash:abc @lines 100-150]`） |

**真实 Anthropic cookbook 数据**：清掉 3/3 中的 2 个文件结果，message list 缩 67%（128K→43K）。8 文档研究任务峰值 173K vs baseline 335K。

## 6. RAG 注入

三个生产决策：

**a. 位置**：
- query 短：retrieved docs 紧贴 user query 之前
- 多轮短交互：放 system prompt 之后（保持 cache 命中，让 history 在后面增长）

**b. metadata 包装**：每个 chunk 必带 `<source>`, `<date>`, `<score>`——支撑引用强制 + 冲突解决

**c. 强制 quote-then-answer**（Anthropic RAG cookbook + LlamaIndex CitationQueryEngine 默认）：
```
1. <quote> 引用相关原文
2. 映射到 source ID
3. 基于 step 1 生成回答
```
→ **实测显著降幻觉**——模型在推理前先承诺证据。

**多源融合**：按 content hash 去重；冲突时**展示双方 + 时间**，要求"更新的优先除非用户指定"。Glean 的 ACL-aware retrieval 模式：每 chunk 带 ACL 标签，**检索时**就过滤掉不可见的（不是生成后过滤）。

## 7. Memory 注入

| 层 | 总在 context? | 机制 |
|---|---|---|
| 用户画像（姓名 / 角色 / 偏好） | **是**——system prompt 顶部 | <100 tokens |
| 长期事实 | **否**——按需召回 | vector store keyed by user_id |
| 程序性 memory（skills/SOP） | 条件 | Anthropic Skills 进入时 1.7K，激活 275-8K |

**与对话历史冲突**：Memory 说"用户偏 Python"但最近几轮是 Go → **当前任务最近轮 wins**；memory 异步更新（write-behind）。Manus 用 `todo.md` **文件**作为程序性 memory——可逆、无限、保持 active context 干净。

## 8. 工具列表注入（>30 工具是杀手）

实测准确率退化：
| 工具数 | 选择准确率 |
|---|---|
| 10 | ~78% |
| 50 | 84-95%（模型 dependent） |
| 100+ | **13-41%** |
| 740 | 0-20% |

### 两阶段路由（>30 工具必做）
1. **Stage 1 语义召回**：embed 所有工具描述；cosine 召回 top-K (8-15)
2. **Stage 2 LLM 选**：把短列表 + 完整 schema 给 LLM

层级化（`browser_*`, `shell_*`, `db_*`）+ **logit masking**（Manus 教训：循环中删工具会 invalidate KV-cache + 让模型困惑——**mask 不删**）

## 9. Prompt Cache 对齐

**Anthropic cache 顺序严格**：`tools → system → messages`，最多 4 显式 `cache_control` breakpoints，回看 20 blocks。

**成本比**：
- Cache write 5min: **1.25×**
- Cache write 1h: **2×**  
- Cache read: **0.1×（90% off）**
- 最小可缓存：4096 tokens (Opus 4.7), 2048 (Sonnet 4.6)

### 推荐生产布局
```
[tools]               <- breakpoint 1
[system + few-shot]   <- breakpoint 2
[KB / RAG corpus]     <- breakpoint 3
[conversation 至此]   <- breakpoint 4 (auto)
[当前问题]            <- 不 cache（每轮变）
```

**Manus 报告**：cached input $0.30/MTok vs uncached $3.00/MTok = **10× 省钱**；目标 cache 命中率 >**80%**，延迟降 **85%**。

**Cache-killer**（最常见 bug）：在 tools/system 任何位置注入时间戳、session ID、per-request 用户数据——**一处变化全量失效**。

## 10. 多轮 Agent 上下文演进

```
Turn 1: 12K (sys+tools) + 0.5K query    = 12.5K
Turn 2: + 8K tool result + 0.3K thought = 20.8K
Turn 3: + 24K file read + 0.5K reason   = 45.8K
... (agentic exploration)
Turn 12: 167K  ← Claude Code auto-compact 触发
        ↓
Turn 13: 35K (compact 摘要 + recent 20K) ← reset
```

### Claude Code 5 层 compaction
1. **Tool-result clearing** —— 先清可重 fetch 的大结果
2. **History truncation** —— 最旧轮丢
3. **Summarisation** —— 剩余历史压成 ~3K 摘要
4. **Memory write** —— 关键事实写入 `/memories` 持久化
5. **Sub-agent spawn** —— 新子任务用 fresh window，仅继承摘要 brief

### Sub-agent 隔离
- Anthropic multi-agent researcher 比单 Opus 4 提升 **90.2%** ——每子 Agent 独立 200K
- 子 Agent 仅返回 1000-2000 tokens distilled findings
- Cost: 多 15× tokens——研究值，chat 不值

### Devin 的玩法
状态**完全在 context 窗口外**——磁盘上 JSON 任务文件作为 DAG，compaction 不丢。

## 11. Token 计数 & 预算执行

| Tokenizer | 用途 |
|---|---|
| `tiktoken` (p50k_base) | OpenAI 离线快速估；Claude ~12% 误差 |
| Anthropic `messages.countTokens` | Ground truth，对账单 |
| 启发式 `chars × 0.25` | UI 显示快速；~20% 误差 |
| Qwen tokenizer | Qwen 模型必用 —— 跨厂商不通用 |

**实时执行**（推荐）：`ContextBudgetAllocator` middleware 发送前算 token，超阈值压缩。**事后**抓 4xx 已经晚了——已付钱 round trip。

## 12. 真实生产参考

| 系统 | 标志性模式 |
|---|---|
| **Cursor** | Merkle tree 文件 hash，10min 增量同步；Turbopuffer 索引；每 prompt 8-12K 代码；`.cursor/rules/*.mdc` 持久化规则（YAML frontmatter） |
| **Claude Code** | `CLAUDE.md` 持久规则；83.5% auto-compact；5 层 compaction；`/compact` 手动；建议 60% 手 compact |
| **Glean** | 检索时强制 ACL；vector DB 带权限 metadata；用户/内容/权限知识图 |
| **Notion AI** | source 选择控件按 DB / page 范围；文档结构作为隐式 metadata |
| **Devin** | 文件 DAG (`tasks/*.json`) 跨 compaction 存活；主 Agent 拥规划，子 Agent 只读 |
| **Manus** | KV-cache 稳定 = "唯一最重要指标"；logit masking 不删工具；`todo.md` 复述；保留 error stack trace |

## 13. 完整流程时序图

```
USER QUERY
    │
    ├──► Intent classifier (small model, ~50ms)
    │     {intent, complexity, needs_rag, needs_tools}
    │
    ├──► PARALLEL ──────────────────────────────┐
    │    ├─► Memory retrieval (vector + KV)     │
    │    ├─► RAG retrieval (hybrid: BM25+dense) │
    │    │     → rerank → top-K=5 → ACL filter  │
    │    └─► Tool semantic shortlist (cos top-12)│
    │                                       ◄────┘
    │
    ├──► Context Budget Allocator
    │     • countTokens 各 bucket
    │     • 动态规则：rag>25K → 压历史; 上传文件 → 跳 RAG
    │     • RAG 重排（best at ends, anti-LITM）
    │
    ├──► Prompt Template Render
    │     • XML tagged sections
    │     • <documents>, <history>, <user_query>
    │     • 静态前缀首位
    │
    ├──► Cache Key Compute
    │     • Hash [tools | system | kb | history]
    │     • ≤4 cache_control breakpoints
    │
    ├──► LLM CALL (streaming)
    │     │
    │     └──► Tool calls?
    │            ├─ 是 → 执行 → append 结果 → loop
    │            └─ 否 → 继续流
    │
    ├──► Compaction trigger（每 loop）
    │     • 75% 窗口：1.clear_tool 2.truncate 3.summarize
    │     • 子任务：spawn 子 Agent (fresh window)
    │
    ├──► Response post-process
    │     • 抽 citations 校验
    │     • 剥内部 scratchpad
    │
    ├──► ASYNC writes
    │     ├─► Memory（抽事实 → vector）
    │     ├─► Trace（LangSmith / OTel）
    │     └─► Cache stats
    │
    └──► Return to user
```

## 14. 边界情况
- **上下文溢出**：drop 顺序：旧工具结果 → 旧轮 → 长检索 doc 中段 → **永不 drop** system / 当前 query。Devin 答案：先序列化到磁盘
- **引用冲突**：双 quote + 时间，"更新优先除非问"。仍歧义 → 拒绝并问
- **Memory 矛盾**：当前任务最近轮 wins；异步排队 memory update
- **工具结果过大**：先 chunk + summarize 再 append；或写盘 + `<file_ref id=...>` 占位

## 15. 实施清单（一页）

```
1. BUDGET     System 5K | Tools 10K | RAG 20K | History 40K
              Memory 2K | Tool-results 30K | Output 8K
              + 20K compaction reserve. Per-query 重分配。

2. TEMPLATE   XML-tagged sections in Markdown.
              顺序: tools → system → KB → history → query.
              "I don't know" allowed. Output schema 末尾。

3. HISTORY    Hybrid: recent 20K verbatim + summary of older.
              Hash-pin 大工具结果。复述 goal。

4. RAG        Hybrid retrieve → rerank → ACL filter →
              wrap <doc source date score> → 重排
              (best at ends) → quote-then-answer 强制。

5. MEMORY     画像 always；长期 retrieved；SOP 作 skills。
              冲突：最近轮 wins；异步 update。

6. TOOLS      ≤15 in-context. 两阶段：语义召回 → LLM 选。
              Mask, 不 remove。

7. CACHE      4 breakpoints: tools/system/KB/history。
              静态前缀无时间戳。目标命中 ≥80%。

8. COMPACT    75% 触发。顺序：clear → truncate → summarize
              → memory write → sub-agent。

9. COUNT      厂商 tokenizer (countTokens API)。
              发送前执行，不事后。

10. OBSERVE   Trace cache_read/write、峰值 context、
              compaction event。命中 <50% 告警。
```

## 16. 推荐 OSS 工具
- **LLMLingua / LongLLMLingua** (Microsoft)：prompt 压缩 4-20×，质量损失 <5%；LooGLE 上 94% 省钱
- **LangChain ContextualCompressionRetriever**：标准管道
- **mem0 / Letta / Zep / Graphiti**：memory 层（详见 L13.X memory 子章）
- **Anthropic Skills**（开标准 2025-12）：progressive disclosure，name+desc 启动加载，body 触发后才载入
