#!/usr/bin/env python3
"""Markdown → 单 HTML 文件 (含目录 + Mermaid 图表 + 浅暗色自适应 + 图解 caption).

Usage:
    python3 scripts/md_to_html.py docs/rag-knowledge-map.md docs/rag-knowledge-map.html

特性:
- 单文件 (双击浏览器打开即可, 无需 server)
- 左侧固定 TOC (h2/h3), 暗色/亮色随系统
- 在关键章节自动插入 Mermaid 图 + 图解 caption (深化讲解)
- 25+ 流程图: 5 层架构 / Write Path / Read Path / Agent / Cache / Failure Mode 等
- 表格 / 代码块自动美化
- 移动端响应式
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import markdown


# ============================================================
# 关键章节自动插入 Mermaid 图
# key = heading 文本片段 (匹配 h3/h4/h5)
# value = (caption 图解说明, mermaid 代码)
# ============================================================
MERMAID_DIAGRAMS: dict[str, tuple[str, str]] = {

    # ========= §〇 速览 =========
    "企业 RAG 5 层架构 (按职责分层, 不绑流量)": (
        "📐 正确架构: 写路径 (L1+L2 离线基础) + 读路径 (L3+L4+L5 在线决策) + Generation (100% 必经终点) + 横切. "
        "100% query 都经过 L4 Router (入口) + L3 检索 + Generation. "
        "80/15/5 是 Router 决策后的'路径分布', 不是某层独占流量. "
        "投资比例: 70% L1-L2, 20% L3-L4, 10% L5+横切.",
        """graph TB
    subgraph WritePath ["📦 离线写路径 (Write Path) — 文档入库"]
        L1["Layer 1: Data Governance<br/>数据治理 100% 必经"]
        L2["Layer 2: Index Quality<br/>索引质量 100% 必索引"]
        L1 --> L2
    end

    subgraph ReadPath ["🔍 在线读路径 (Read Path) — 用户 query"]
        Q["👤 用户 query"]
        L4["Layer 4: Query Routing<br/>查询路由 100% 必经入口"]
        L3["Layer 3: Retrieval & Rerank<br/>检索+重排 100% 都用"]
        L5["Layer 5: Agent Orchestration<br/>智能体调度 仅 5% 走"]
        Gen["Generation Layer<br/>LLM + Validator 100% 必到"]
        Q --> L4
        L4 -->|80% 普通| L3
        L4 -->|15% 增强| L3
        L4 -->|5% Agent| L5
        L5 -.->|多次调| L3
        L3 --> Gen
        L5 --> Gen
    end

    L2 -.->|索引可读| L3

    Cross["🔄 横切: ACL / Audit / Cost / Observability"]
    L1 -.- Cross
    L4 -.- Cross
    Gen -.- Cross

    style L1 fill:#10B981,color:#fff
    style L2 fill:#22C55E,color:#fff
    style L3 fill:#84CC16,color:#fff
    style L4 fill:#A855F7,color:#fff
    style L5 fill:#EC4899,color:#fff
    style Gen fill:#3B82F6,color:#fff
    style Cross fill:#F97316,color:#fff"""
    ),

    "80/15/5 路径分流原则": (
        "📊 Router 决策后的路径分布 (Glean / Notion / Microsoft 内部数据). "
        "100% query 都经过 Router (L4), Router 根据 query 复杂度分流. "
        "注意: 这是'路径分布'不是'层独占流量'. 100% query 也都用 L3 检索 + Generation. "
        "反向用法: 跑 1 周 traces 看真实分布, 不是 80/15/5 → Router 没做好.",
        """pie showData
    title Router 决策后路径分布 (100% query 都经过 Router)
    "普通 RAG 路径 (L3 + Gen)" : 80
    "增强 RAG 路径 (L3 + HyDE/Multi-Query + Gen)" : 15
    "Agent 路径 (L5 多步 + L3 多次 + Tools + Gen)" : 5"""
    ),

    "RAG 4 代演进": (
        "🕒 RAG 4 代演进时间线: 不替代而叠加. 现代企业 RAG 系统 4 代并存, "
        "Naive RAG 在简单 FAQ 仍是最优 (快+便宜), Agent 在跨系统场景才有价值. "
        "选最适合的代, 不是最新的代.",
        """timeline
    title RAG 4 代演进 (不替代而叠加)
    2022 : Gen 1 Naive RAG
         : query→embed→search→prompt→LLM
    2023 : Gen 2 Advanced RAG
         : + Reranker + HyDE + 父子分块
    2024 : Gen 3 Modular RAG
         : 7 模块可插拔微服务化
    2025-2026 : Gen 4 Agent + RAG
              : Plan + Tool + 多步推理 + 自纠错"""
    ),

    "完整数据流 — 离线索引构建阶段": (
        "📦 离线 Index Build 必须先做, 否则在线检索没数据. "
        "工业标准: 三存储 (Vector DB + Inverted Index + Doc Store), 不是双存储. "
        "Vector DB 存稠密向量做语义检索, Inverted Index 存倒排表做 BM25 字面检索, Doc Store 存原文供 LLM 读. "
        "同一个 chunk_id 是三个存储的连接键. 漏掉 BM25 是 60% 单 Dense 项目栽倒的根因.",
        """graph LR
    Doc["📄 原始文档<br/>PDF/Word/网页/API"] --> Parse["Parser 解析<br/>结构化文本+元数据"]
    Parse --> Chunk["Chunking 分块<br/>200-1024 字/块<br/>分配 chunk_id"]
    Chunk --> Split{分流三路并行}

    Split -->|chunk text| Embed["Embedder 向量化<br/>BGE-M3 / OpenAI text-3<br/>→ 1024 维向量"]
    Embed --> VDB[("🔵 向量库<br/>pgvector / Pinecone<br/>chunk_id + vector<br/>HNSW 索引")]

    Split -->|chunk text| Token["分词 + 倒排表<br/>jieba / nltk<br/>+ IDF + len + avgdl"]
    Token --> IDX[("🟠 倒排索引库<br/>Elasticsearch / tsvector<br/>term → chunk_id 倒排表<br/>GIN 索引")]

    Split -->|原文+chunk_id| DocDB[("🟢 文档库<br/>Postgres / Redis<br/>chunk_id + text + metadata<br/>B-tree 索引")]

    VDB -.->|chunk_id 连接键| DocDB
    IDX -.->|chunk_id 连接键| DocDB

    style Doc fill:#3B82F6,color:#fff
    style VDB fill:#A855F7,color:#fff
    style IDX fill:#F59E0B,color:#fff
    style DocDB fill:#10B981,color:#fff"""
    ),

    "完整数据流 — 在线检索与生成阶段": (
        "🔍 在线 Hybrid 检索 + 生成 9 步. ⭐ 易忽略: (1) Query 双路预处理 (Embedder + Tokenizer 必须用入库时同一套) "
        "(2) 双路并行 (asyncio.gather, 总延迟 = max 不是 sum) (3) RRF 融合 (用 rank 不用 score, 兼容两路) "
        "(4) 喂给 LLM 的是原文 (text), 向量和 score 只是检索中间产物 (5) Query 和 Doc 必须用同一套 Embedder + Tokenizer.",
        """graph TB
    Q["👤 用户 query<br/>'RF12345 退款流程'"] --> Pre{Query 双路预处理}

    Pre -->|路径 A| QE["Query Embedding<br/>⭐ 同一个 Embedder<br/>→ 1024 维向量"]
    Pre -->|路径 B| QT["Query 分词<br/>⭐ 同一个 tokenizer<br/>→ ['RF12345', '退款', '流程']"]

    QE --> ANN["🔵 ANN 向量库搜索<br/>HNSW + cosine<br/>→ top-50 chunk_id<br/>(语义近邻)"]
    QT --> BM25["🟠 倒排索引查询<br/>BM25 公式打分<br/>→ top-50 chunk_id<br/>(字面命中 RF12345)"]

    ANN --> RRF["⭐ RRF 融合<br/>score = Σ 1/(k+rank), k=60<br/>→ top-20 chunk_id"]
    BM25 --> RRF

    RRF --> Rerank["🎯 Reranker 精排 (可选)<br/>BGE-Reranker-v2-M3<br/>Cross-Encoder<br/>→ top-5 chunk_id"]
    Rerank --> Lookup["🔎 回查文档库<br/>SELECT text WHERE chunk_id IN ..."]
    Lookup --> Texts["📄 top-5 原文片段 (text)"]
    Texts --> Prompt["Prompt 拼接<br/>system + 原文 + query"]
    Prompt --> LLM["🤖 LLM 推理<br/>⭐ 喂的是原文 text<br/>向量和 score 是检索中间产物"]
    LLM --> Ans["✅ 答案 + 引用<br/>用 chunk_id 反查 URL"]

    style Q fill:#3B82F6,color:#fff
    style QE fill:#A855F7,color:#fff
    style QT fill:#F59E0B,color:#fff
    style ANN fill:#A855F7,color:#fff
    style BM25 fill:#F59E0B,color:#fff
    style RRF fill:#EC4899,color:#fff
    style Rerank fill:#EF4444,color:#fff
    style LLM fill:#3B82F6,color:#fff
    style Ans fill:#10B981,color:#fff"""
    ),

    "5 个最容易被忽略的事实": (
        "🎯 RAG 5 个高频面试坑: (1) 三存储不是双存储 — 漏 BM25 是大坑 "
        "(2) Hybrid 双路并行不是单 Dense (3) 向量库返 chunk_id 不返答案 "
        "(4) 喂给 LLM 的是原文 text, 向量和 score 找完就丢 (5) Query 和 Doc 必须用同一套预处理.",
        """graph TB
    subgraph Wrong ["❌ 常见误区"]
        W1["误区 1<br/>RAG = 向量库 + LLM<br/>两个组件够了"]
        W2["误区 2<br/>用了向量库 BM25 就过时了"]
        W3["误区 3<br/>向量库直接返回答案"]
        W4["误区 4<br/>把向量/score 塞给 LLM"]
        W5["误区 5<br/>doc 用 BGE, query 用 OpenAI"]
    end

    subgraph Right ["✅ 真相"]
        R1["真相 1<br/>三存储: Vector DB + Inverted Index + Doc Store<br/>chunk_id 三方连接键"]
        R2["真相 2<br/>BM25 (1994) 在 SKU/编号/错别字/代码<br/>4 类 query 上 Dense 完全打不过"]
        R3["真相 3<br/>向量库返 chunk_id, 原文要回查 Doc Store"]
        R4["真相 4<br/>LLM 输入只有 token<br/>cosine/BM25/Reranker 三种 score 都不喂 LLM"]
        R5["真相 5<br/>必须同一个 Embedder + tokenizer<br/>否则向量空间/分词都不兼容"]
    end

    W1 --> R1
    W2 --> R2
    W3 --> R3
    W4 --> R4
    W5 --> R5

    style W1 fill:#EF4444,color:#fff
    style W2 fill:#EF4444,color:#fff
    style W3 fill:#EF4444,color:#fff
    style W4 fill:#EF4444,color:#fff
    style W5 fill:#EF4444,color:#fff
    style R1 fill:#10B981,color:#fff
    style R2 fill:#10B981,color:#fff
    style R3 fill:#10B981,color:#fff
    style R4 fill:#10B981,color:#fff
    style R5 fill:#10B981,color:#fff"""
    ),

    "BM25 在 RAG 中扮演的角色": (
        "🟠 BM25 不是替代 Dense, 是与 Dense 并列的第二条召回通道. "
        "Dense 长项: 语义近邻 (退款 ↔ 返金). BM25 长项: 字面精确 (RF12345 / iPhone 16 Pro Max 1TB). "
        "工业标准: Hybrid (Dense + BM25 + RRF), 召回 +15-30% NDCG.",
        """graph LR
    Q["👤 query"] --> Type{query 类型?}

    Type -->|自然语言| D["🔵 Dense 强项<br/>语义近邻<br/>BGE-M3 + HNSW<br/>例: 退款流程"]
    Type -->|SKU/编号| B1["🟠 BM25 强项<br/>字面精确<br/>例: RF12345"]
    Type -->|数字日期| B2["🟠 BM25 强项<br/>例: iPhone 16 Pro 1TB"]
    Type -->|错别字| B3["🟠 BM25 强项<br/>N-gram 模糊<br/>例: 退欵"]
    Type -->|代码命令| B4["🟠 BM25 强项<br/>字符级匹配<br/>例: asyncio.gather"]

    D --> Hybrid["🔥 Hybrid Search<br/>双路并行<br/>asyncio.gather"]
    B1 --> Hybrid
    B2 --> Hybrid
    B3 --> Hybrid
    B4 --> Hybrid

    Hybrid --> RRF["RRF 融合<br/>k=60"]
    RRF --> Top["top-K 互补召回<br/>+15-30% NDCG"]

    style Q fill:#3B82F6,color:#fff
    style D fill:#A855F7,color:#fff
    style B1 fill:#F59E0B,color:#fff
    style B2 fill:#F59E0B,color:#fff
    style B3 fill:#F59E0B,color:#fff
    style B4 fill:#F59E0B,color:#fff
    style Hybrid fill:#EC4899,color:#fff
    style Top fill:#10B981,color:#fff"""
    ),

    # ========= §一 基础原理 =========
    "Gen 1: Naive RAG (2022)": (
        "🟦 Naive RAG 单线流水: 早期 LangChain demo / ChatGPT Retrieval Plugin. "
        "实现 10 行代码. 但生产中栽: 专有名词召不到 / 多跳拿不齐 / 模糊 query 答非所问 / 无拒答.",
        """graph LR
    Q["Query 用户问题"] --> E["Embedding 向量化"]
    E --> S["Vector Search<br/>top-K"]
    S --> P["Prompt 拼接"]
    P --> LLM["LLM 生成"]
    LLM --> A["Answer"]

    style Q fill:#3B82F6,color:#fff
    style A fill:#10B981,color:#fff"""
    ),

    "Gen 4: Agent + RAG (2025-2026)": (
        "🤖 Agent + RAG: Modular 之上加智能调度. LLM 自主决定要不要查/查几次/查什么. "
        "代价: 一次 query 跑 5-10 步 = 5-10× 成本 + 死循环风险. "
        "必须限制 max_steps=8, timeout=8s, budget cap.",
        """graph TD
    Q["Query 用户问题"] --> P["Planner 规划<br/>(Sonnet 4 / o3)"]
    P --> Step1["Step 1: 调 Tool A"]
    Step1 --> Eval1{"够答了?"}
    Eval1 -->|否| Step2["Step 2: 调 Tool B"]
    Eval1 -->|是| LLM["LLM 综合"]
    Step2 --> Eval2{"够答了?"}
    Eval2 -->|否| StepN["Step N: 继续..."]
    Eval2 -->|是| LLM
    StepN --> LLM
    LLM --> A["Answer + 引用"]

    Limit["⚠️ 限制: max_steps=8<br/>timeout=8s<br/>budget cap"]
    P -.- Limit

    style Q fill:#3B82F6,color:#fff
    style A fill:#10B981,color:#fff
    style Limit fill:#EF4444,color:#fff"""
    ),

    "2025-2026 Agent RAG 最新发展": (
        "🚀 2026 标准 Agent RAG 七层架构: Query Understanding → Router → Orchestrator (Planner) → "
        "Tool Execution Loop (RAG/SQL/Web/Browser) → Memory (3 层) → Synthesizer → Validator. "
        "对比 2024 demo, 2026 增加: MCP 协议化 / Reasoning Model (o3) / Computer Use / Multi-Agent 团队 / Self-Improving.",
        """graph TB
    User["👤 用户 query"]
    User --> L1["Layer 1: Query Understanding<br/>意图分类 + 复杂度评估"]
    L1 --> L2{"Layer 2: Router<br/>三层混合"}
    L2 -->|简单 80%| RAG["普通 RAG<br/>Hybrid + Reranker"]
    L2 -->|复杂 5%| L3["Layer 3: Orchestrator<br/>Planner LLM (Sonnet 4 / o3)<br/>生成执行计划"]

    L3 --> L4["Layer 4: Tool Execution Loop"]

    subgraph Tools["🔧 Tool Registry (MCP 协议)"]
        T1["RAG Search"]
        T2["Web Search<br/>(Tavily / SerpAPI)"]
        T3["SQL Query<br/>(Text2SQL)"]
        T4["Function Call<br/>(业务 API)"]
        T5["Browser<br/>(Computer Use)"]
        T6["Code Interpreter<br/>(Python sandbox)"]
    end

    L4 --> Tools
    Tools --> Eval{"信息够吗?"}
    Eval -->|不够 < 8 步| L4
    Eval -->|够了| L5["Layer 5: Memory<br/>L1 Session (Redis)<br/>L2 User Pref (PG)<br/>L3 Business (pgvector)"]
    L5 --> L6["Layer 6: Synthesizer<br/>(Haiku 综合)"]
    L6 --> L7["Layer 7: Validator<br/>Faithfulness / Citation / PII"]
    L7 -->|通过| Ans["✅ 答案 + 引用"]
    L7 -->|拒答| Refuse["❌ 拒答 / 转人工"]
    RAG --> L7

    Cost["💰 Cost Controller<br/>max_steps=8<br/>per_query $1<br/>per_user_day $50"]
    L4 -.- Cost

    style User fill:#3B82F6,color:#fff
    style L3 fill:#EC4899,color:#fff
    style L4 fill:#A855F7,color:#fff
    style Tools fill:#F59E0B,color:#000
    style L5 fill:#10B981,color:#fff
    style Ans fill:#10B981,color:#fff
    style Refuse fill:#EF4444,color:#fff
    style Cost fill:#EF4444,color:#fff"""
    ),

    "5 大新趋势 (2025-2026)": (
        "🔥 2025-2026 Agent RAG 5 大演进: MCP 协议统一工具生态 / Reasoning Model (o3) 推理深化 / "
        "Computer Use 操作 GUI / Multi-Agent 团队化 / Self-Improving Episodic Memory. "
        "对比 2024 早期 Agent (各自为政), 2026 已有标准化 + 团队化 + 学习能力.",
        """graph LR
    Old["2024 早期 Agent<br/>(实验阶段)"]:::old

    subgraph Trends["🚀 2025-2026 5 大趋势"]
        T1["1. MCP 协议化<br/>统一工具调用<br/>1000+ MCP Server"]
        T2["2. Reasoning Model<br/>o1/o3/R1 + Agent<br/>显式推理链"]
        T3["3. Computer Use<br/>Anthropic / Google<br/>操作 GUI/浏览器"]
        T4["4. Multi-Agent 团队<br/>Magentic-One<br/>Orchestrator+Worker"]
        T5["5. Self-Improving<br/>Reflexion / Voyager<br/>Episodic Memory"]
    end

    New["2025-2026 成熟 Agent<br/>(生产/商业化)"]:::new

    Old --> T1
    Old --> T2
    Old --> T3
    Old --> T4
    Old --> T5

    T1 --> New
    T2 --> New
    T3 --> New
    T4 --> New
    T5 --> New

    classDef old fill:#9CA3AF,color:#fff
    classDef new fill:#10B981,color:#fff
    style T1 fill:#3B82F6,color:#fff
    style T2 fill:#A855F7,color:#fff
    style T3 fill:#EC4899,color:#fff
    style T4 fill:#F59E0B,color:#000
    style T5 fill:#06B6D4,color:#fff"""
    ),

    # ========= §二 业务流程 =========
    "RAG 整体业务流程": (
        "🌐 RAG 业务流程鸟瞰: 5 个核心环节 + 3 个支撑系统. "
        "用户提问到答案返回中间所有步骤都可监控/审计/优化. "
        "支撑系统决定上限: 文档入库决定知道什么, ACL 决定能给谁看, 监控决定能持续优化.",
        """graph LR
    U["👤 用户提问<br/>Query"] --> R["🔍 系统找资料<br/>Retrieve"]
    R --> O["📋 整理资料<br/>Rerank + Context Build"]
    O --> G["🤖 LLM 生成答案<br/>Generate"]
    G --> V["✅ 引用校验 + 拒答<br/>Validator"]
    V --> Render["💬 给用户看<br/>Render + Cite"]

    Ingest["📥 文档入库<br/>Ingestion"] -.-> R
    ACL["🔒 权限审计<br/>ACL + Audit"] -.-> R
    Obs["📊 监控评估<br/>Observability"] -.-> Render

    style U fill:#3B82F6,color:#fff
    style Render fill:#10B981,color:#fff
    style Ingest fill:#F59E0B,color:#fff
    style ACL fill:#EF4444,color:#fff
    style Obs fill:#6366F1,color:#fff"""
    ),

    "5 步流程": (
        "📥 Ingestion 5 步流水: 上传 → 解析 → 分块 → 编码 → 入库. "
        "100 万文档典型耗时: 解析 2-5 小时 (LlamaParse), 编码 1-2 小时 (BGE-M3 GPU), "
        "总成本 $200-2000. 增量同步: 5000 新文档/天 ~30 分钟.",
        """graph LR
    U["📤 上传文档<br/>(PDF/Word/Markdown)"] --> P["📄 解析 Parse<br/>(LlamaParse / GPT-4o)"]
    P --> C["✂️ 切块 Chunking<br/>(256-1024 字)"]
    C --> E["🧮 向量编码 Embedding<br/>(BGE-M3 → 1024 维)"]
    E --> I["💾 入库 Index<br/>(Vector DB + 关系库)"]

    style U fill:#3B82F6,color:#fff
    style I fill:#10B981,color:#fff"""
    ),

    "退款失败诊断": (
        "🔍 Agent 多步推理实战: 跨 4 个业务系统 (订单+支付+日志+风控) 完成诊断. "
        "替代 1 个 L3 工程师 5 分钟工作. 单次成本 $0.05-0.5, 延迟 5-30s, "
        "但答案准确+可执行 (业务系统实时数据).",
        """sequenceDiagram
    autonumber
    participant U as 👤 用户
    participant A as 🤖 Agent
    participant O as 订单服务
    participant P as 支付通道
    participant L as 日志服务
    participant R as 风控服务

    U->>A: "为什么订单 12345 退款失败?"
    A->>O: get_order_status("12345")
    O-->>A: status=refund_failed, error_code=RF102
    A->>P: lookup_error_code("RF102")
    P-->>A: "原支付卡已失效"
    A->>L: get_retry_log("12345")
    L-->>A: ["retry 1 failed", "retry 2 failed"]
    A->>R: get_risk_log("12345")
    R-->>A: {risk_level: low, blocked: false}
    A-->>U: "订单退款失败. 原因: 原支付卡已失效 (RF102),<br/>系统已自动重试 2 次. 建议: 联系用户更换收款方式."
"""
    ),

    # ========= §三 5 层架构总览 =========
    "正确的层级模型 (写路径 + 读路径 + 横切)": (
        "🏗️ 正确架构: 100% query 都经过 L4 Router (入口) + L3 检索 + Generation (终点). "
        "Router 根据复杂度决策: 80% 普通 RAG, 15% 增强 RAG, 5% Agent. "
        "L1+L2 是离线写路径 (基础设施), L3+L4+L5 是在线读路径. "
        "Generation Layer 100% 必经 (LLM + Validator). 横切贯穿所有.",
        """graph TB
    subgraph WritePath ["📦 离线写路径"]
        L1["L1 Data Governance<br/>数据治理 100% 文档必经"]
        L2["L2 Index Quality<br/>索引质量 100% 文档必索引"]
        L1 --> L2
    end

    subgraph ReadPath ["🔍 在线读路径"]
        Q["👤 用户 query"]
        L4["L4 Query Routing<br/>路由 100% 必经入口"]
        L3["L3 Retrieval & Rerank<br/>检索 100% 都用"]
        L5["L5 Agent Orch<br/>Agent 仅 5% 走"]
        Gen["Generation Layer<br/>LLM + Validator 100% 必到"]
        Q --> L4
        L4 -->|80% 普通| L3
        L4 -->|15% 增强| L3
        L4 -->|5% Agent| L5
        L5 -.->|多次调| L3
        L3 --> Gen
        L5 --> Gen
    end

    L2 -.->|索引可读| L3

    subgraph CrossCut ["🔄 横切关注点"]
        ACL[ACL 三层防御]
        Audit[Audit chunk-level]
        Cost[Cost 5 层缓存]
        Obs[Observability]
    end
    L1 -.- CrossCut
    L4 -.- CrossCut
    Gen -.- CrossCut

    style L1 fill:#10B981,color:#fff
    style L2 fill:#22C55E,color:#fff
    style L3 fill:#84CC16,color:#fff
    style L4 fill:#A855F7,color:#fff
    style L5 fill:#EC4899,color:#fff
    style Gen fill:#3B82F6,color:#fff
    style CrossCut fill:#F97316,color:#fff"""
    ),

    "5 层接口契约": (
        "🔌 5 层接口契约: 每层职责清晰, 输入输出明确. 工程实施时按此契约划分服务边界. "
        "写路径 (L1→L2) 离线一次性. 读路径 (用户 query → L4 → L3/L5 → Generation) 实时. "
        "Generation 是 100% 必经终点.",
        """graph LR
    Doc["📥 用户文档"] --> L1["L1 数据治理<br/>清洁 chunks + ACL"]
    L1 --> L2["L2 索引质量<br/>vector + sparse 索引"]
    Q["🔍 用户 query"] --> L4["L4 Router<br/>路径决策"]
    L2 -.->|索引就绪| L3
    L4 -->|普通/增强| L3["L3 Hybrid 检索<br/>ranked top-K chunks"]
    L4 -->|复杂| L5["L5 Agent<br/>多步 + 工具"]
    L5 -.-> L3
    L3 --> Gen["Generation Layer<br/>LLM + Validator"]
    L5 --> Gen
    Gen --> Out["💬 用户输出<br/>answer + citations"]

    style Doc fill:#10B981,color:#fff
    style Q fill:#3B82F6,color:#fff
    style Gen fill:#3B82F6,color:#fff
    style Out fill:#10B981,color:#fff"""
    ),

    # ========= §四 L1 数据治理 =========
    "Ingestion 完整写流程": (
        "📥 完整 Write Path 7 步流水: 业界标准做法. 每步失败进 dead letter queue, "
        "3 次重试后通知管理员. 单 PDF 平均 50 页耗时 15-55s. 100 万文档 batch 约 7 天 "
        "(100 worker × 30s = 6000/小时).",
        """graph TD
    Upload["1️⃣ 用户上传 PDF / Connector 同步"] --> Parse["2️⃣ Parse 解析<br/>LlamaParse/Marker/GPT-4o"]
    Parse --> Boilerplate["3️⃣ Boilerplate 噪声过滤<br/>页眉页脚剥离"]
    Boilerplate --> PII["4️⃣ PII 检测<br/>Microsoft Presidio + 中文 NER"]
    PII --> Dedup["5️⃣ Deduplication 去重<br/>SHA256 + MinHash + Embedding"]
    Dedup --> Quality["6️⃣ Quality Gating<br/>LLM-as-judge 3 维度 5 分制"]
    Quality --> Meta["7️⃣ Metadata Enricher<br/>NER + topic + summary"]
    Meta --> L2["进入 L2 索引层"]

    Dedup -->|重复| Skip["跳过, 引用已有 chunk_id"]
    Quality -->|score < 8/15| Quarantine["进 quarantine 队列<br/>人工 review"]

    style Upload fill:#3B82F6,color:#fff
    style L2 fill:#10B981,color:#fff
    style Skip fill:#EF4444,color:#fff
    style Quarantine fill:#F59E0B,color:#fff"""
    ),

    "三层去重策略": (
        "🔍 三层去重: 完全 → 近似 → 语义. SHA256 抓完全重复 (50%+), "
        "MinHash + LSH 抓近似 (Jaccard > 0.85, 18%), "
        "Embedding cosine > 0.95 抓语义 (5-10%). 综合可去重 70-90%. "
        "Confluence 5 万文档实测去重率 35%, 索引体积 -35%, 召回噪声 -25%.",
        """graph TD
    Chunk["新 chunk"] --> H1{Layer 1: SHA256<br/>完全重复?}
    H1 -->|Hit| Skip1["跳过, 引用已有"]
    H1 -->|Miss| H2{Layer 2: MinHash + LSH<br/>Jaccard > 0.85?}
    H2 -->|Hit| Skip2["近似重复, 跳过"]
    H2 -->|Miss| H3{Layer 3: Embedding<br/>cosine > 0.95?}
    H3 -->|Hit| Skip3["语义重复, 跳过"]
    H3 -->|Miss| Insert["✅ 入库"]

    style Chunk fill:#3B82F6,color:#fff
    style Insert fill:#10B981,color:#fff
    style Skip1 fill:#EF4444,color:#fff
    style Skip2 fill:#F59E0B,color:#fff
    style Skip3 fill:#A855F7,color:#fff"""
    ),

    "时效性管理": (
        "⏰ 时效性管理: 90% 项目忽视, 但极重要. 三种衰减函数选用. "
        "Notion 实测: 公司知识半衰期 90 天, 个人笔记 180 天, 政策 365 天. "
        "Glean: Slack 30 天, 邮件 60 天, Confluence 180 天.",
        """graph LR
    Doc["📄 文档"] --> Meta["+ created_at<br/>+ last_modified<br/>+ expires_at"]
    Meta --> F["recency_decay 函数"]
    F --> Exp["指数衰减<br/>weight = exp(-λ × age)<br/>新闻场景"]
    F --> Lin["线性衰减<br/>weight = 1 - age/max_age<br/>政策场景"]
    F --> Step["阶梯函数<br/>1y:1.0 / 1-2y:0.5 / 2y+:0.1<br/>法规场景"]

    Exp --> Final["final_score = retrieval × (0.7 + 0.2×authority + 0.1×decay)"]
    Lin --> Final
    Step --> Final

    style Doc fill:#3B82F6,color:#fff
    style Final fill:#10B981,color:#fff"""
    ),

    # ========= §五 L2 索引质量 =========
    "完整 Index Build Path 端到端": (
        "🔨 Index Build Path 完整端到端: 100 万 chunk 典型耗时 3-4 小时. "
        "Contextual Retrieval 用 Haiku $50-100 一次性投入, 召回失败率 -49%. "
        "增量更新: 老 chunk 软删 + 新版入库, HNSW 不支持 in-place 删 → 周期 REINDEX.",
        """graph LR
    In["L1 cleaned chunks"] --> Chunk["Chunking 策略<br/>(父子分块默认)"]
    Chunk --> Ctx["Contextual Retrieval (可选)<br/>Anthropic Haiku 加 50-100 字 prefix"]
    Ctx --> Emb["Embedding 推理<br/>BGE-M3 batch=32"]
    Emb --> Norm["L2 归一化"]
    Norm --> VecIdx["Vector Index 构建<br/>HNSW M=16 ef=200"]
    Norm --> SparseIdx["Sparse Index 构建<br/>tsvector / SPLADE"]
    VecIdx --> Out["可检索索引"]
    SparseIdx --> Out

    style In fill:#22C55E,color:#fff
    style Out fill:#84CC16,color:#fff"""
    ),

    "Chunking 8 种策略": (
        "🍰 8 种 Chunking 策略对比: 召回 NDCG 从 0.55 (固定窗口) 到 0.83 (Contextual). "
        "业界主流: 通用用父子分块 + Contextual Retrieval, 代码用 AST-aware, "
        "长 context 模型用 Late Chunking (Jina 0 LLM 调用).",
        """graph TD
    Doc["原始文档"] --> Choose{选择策略}
    Choose --> Fixed["固定窗口<br/>NDCG 0.55"]
    Choose --> Recur["递归字符<br/>NDCG 0.62"]
    Choose --> Sent["句子窗口<br/>NDCG 0.68"]
    Choose --> Parent["父子分块<br/>NDCG 0.72"]
    Choose --> Sem["语义分块<br/>NDCG 0.74"]
    Choose --> Late["Late Chunking<br/>NDCG 0.82"]
    Choose --> Ctx["Contextual<br/>NDCG 0.83"]
    Choose --> AST["AST-aware<br/>代码 +25%"]

    style Fixed fill:#94A3B8,color:#fff
    style Ctx fill:#10B981,color:#fff
    style Late fill:#22C55E,color:#fff
    style AST fill:#A855F7,color:#fff"""
    ),

    "Embedder 推理流程": (
        "🧮 Embedder Forward Pass: Transformer Encoder + Mean Pooling + L2 归一化. "
        "BGE-M3 单 GPU A10 batch=32 推理 ~50ms = 640 doc/s. "
        "归一化后 cosine == dot product, BGE/Qwen3 默认归一化 → 用 IP 距离 (快 30%).",
        """graph LR
    Text["文本"] --> Tok["tokenize<br/>(subword)"]
    Tok --> IDs["token IDs<br/>+ position embedding"]
    IDs --> Trans["Transformer Encoder<br/>(N 层 self-attn + FFN)"]
    Trans --> Hidden["token-level<br/>hidden states"]
    Hidden --> Pool["Mean Pooling<br/>(BGE/Qwen3) 或 CLS pooling"]
    Pool --> Norm["L2 归一化"]
    Norm --> Vec["1024 维向量"]

    style Text fill:#3B82F6,color:#fff
    style Vec fill:#10B981,color:#fff"""
    ),

    "HNSW (Hierarchical Navigable Small World)": (
        "🕸️ HNSW 多层近邻图: Malkov & Yashunin 2018. 业界主流向量索引. "
        "上层稀疏 (远跳, 类似高速公路), 下层密集 (精搜, 类似乡道). "
        "查询从顶层贪心走到 layer 0, 用 ef_search=100 候选池精搜. "
        "内存 = 单向量 4.3KB × 数量, 1 亿向量 = 430GB → 必须量化或分片.",
        """graph TB
    Q["query vector"] --> EP["Layer 2: 入口<br/>(稀疏, 远跳)"]
    EP -->|贪心走| L1["Layer 1: 中层"]
    L1 -->|逐层下降| L0["Layer 0: 密集<br/>(ef_search 候选池)"]
    L0 --> Top["返回 top-K"]

    Note["⚠️ 关键参数:<br/>M=16 邻居数<br/>ef_construction=200<br/>ef_search=100 (甜点)"]

    style Q fill:#3B82F6,color:#fff
    style Top fill:#10B981,color:#fff
    style Note fill:#F59E0B,color:#fff"""
    ),

    # ========= §六 L3 检索 =========
    "完整 Read Path 端到端总结": (
        "🔍 Query Read Path 完整流程: 业界默认配置. 总延迟 ~1.2s. "
        "HyDE 默认开 (1 LLM 调用 +10% 召回). Hybrid + RRF + Reranker + LongContextReorder 是业界最佳实践. "
        "高价值场景再加 Multi-Query + Reranker Cascade + LLM Verifier 总 3-5s 但 NDCG 顶级.",
        """graph TD
    Q["👤 用户 query"] --> HyDE["HyDE 生成假设文档<br/>(1 LLM 调用)"]
    HyDE --> Hybrid["Hybrid Search 并行"]
    Hybrid --> Dense["Dense 检索<br/>BGE-M3 + HNSW<br/>top-50"]
    Hybrid --> Sparse["Sparse 检索<br/>BM25 + jieba<br/>top-50"]
    Dense --> RRF["RRF Fusion (k=60)<br/>top-20"]
    Sparse --> RRF
    RRF --> Rerank["BGE-Reranker-v2-M3<br/>top-10"]
    Rerank --> Reorder["LongContextReorder<br/>头尾置重要"]
    Reorder --> Refusal{Faithfulness ≥ 0.85?}
    Refusal -->|No| Reject["拒答 / 转人工"]
    Refusal -->|Yes| Out["Top-5 chunks → Generation"]

    style Q fill:#3B82F6,color:#fff
    style Out fill:#84CC16,color:#fff
    style Reject fill:#EF4444,color:#fff"""
    ),

    "三通道并行执行": (
        "⚡ 三通道并行检索: asyncio.gather 同时跑 Dense + Sparse + Keyword. "
        "总延迟 = max(三路) 而非 sum, 性能 1.5-3× 加速. "
        "Dense 召回语义相近, Sparse 召回专有名词/SKU/错别字, Keyword 抓 UUID/IP 强标识. 三路互补.",
        """graph TD
    Q["query"] --> P1["Dense<br/>HNSW + BGE-M3<br/>top-50"]
    Q --> P2["Sparse<br/>BM25 + jieba<br/>top-50"]
    Q --> P3["Keyword<br/>正则 + 倒排<br/>top-50"]
    P1 --> Merge["RRF 融合<br/>(k=60)"]
    P2 --> Merge
    P3 --> Merge
    Merge --> Final["top-K"]

    style Q fill:#3B82F6,color:#fff
    style Final fill:#84CC16,color:#fff"""
    ),

    "为了解决什么问题": (
        "📜 BM25 不是 TF-IDF 的微调, 是为了修复 TF-IDF 在 1980-1990 年代暴露的 3 个根本缺陷而生. "
        "1994 Robertson + Spärck Jones 在 TREC-3 提出, 30 年后仍是 Elasticsearch / Lucene / Solr / Postgres tsvector 的默认排序算法. "
        "看清这 3 个缺陷 → 才能理解 BM25 公式里每一项为什么这么写.",
        """graph LR
    subgraph TFIDF ["❌ TF-IDF 1972-1990 三大致命缺陷"]
        F1["缺陷 1: 长文档 bias<br/>长文档 TF 高 → 排第一<br/>但短而 focused 的更相关"]
        F2["缺陷 2: TF 无上限<br/>词出现 100 次 = 重要 10×<br/>实际 5 次和 100 次差不多"]
        F3["缺陷 3: 无法调归一化强度<br/>不同领域文档长度差异大<br/>要么不归一化要么死归一化"]
    end

    subgraph BM25 ["✅ BM25 1994 三大修复"]
        Fix1["修复 1: 长度归一化<br/>引入 |d| / avgdl 项<br/>长短文档公平打分"]
        Fix2["修复 2: TF 饱和函数<br/>TF × (k1+1) / (TF + k1)<br/>有上界, 边际递减"]
        Fix3["修复 3: 可调 b 参数<br/>b ∈ [0, 1], 默认 0.75<br/>领域适配灵活"]
    end

    F1 --> Fix1
    F2 --> Fix2
    F3 --> Fix3

    Fix1 --> Result["📊 BM25 最终公式<br/>score = Σ IDF × TF×(k1+1) / (TF + k1×(1-b+b×|d|/avgdl))<br/>30 年工业默认"]
    Fix2 --> Result
    Fix3 --> Result

    style F1 fill:#EF4444,color:#fff
    style F2 fill:#EF4444,color:#fff
    style F3 fill:#EF4444,color:#fff
    style Fix1 fill:#10B981,color:#fff
    style Fix2 fill:#10B981,color:#fff
    style Fix3 fill:#10B981,color:#fff
    style Result fill:#3B82F6,color:#fff"""
    ),

    "为什么 RAG 时代 BM25 仍是必选": (
        "🎯 Dense (语义检索) 不能取代 BM25, 二者互补不是替代. "
        "Dense 在 4 类查询上有盲区: 专有名词 / 数字日期 / 错别字 / 代码命令. "
        "工业标准: Hybrid (Dense + BM25 + RRF), 60% 单 Dense 项目栽倒就是因为没加 BM25. "
        "Klarna / Notion / Glean / Anthropic 全用 Hybrid.",
        """graph TB
    Q["👤 用户 query"] --> Split{"query 类型?"}

    Split -->|自然语言| Dense["✅ Dense 强项<br/>BGE-M3 / OpenAI text-3<br/>语义理解 + 同义词<br/>例: 退款流程是什么"]
    Split -->|含 SKU 编号| BM25_1["✅ BM25 强项<br/>精确词形匹配<br/>例: RF12345 故障"]
    Split -->|数字/日期/价格| BM25_2["✅ BM25 强项<br/>字面命中<br/>例: iPhone 16 Pro Max 1TB"]
    Split -->|错别字| BM25_3["✅ BM25 强项<br/>N-gram + 模糊匹配<br/>例: 退欵申请"]
    Split -->|代码/函数名| BM25_4["✅ BM25 强项<br/>定位字面<br/>例: asyncio.gather"]

    Dense --> Hybrid["🔥 Hybrid Search<br/>asyncio.gather 并行"]
    BM25_1 --> Hybrid
    BM25_2 --> Hybrid
    BM25_3 --> Hybrid
    BM25_4 --> Hybrid

    Hybrid --> RRF["RRF Fusion<br/>score = Σ 1/(k + rank)<br/>k=60"]
    RRF --> Top["top-K 互补召回<br/>+15-30% NDCG"]

    style Q fill:#3B82F6,color:#fff
    style Dense fill:#10B981,color:#fff
    style BM25_1 fill:#F59E0B,color:#fff
    style BM25_2 fill:#F59E0B,color:#fff
    style BM25_3 fill:#F59E0B,color:#fff
    style BM25_4 fill:#F59E0B,color:#fff
    style Hybrid fill:#A855F7,color:#fff
    style Top fill:#84CC16,color:#fff"""
    ),

    "真实数值例子": (
        "🧮 BM25 公式实战: 同一个 'query=退款', DocA 50 字短文出现 3 次 vs DocB 800 字长文出现 8 次. "
        "TF-IDF 把 DocB 排第一 (TF 大), BM25 把 DocA 排第一 (短而集中). "
        "这就是公式里 |d|/avgdl 项的作用 — 防长文档 bias.",
        """graph LR
    Q["query: '退款'<br/>IDF=4.61<br/>(N=10000, df=100)"]

    subgraph DocA ["📄 DocA: 50 字短文"]
        A1["TF=3<br/>|d|=50<br/>|d|/avgdl=0.25"]
        A2["分母 = 3 + 1.2×0.4375 = 3.525<br/>分子 = 3×2.2 = 6.6<br/>TF_norm ≈ 1.872"]
        A3["BM25 score<br/>≈ 4.61 × 1.872<br/>≈ 8.63 ✅"]
        A1 --> A2 --> A3
    end

    subgraph DocB ["📄 DocB: 800 字长文"]
        B1["TF=8<br/>|d|=800<br/>|d|/avgdl=4.0"]
        B2["分母 = 8 + 1.2×3.25 = 11.9<br/>分子 = 8×2.2 = 17.6<br/>TF_norm ≈ 1.479"]
        B3["BM25 score<br/>≈ 4.61 × 1.479<br/>≈ 6.82"]
        B1 --> B2 --> B3
    end

    Q --> A1
    Q --> B1
    A3 --> Result["🏆 BM25 排序<br/>DocA (8.63) > DocB (6.82)<br/>短而集中胜出"]
    B3 --> Result

    Compare["⚠️ 对比 TF-IDF<br/>DocA = 4.61 × 3 = 13.83<br/>DocB = 4.61 × 8 = 36.88<br/>DocB 反向胜出 (错!)"]
    Result -.-> Compare

    style Q fill:#3B82F6,color:#fff
    style A3 fill:#10B981,color:#fff
    style B3 fill:#F59E0B,color:#fff
    style Result fill:#84CC16,color:#fff
    style Compare fill:#EF4444,color:#fff"""
    ),

    "BGE-Reranker-v2-M3": (
        "🎯 Cross-Encoder 重排: 把 query 和 doc 拼一起送 BERT, 输出 0-1 相关分. "
        "联合编码 → 精度比 Bi-Encoder 高 +4 NDCG, 但 N 次推理 → 慢 (50 候选 ~150ms). "
        "用法: Bi-Encoder 召回 top-50 → Cross-Encoder 重排 top-5/10.",
        """graph LR
    Q["query"] --> Pair["拼对 [CLS] q [SEP] doc [SEP]"]
    Doc1["doc 1"] --> Pair
    Doc2["doc 2"] --> Pair
    DocN["doc 50"] --> Pair
    Pair --> BERT["BERT 推理<br/>(N 次, 每对一次)"]
    BERT --> Score["0-1 相关分"]
    Score --> Sort["按分数重排"]
    Sort --> Top["top-K (e.g. K=5)"]

    style Q fill:#3B82F6,color:#fff
    style Top fill:#10B981,color:#fff"""
    ),

    "Reranker Cascade (多级级联, 极致精度)": (
        "🪜 Reranker Cascade 5 级: 越后面越贵越准, 候选越少. "
        "总成本 ~$0.13/query (顶级精度). Glean 推断架构: 召回 1000 → BM25 200 → "
        "BGE 50 → ColBERT 10 → LLM 综合 → 答案.",
        """graph LR
    L0["L0 召回 1000"] --> L1["L1 BM25 粗排<br/>1000 → 200<br/>$0.0001"]
    L1 --> L2["L2 Cross-Encoder<br/>200 → 50<br/>$0.05"]
    L2 --> L3["L3 ColBERT<br/>50 → 10<br/>$0.05"]
    L3 --> L4["L4 LLM Verifier<br/>10 → 3<br/>$0.03"]
    L4 --> Out["top-3"]

    style L0 fill:#94A3B8,color:#fff
    style Out fill:#10B981,color:#fff"""
    ),

    "HyDE (假设性文档嵌入) 读流程": (
        "💡 HyDE: Gao et al. 2022. 解决短 query vs 长 doc 向量空间 gap. "
        "LLM 不需要答对 (hypothesis 可幻觉), 只需语义相关. "
        "成本: 多 1 次 LLM 调用 (Haiku $0.0001) + 500ms-2s. 召回 +10%. 性价比之王, 默认开.",
        """graph LR
    Q["短 query"] --> LLM["LLM 生成 hypothesis<br/>(Haiku $0.0001)"]
    LLM --> Hyp["假设答案文档"]
    Hyp --> Emb["embed hypothesis<br/>(而非原 query)"]
    Emb --> Search["向量检索"]
    Search --> Top["top-K real chunks"]

    Q -.->|skip if 长 query| Search

    style Q fill:#3B82F6,color:#fff
    style Top fill:#10B981,color:#fff"""
    ),

    "Lost in the Middle 现象": (
        "🌀 Lost in the Middle (Liu et al. 2023): LLM 对 prompt 中间内容关注度低, U 型曲线. "
        "GPT-3.5/Claude-1 受影响大, GPT-4 受影响小. "
        "解法 LongContextReorder: top-1 → 头, top-2 → 尾, 交替放置. "
        "配 Cross-Encoder 准确率 +15-25%.",
        """graph TD
    Original["原排序: c1, c2, c3, c4, c5"] --> Detect["LLM 中间忽略 (50% 准确率)<br/>头尾 75%"]
    Detect --> Reorder["LongContextReorder (长文重排)"]
    Reorder --> New["新排序: c1, c3, c5, c4, c2<br/>top-1 → 头, top-2 → 尾"]
    New --> LLM["LLM 关注头尾 (准确率 +15-25%)"]

    style Original fill:#EF4444,color:#fff
    style LLM fill:#10B981,color:#fff"""
    ),

    "MMR (Maximum Marginal Relevance)": (
        "🎲 MMR: 相关性 + 多样性平衡. λ=0.7 工业甜点 (偏向相关). "
        "适合比较/综述/推荐场景 (避免 top-K 全是同一篇). "
        "不适合精确事实查询. 真实案例: 新闻 RAG λ=0.6 后 CTR +18%.",
        """graph LR
    R["候选 top-50"] --> Init["初始 S = 空"]
    Init --> Pick["选 d_1 = argmax Sim(q, d)"]
    Pick --> S["加入 S"]
    S --> Loop["第 k 轮:<br/>选 d_k = argmax MMR(d)"]
    Loop --> MMR["MMR = λ×Sim(q,d) - (1-λ)×max Sim(d, d_j∈S)"]
    MMR --> Until{"|S| = K?"}
    Until -->|否| Loop
    Until -->|是| Out["返回 K 个多样化结果"]

    style R fill:#94A3B8,color:#fff
    style Out fill:#10B981,color:#fff"""
    ),

    "CRAG (Corrective-RAG) 完整流程": (
        "🔧 CRAG: Jiang et al. 2024. 检索后评估器三档 + 行动. "
        "Correct → 知识精炼 (拆 strips 过滤无关). Incorrect → Web 搜索补救. "
        "Ambiguous → 两路同时. 比 Self-RAG 易落地 (不需 fine-tune LLM, 用 prompt 评估).",
        """graph TD
    Q["query"] --> Retrieve["1. Retrieve 标准 RAG"]
    Retrieve --> Assess["2. Assess (LLM 评估器)"]
    Assess -->|Correct| Refine["3a. Knowledge Refinement<br/>拆 strips → 过滤 → 重组"]
    Assess -->|Incorrect| Rewrite["3b. Query Rewrite + Web Search"]
    Assess -->|Ambiguous| Both["3c. Both 两路同时"]
    Refine --> Gen["4. Generate"]
    Rewrite --> Gen
    Both --> Gen
    Gen --> A["Answer + 强制引用"]

    style Q fill:#3B82F6,color:#fff
    style A fill:#10B981,color:#fff
    style Assess fill:#F59E0B,color:#fff"""
    ),

    # ========= §七 L4 Router =========
    "Modular RAG 7 模块完整接口": (
        "🧩 Modular RAG 7 模块: 学界共识 (Yunfan Gao 2024 综述). "
        "微服务化思想, 像 Java 微服务治理. 召回差只调 Retriever, 幻觉高加 Validator, "
        "成本高换小模型 Generator. 不重写系统, 单点优化.",
        """graph LR
    Q["Query"] --> M1["1. Query Understanding<br/>查询理解 + 改写"]
    M1 --> M2["2. Router<br/>按问题类型分流"]
    M2 --> M3["3. Retriever<br/>多通道检索"]
    M3 --> M4["4. Reranker<br/>重排"]
    M4 --> M5["5. Context Builder<br/>上下文组装"]
    M5 --> M6["6. Generator<br/>LLM 生成"]
    M6 --> M7["7. Validator<br/>引用 + 事实校验"]
    M7 --> A["Answer"]

    style Q fill:#3B82F6,color:#fff
    style A fill:#10B981,color:#fff"""
    ),

    "Router 路由决策流程 (3 层混合)": (
        "🚦 Router 三层混合: 规则 → 语义 → LLM 兜底. "
        "60-70% 走规则 (0ms 0 cost), 20-30% 走语义 (10ms), 10-20% 走 LLM (500ms $0.0001). "
        "平均延迟 ~52ms, 平均 cost $0.00001/query (几乎 0).",
        """graph TD
    Q["用户 query"] --> R1{"Layer 1: 规则路由<br/>正则 + 关键词"}
    R1 -->|匹配 60-70%, 0ms 0 cost| Route1["走对应路径"]
    R1 -->|未匹配| R2{"Layer 2: 语义路由<br/>cosine 找最近路由"}
    R2 -->|cos > 0.7, 20-30% 10ms| Route2["走对应路径"]
    R2 -->|未匹配| R3{"Layer 3: LLM 兜底<br/>Haiku 分类"}
    R3 -->|10-20% 500ms $0.0001| Route3["走对应路径"]

    style Q fill:#3B82F6,color:#fff
    style Route1 fill:#10B981,color:#fff
    style Route2 fill:#22C55E,color:#fff
    style Route3 fill:#84CC16,color:#fff"""
    ),

    "5 类 Query 完整路由流程": (
        "📋 5 类 Query 完整分流: 80% FAQ → RAG, 5% 编号 → API, 10% 数据分析 → Text2SQL, "
        "5% 跨系统 → Agent. 平均成本砍一半, 简单问题响应快, 复杂能力强.",
        """graph LR
    Q["用户提问"] --> Router{Router<br/>路由决策}
    Router -->|80% FAQ| A["普通 RAG<br/>Hybrid + Rerank<br/>$0.001 / 1-2s"]
    Router -->|5% 编号| B["BM25 + 业务 API<br/>$0.0001 / <1s"]
    Router -->|10% 数据分析| C["Text2SQL → DB<br/>$0.005 / 2-3s"]
    Router -->|5% 跨系统| D["Agent + Tool Calling<br/>$0.05-0.5 / 5-30s"]

    style Q fill:#3B82F6,color:#fff
    style A fill:#10B981,color:#fff
    style B fill:#22C55E,color:#fff
    style C fill:#84CC16,color:#fff
    style D fill:#EC4899,color:#fff"""
    ),

    "Text2SQL 完整流程": (
        "🗄️ Text2SQL RAGFlow 三模块架构: Knowledge Base + SQL Generator + Executor. "
        "三类知识用 type 字段区分 (DDL + Q-SQL + Description). "
        "实战: 月 1 准确率 60% → 月 6 加错误反思后 85%.",
        """graph TB
    Q["自然语言 query"] --> KB["Knowledge Base 检索<br/>(单 Milvus collection)"]
    KB --> DDL["type=ddl<br/>表结构"]
    KB --> QSQL["type=qsql<br/>(问题, SQL) few-shot"]
    KB --> Desc["type=description<br/>业务术语"]
    DDL --> Gen["SQL Generator<br/>Sonnet temp=0"]
    QSQL --> Gen
    Desc --> Gen
    Gen --> SQL["生成 SQL"]
    SQL --> Safe["安全检查<br/>+LIMIT, 禁 DELETE"]
    Safe --> Exec["执行 (只读账号)"]
    Exec -->|成功| Result["格式化结果"]
    Exec -->|失败| Fix["Fixer Reflection<br/>(max 3 次重试)"]
    Fix --> Gen

    style Q fill:#3B82F6,color:#fff
    style Result fill:#10B981,color:#fff"""
    ),

    # ========= §八 L5 Agent =========
    "Tool Calling 6 步完整流程": (
        "🛠️ Tool Calling 6 步标准协议 (OpenAI / Anthropic / Gemini 三家 API 略不同但流程一致). "
        "关键: LLM 不持权限, 只能申请. Java/Python 后端鉴权决定给不给. "
        "防 prompt injection 拐骗 ('我是管理员').",
        """sequenceDiagram
    autonumber
    participant U as 用户
    participant App as 应用代码
    participant L as LLM
    participant T as Tool API

    Note over App: 1. 定义 Tool (JSON Schema)
    U->>App: 2. 用户提问
    App->>L: + tools 列表
    L-->>App: 3. 模型决策 (返 tool_calls)
    App->>T: 4. 代码执行 (调真实 API)
    T-->>App: 结果
    App->>L: 5. 结果反馈 (role: tool)
    L-->>App: 6. 最终生成自然语言答案
    App->>U: 答案"""
    ),

    "Memory 三层架构": (
        "🧠 Agent Memory 三层: Session (短期 Redis 6h) + User Preference (长期 PG) + "
        "Business Memory (业务上下文 VectorDB). "
        "Token 预算分配 (16K context): system 1K + preference 0.5K + business 2K + session 2K + RAG 8K + query 1K + 输出 1.5K.",
        """graph TD
    Agent["🤖 Agent"] --> M1["L1 Session Memory<br/>Redis 短期 6h<br/>本次会话"]
    Agent --> M2["L2 User Preference<br/>PG 长期<br/>用户偏好/角色"]
    Agent --> M3["L3 Business Memory<br/>VectorDB<br/>业务上下文 (语义检索)"]
    M1 --> P["拼 Prompt (Token 预算分配)"]
    M2 --> P
    M3 --> P
    P --> LLM["LLM 推理"]

    style Agent fill:#EC4899,color:#fff
    style LLM fill:#10B981,color:#fff"""
    ),

    "7 种高级 RAG-Agent 模式": (
        "🚀 7 种高级 RAG 模式: 各有适用场景. Self-RAG 重 (需 fine-tune), CRAG 易落地, "
        "GraphRAG 强但贵, LightRAG 平衡, FRAG 自适应, GraphIRAG 多轮, Adaptive 按复杂度选.",
        """graph TD
    Base["基础 RAG"] --> Self["Self-RAG<br/>(Asai 2023)<br/>训练 reflection token"]
    Base --> CRAG["CRAG (Jiang 2024)<br/>检索后三档评估<br/>不需 fine-tune ✓"]
    Base --> Graph["GraphRAG (Microsoft 2024)<br/>三元组+图+Leiden<br/>跨文档关系"]
    Base --> Light["LightRAG (HKUDS 2024)<br/>GraphRAG 轻量版"]
    Base --> FRAG["FRAG (2025)<br/>自适应分流"]
    Base --> Iter["GraphIRAG (2025)<br/>多轮检索"]
    Base --> Adapt["Adaptive RAG<br/>按复杂度选策略"]

    style Base fill:#3B82F6,color:#fff
    style CRAG fill:#10B981,color:#fff
    style Graph fill:#A855F7,color:#fff"""
    ),

    # ========= §九 Generation =========
    "完整 Generation 读流程总结": (
        "📝 Generation 完整流程: Context Building → LLM Inference → Streaming → Validator. "
        "TTFT 1-3s, 总响应 5-10s, 单次成本 $0.001-0.05. "
        "Validator 4 道防线: citation 校验 / Faithfulness / PII 过滤 / Guardrail.",
        """graph LR
    In["query + top-K chunks"] --> CB["Context Building<br/>(prompt 拼接)"]
    CB --> LCR["LongContextReorder (长文重排)"]
    LCR --> LLM["LLM Inference<br/>(vLLM / API)"]
    LLM --> Stream["Streaming SSE 边输出"]
    Stream --> V["Validator 校验<br/>citation + faithfulness + PII + Guardrail"]
    V -->|pass| Out["✅ 答案 + citations"]
    V -->|fail| Reject["拒答 / fallback"]

    style In fill:#84CC16,color:#fff
    style Out fill:#10B981,color:#fff
    style Reject fill:#EF4444,color:#fff"""
    ),

    "LLM Inference (推理) 完整流程": (
        "⚙️ LLM Inference 两阶段: Prefill (一次性处理 prompt 计算 KV cache) + "
        "Decode (逐 token 生成, 用 KV cache 加速). "
        "vLLM PagedAttention 把 KV cache 像 OS 内存分页, 吞吐 24× HF Transformers.",
        """graph LR
    Prompt["输入 prompt"] --> Tok["Tokenize<br/>(BPE)"]
    Tok --> Prefill["Prefill 阶段<br/>(一次性并行处理)"]
    Prefill --> KV["KV Cache (PagedAttention)"]
    KV --> Decode["Decode 阶段<br/>(逐 token autoregressive)"]
    Decode --> Sample["Sampling<br/>(Greedy / Top-K / Top-P)"]
    Sample --> Token["输出 token"]
    Token --> Decode
    Token --> Stream["SSE 流式返回"]

    style Prompt fill:#3B82F6,color:#fff
    style Stream fill:#10B981,color:#fff"""
    ),

    # ========= §十 横切 =========
    "Cache 5 层完整读写流程": (
        "💾 5 层缓存设计: L1 Embedding → L2 检索 → L3 Rerank → L4 答案精确 → L5 答案语义 (近邻). "
        "综合命中率 60-80%, 月成本可省 60%+. "
        "真实案例: LegalTech $80K → $25K 省 68%.",
        """graph TD
    Q["👤 用户 query"] --> L1{L1: Embedding<br/>Cache?}
    L1 -->|Hit 30-60%| Use1["复用向量"]
    L1 -->|Miss| EM["调 Embedder"]
    EM --> Use1
    Use1 --> L2{L2: 检索结果<br/>Cache?}
    L2 -->|Hit 20-40%| Use2["复用 chunk_ids"]
    L2 -->|Miss| Search["走 Hybrid Search"]
    Search --> Use2
    Use2 --> L3{L3: Rerank<br/>Cache?}
    L3 -->|Hit 10-20%| Use3["复用排序"]
    L3 -->|Miss| RR["调 Reranker"]
    RR --> Use3
    Use3 --> L4{L4: 答案精确<br/>Cache?}
    L4 -->|Hit 10-30%| Final["返回缓存答案"]
    L4 -->|Miss| L5{L5: 答案语义<br/>Cache?}
    L5 -->|Hit 15-35% cosine 0.93+| Final
    L5 -->|Miss| LLM["调 LLM 生成"]
    LLM --> Final

    style Q fill:#3B82F6,color:#fff
    style Final fill:#10B981,color:#fff"""
    ),

    "ACL (Access Control List 访问控制) 读写流程": (
        "🔒 ACL 三层防御: Schema Strip + JWT 短令牌 + MCP/Tool gating. "
        "关键原则: LLM 不持权限, 只能申请, 后端决定. "
        "即使 prompt 注入'我是管理员', 后端仍按 JWT role 决定. "
        "Notion 早期 ACL 越权事件后业界共识.",
        """graph TD
    U["👤 用户请求"] --> JWT["🔑 Layer 1: JWT 验签<br/>(60s 短令牌)"]
    JWT --> SS["🔍 Layer 2: SQL 行级过滤<br/>WHERE tenant_id + readers"]
    SS --> Ret["返回 chunks"]
    Ret --> Strip["📋 Schema Strip<br/>按 role 选字段"]
    Strip --> MCP["🛡️ Layer 3: MCP/Tool gating<br/>tool 调用再 verify"]
    MCP --> Final["✅ 输出"]

    style U fill:#3B82F6,color:#fff
    style JWT fill:#F59E0B,color:#fff
    style SS fill:#10B981,color:#fff
    style MCP fill:#EF4444,color:#fff
    style Final fill:#84CC16,color:#fff"""
    ),

    "拒答完整流程": (
        "🚫 Refusal 6 道防线: 候选不足 / score 低 / Guardrail / Faithfulness / PII / 输出 Guardrail. "
        "Air Canada 2024 法庭判赔后行业共识: 涉钱/法律/医疗强制转人工. "
        "DPD 2024 chatbot 骂用户事件后必备 Llama Guard.",
        """graph TD
    Q["query"] --> R1{候选数 < 3?}
    R1 -->|是| Reject1["拒答: 没找到相关文档"]
    R1 -->|否| R2{最高 score < 0.5?}
    R2 -->|是| Reject2["拒答: 信心不足"]
    R2 -->|否| Guard1["生成前 Guardrail<br/>(Llama Guard 输入)"]
    Guard1 -->|不安全| Reject3["拒答: 内容违规"]
    Guard1 -->|安全| LLM["LLM 生成"]
    LLM --> Faith{Faithfulness < 0.85?}
    Faith -->|是| Reject4["拒答: 答案不可靠"]
    Faith -->|否| PII{含 PII?}
    PII -->|是| Mask["脱敏 / 拒答"]
    PII -->|否| Guard2["输出 Guardrail<br/>(Llama Guard 输出)"]
    Guard2 -->|不安全| Reject5["拒答"]
    Guard2 -->|安全| Final["✅ 返回"]

    style Q fill:#3B82F6,color:#fff
    style Final fill:#10B981,color:#fff
    style Reject1 fill:#EF4444,color:#fff
    style Reject2 fill:#EF4444,color:#fff
    style Reject3 fill:#EF4444,color:#fff
    style Reject4 fill:#EF4444,color:#fff
    style Reject5 fill:#EF4444,color:#fff
    style Mask fill:#F59E0B,color:#fff"""
    ),

    # ========= §十一 周边技术栈 =========
    "完整技术栈全景 (5 大类)": (
        "🏛️ RAG 完整技术栈拓扑: 5 大类组件协同. 数据存储 (向量+全文+关系+对象+缓存+图), "
        "计算引擎 (LLM+Embedder 推理), 流程编排 (队列+调度+ETL), "
        "可观测 (监控+追踪+错误+日志), 部署 (容器+网关+安全).",
        """graph TB
    subgraph DataLayer [数据存储层]
        VDB[向量库<br/>Pinecone/Milvus/pgvector]
        FT[全文搜索<br/>Elasticsearch/OpenSearch]
        RDB[关系库<br/>PostgreSQL/MySQL]
        OS[文档存储<br/>S3/MinIO]
        Cache[缓存<br/>Redis/Tair]
        KG[知识图谱<br/>Neo4j/NebulaGraph]
    end
    subgraph Compute [计算引擎层]
        LLM[LLM 推理<br/>vLLM/SGLang/TensorRT]
        Emb[Embedder 推理<br/>TEI/Infinity]
    end
    subgraph Orch [流程编排层]
        MQ[消息队列<br/>Kafka/RocketMQ]
        Sched[任务调度<br/>Celery/Temporal]
        ETL[ETL<br/>Airbyte/DataX]
    end
    subgraph Obs [可观测层]
        Met[Prometheus + Grafana]
        Trace[OpenTelemetry + Phoenix/Langfuse]
        Err[Sentry / Datadog]
    end
    subgraph Deploy [部署运行层]
        K8s[Docker / Kubernetes]
        GW[网关 Apisix/Higress]
        Sec[安全 Vault/OAuth]
    end"""
    ),

    "Pinecone": (
        "☁️ Pinecone SaaS 向量库: 0 运维 / multi-tenant 原生 / serverless 真按需. "
        "贵 (10× 自托管) 但省心. Notion / Salesforce / Gong 都用. "
        "1000 万向量 multi-region P95 < 100ms, $70/月起.",
        """graph LR
    App["应用代码"] -->|client.upsert| Pine["Pinecone Cloud"]
    Pine --> Shard["分片路由<br/>(by namespace)"]
    Shard --> HNSW["HNSW 索引"]
    Shard --> Replica["multi-region replica"]
    App -->|client.query| Pine
    Pine -->|fan-out| Shard
    HNSW --> Top["top-K + filter"]
    Top --> App

    style App fill:#3B82F6,color:#fff
    style Top fill:#10B981,color:#fff"""
    ),

    "vLLM": (
        "⚡ vLLM 高吞吐 LLM 推理: PagedAttention (类 OS 内存分页) + Continuous Batching. "
        "vs HF Transformers 吞吐 24×. 单 A100 70B Q4: 50-100 token/s. "
        "OpenAI 兼容 API. 业界自托管首选.",
        """graph TD
    Start["vllm serve <model>"] --> Load["加载模型权重<br/>(~30s for 70B)"]
    Load --> KV["初始化 PagedAttention<br/>KV cache pool"]
    KV --> HTTP["启动 OpenAI 兼容 HTTP server"]
    Client["client POST /v1/chat/completions"] --> HTTP
    HTTP --> Sched["vLLM Scheduler"]
    Sched --> Prefill["Prefill (并行处理 prompt)"]
    Prefill --> Decode["Decode (逐 token)"]
    Decode --> Batch["Continuous Batching<br/>多 request 共享 GPU"]
    Batch --> Stream["Streaming SSE"]
    Stream --> Client

    style Start fill:#94A3B8,color:#fff
    style Stream fill:#10B981,color:#fff"""
    ),

    # ========= §十六 Failure Mode =========
    "诊断决策树": (
        "🔍 RAG 答案错诊断决策树: 6 大失败模式分类. "
        "Type A 没召回 / B 召回错版本 / C 信息不全 / D LLM 编了 chunk 没说 / E 引用错 / F 拒答错. "
        "面试时按这棵树走能覆盖 95% 排查场景.",
        """graph TD
    A["🔍 用户报答案错"] --> B["1. 复现 5min"]
    B --> C{"2. 看检索 chunk"}
    C --> D{"3. KB 中真有答案?"}
    D -->|没有| Cov["Coverage Gap<br/>补 KB"]
    D -->|有| E{"4. chunk 对吗?"}
    E -->|没召到| TypeA["Type A: Retrieval Failure<br/>修: Hybrid + HyDE + 父子"]
    E -->|版本错| TypeB["Type B: Wrong Retrieval<br/>修: 版本管理 + 时效"]
    E -->|不全| TypeC["Type C: Context Insufficient<br/>修: 增 K + 多跳"]
    E -->|对的但答错| F{"5. LLM 出错类型?"}
    F -->|编了 chunk 没说| TypeD["Type D: Hallucination<br/>修: 强 prompt + Validator"]
    F -->|引用错| TypeE["Type E: Citation Error<br/>修: post-hoc 校验"]
    F -->|拒答错| TypeF["Type F: Refusal Wrong<br/>修: 动态阈值"]

    style A fill:#3B82F6,color:#fff
    style TypeA fill:#EF4444,color:#fff
    style TypeB fill:#F59E0B,color:#fff
    style TypeC fill:#F59E0B,color:#fff
    style TypeD fill:#EF4444,color:#fff
    style TypeE fill:#F59E0B,color:#fff
    style TypeF fill:#A855F7,color:#fff"""
    ),

    # ========= §十三 案例统计 =========
    "按主 Layer 分布 (主标签去重计 22)": (
        "📊 22 案例按主 Layer 分布 (主标签去重). "
        "L1 数据治理 36% 印证'70% 项目栽数据治理'核心论断. "
        "横切 32% 是法律/品牌灾难高发区 (Air Canada / DPD / NYC). "
        "L3+L7 验证类合计 18% (Lost in the Middle / Citation 校验).",
        """pie showData
    title 22 真实案例按主 Layer 分布 (去重)
    "L1 数据治理 (8)" : 8
    "横切 Security/ACL/产品 (7)" : 7
    "L2 索引 (2)" : 2
    "L3 检索 (2)" : 2
    "L7 Validator (2)" : 2
    "L5 Agent 成功 (1)" : 1"""
    ),

    "按严重程度": (
        "⚠️ 22 案例按严重程度: 致命 3 个 (Air Canada 法律责任 / DPD 品牌灾难 / NYC 政府违法). "
        "高 4 个 (Samsung 数据泄露 / Notion ACL / Bing PII / Bloomberg). 中 8 个. 低 7 个. "
        "致命级都是横切关注点失败 (Refusal/Guardrail/ACL).",
        """pie showData
    title 22 案例按严重程度
    "致命 (法律/品牌)" : 3
    "高 (合规/隐私)" : 4
    "中 (质量退化)" : 8
    "低 (优化)" : 7"""
    ),

    # ========= §十四 评估 =========
    # ========= 业务必备 5 大 KPI =========
    "业务必备 5 大 KPI": (
        "📈 5 大 KPI 健康范围: 监控 dashboard 必备. "
        "拒答率突涨 → 检索退化告警. cost 突增 → 死循环 / 缓存失效. NPS 跌破 50 → 紧急 review.",
        """graph TB
    subgraph KPI [5 大 KPI 健康范围]
        K1["🎯 召回率 Recall<br/>> 80% (Golden Set 月测)"]
        K2["🚫 拒答率 Refusal Rate<br/>10-30% (太低幻觉, 太高用户骂)"]
        K3["💰 单次成本 Cost/Query<br/>$0.001-0.05"]
        K4["⚡ 响应延迟 Latency<br/>首字 < 3s, 总 < 10s"]
        K5["⭐ 用户满意度 NPS<br/>> 60 (终极指标)"]
    end

    style K1 fill:#10B981,color:#fff
    style K2 fill:#F59E0B,color:#fff
    style K3 fill:#3B82F6,color:#fff
    style K4 fill:#A855F7,color:#fff
    style K5 fill:#EC4899,color:#fff"""
    ),

    "5 KPI 因果": (
        "🔗 5 KPI 因果关系: 调一个会影响其他. 没有银弹, 平衡是艺术. "
        "重排提召回但加延迟成本; 缓存省钱省延迟但要防数据不新; 模型升级提 NPS 但贵.",
        """graph LR
    Recall["召回率 ↑"] --> Refusal["拒答率 ↓"]
    Refusal --> NPS["NPS ↑"]

    Rerank["Reranker ↑"] --> Recall
    Rerank --> Latency["延迟 ↑"]
    Rerank --> Cost1["成本 ↑"]

    Cache["缓存 ↑"] --> Cost2["成本 ↓"]
    Cache --> Latency2["延迟 ↓"]
    Cache -.防失效.-> Stale["数据不新风险"]

    Model["LLM 升级"] --> NPS
    Model --> Cost3["成本 ↑"]

    style Recall fill:#10B981,color:#fff
    style NPS fill:#EC4899,color:#fff"""
    ),

    # ========= 业务视角选型决策 =========
    "业务视角选型决策": (
        "🎯 5 关键决策: 我需要 RAG 吗 → 自建 vs 买 → 私有化 vs 云 → 中国 vs 海外 → 投入多少. "
        "POC: $50K / 2 月. MVP: $300K / 6 月. 生产化: $1M / 12 月.",
        """graph TD
    Q1{我需要 RAG 吗?} --> A1[大量私有文档?]
    A1 --> Q2{自建 vs 买?}
    Q2 -->|< 5 人 / 通用| Buy[Buy: Glean / Assistants]
    Q2 -->|> 20 人 / 定制| Build[Build]
    Build --> Q3{私有化 vs 云?}
    Q3 -->|金融/医疗/政府| Priv[私有化部署]
    Q3 -->|SaaS B2B| Cloud[云]
    Q3 -->|跨国大企业| Hybrid[混合云]
    Priv --> Q4{中国 vs 海外?}
    Cloud --> Q4
    Q4 -->|国内/备案| CN[Qwen3/DeepSeek/GLM]
    Q4 -->|国际| Intl[Claude/GPT/Gemini]
    Q4 -->|性价比| Cheap[DeepSeek-V3]
    CN --> Q5{投入多少?}
    Intl --> Q5
    Q5 --> POC["POC: 5 人 x 2 月 ~$50K"]
    Q5 --> MVP["MVP: 10 人 x 6 月 ~$300K"]
    Q5 --> Prod["生产化: 15 人 x 12 月 ~$1M"]"""
    ),

    # ========= 部署模式 =========
    "部署模式 5 种": (
        "🏗️ 部署模式 5 种, 对应不同客户群. SaaS 多租户成本最低 ($50-500/月) 但合规弱; "
        "完全本地化最贵 ($100K+ 部署 + $50K+/月) 但合规强. 混合云适合跨国.",
        """graph TD
    Customer{客户类型} --> SMB["SMB 中小企业"]
    Customer --> MidLg["中大企业"]
    Customer --> Fin["金融 / 医疗 / 高合规"]
    Customer --> Gov["政府 / 军工 / 国企"]
    Customer --> MNC["跨国大企业"]

    SMB --> M1["SaaS 多租户<br/>$50-500/月<br/>共享集群 + 行级 ACL"]
    MidLg --> M2["Single-tenant SaaS<br/>$1K-10K/月<br/>独立 DB"]
    Fin --> M3["VPC 部署<br/>$5K-30K/月<br/>客户 VPC 内"]
    Gov --> M4["完全本地化<br/>$50K-500K/年<br/>+部署 $100K-1M"]
    MNC --> M5["混合云<br/>数据本地+模型境外<br/>$200K-1M/年"]

    style M1 fill:#10B981,color:#fff
    style M2 fill:#22C55E,color:#fff
    style M3 fill:#A855F7,color:#fff
    style M4 fill:#EF4444,color:#fff
    style M5 fill:#3B82F6,color:#fff"""
    ),

    # ========= 评估工具 =========
    "评估工具对比": (
        "🛠️ 5 评估工具: RAGAS 离线评估首选 (无参考). LlamaIndex Eval 嵌入式. "
        "Phoenix / Langfuse 生产监控 (开源). LangSmith LangChain 商业. "
        "实践: 三者非互斥, 组合用.",
        """graph LR
    Stage{评估阶段?} --> Dev["开发期"]
    Stage --> Prod["生产期"]
    Stage --> Both["持续"]

    Dev --> RAGAS["RAGAS<br/>离线 4 大指标<br/>无参考 ✓"]
    Dev --> LIEval["LlamaIndex Eval<br/>BatchEvalRunner"]

    Prod --> Phoenix["Phoenix<br/>OpenTelemetry"]
    Prod --> Lang["Langfuse<br/>开源"]
    Prod --> LS["LangSmith<br/>LangChain 商业"]

    Both --> Combo["组合: RAGAS + Phoenix"]

    style RAGAS fill:#10B981,color:#fff
    style Phoenix fill:#A855F7,color:#fff"""
    ),

    "Golden Set 制作": (
        "🎯 Golden Set 4 类样本配比: 高频 50% (覆盖 80% 流量) + 长尾 20% (边缘但重要) + "
        "边界 case 15% (拒答 / 越权) + 已知 Bad case 15% (回归保护). 季度更新.",
        """pie showData
    title Golden Set 4 类样本配比
    "高频 query (50%)" : 50
    "长尾 query (20%)" : 20
    "边界 case (15%)" : 15
    "已知 Bad case (15%)" : 15"""
    ),

    # ========= 学习路径 =========
    "0 → 入门 (1 周)": (
        "📚 学习路径 4 阶段 + 3 转型路线. 入门 1 周, 中级 1 月, 高级 3 月, 专家 6 月+. "
        "推荐顺序: 业务理解 → 5 层架构 → 一个组件深入. 不要一上来就读所有技术细节.",
        """gantt
    title RAG 学习路径 (按阶段)
    dateFormat YYYY-MM-DD
    axisFormat %m/%d

    section 入门 1 周
    概念 + Demo (Day 1-2)         :a1, 2026-04-25, 2d
    核心组件 (Day 3-4)            :a2, after a1, 2d
    评估 (Day 5)                  :a3, after a2, 1d
    案例 (Day 6-7)                :a4, after a3, 2d

    section 中级 1 月
    深化基础 (W1)                 :b1, after a4, 7d
    检索优化 (W2)                 :b2, after b1, 7d
    Agent (W3)                    :b3, after b2, 7d
    上线 (W4)                     :b4, after b3, 7d

    section 高级 3 月
    工程化 (M1)                   :c1, after b4, 30d
    优化 (M2)                     :c2, after c1, 30d
    评估闭环 (M3)                 :c3, after c2, 30d

    section 专家 6 月+
    规模化 (M1-2)                 :d1, after c3, 60d
    高级 Agent (M3-4)             :d2, after d1, 60d
    影响力 (M5-6)                 :d3, after d2, 60d"""
    ),

    # ========= 评估 =========
    "评估三大维度": (
        "📊 RAG 评估三大维度: 检索质量 (Precision/Recall/MRR/NDCG) + 生成质量 (Faithfulness/Relevancy/Citation) + 系统性能 (Latency/QPS/Cost). "
        "三维不可偏废. 召回再准答案不忠实也白搭, 答案再好慢到无法用也没意义.",
        """graph TD
    Eval["RAG 评估"] --> R["检索质量"]
    Eval --> G["生成质量"]
    Eval --> S["系统性能"]

    R --> R1[Precision 查准率]
    R --> R2[Recall 查全率]
    R --> R3[MRR / NDCG@K]
    R --> R4[Context Precision/Recall]

    G --> G1[Faithfulness 忠实度]
    G --> G2[Answer Relevancy]
    G --> G3[Citation Accuracy]
    G --> G4[ROUGE / BLEU]

    S --> S1[Latency P50/P95/P99]
    S --> S2[QPS]
    S --> S3[Cost per query]
    S --> S4[拒答率]

    style Eval fill:#6366F1,color:#fff"""
    ),
    "Agent RAG 架构体系总图": (
        "🎯 Agent RAG 7 层立体架构 + 横切 Cost Controller. 简单 query (80-95%) 走左侧 Modular RAG 单次管道; 复杂 query (5-20%) 走右侧 Agent 路径 (Planner → Tool Loop → Memory → Synthesizer). 全部经 Validator 闸门 + 全程 Cost Controller 监控.",
        """graph TB
    User["👤 用户 query"]
    QU["Layer 1 — Query Understanding<br/>意图分类 + 复杂度评估"]
    Router{"Layer 2 — Router<br/>规则 → 语义 → LLM 兜底"}

    RAG["Modular RAG<br/>单次完整管道<br/>L1+L2+L3 see §3"]

    Plan["Layer 3 — Planner<br/>Sonnet 4.5 / o3<br/>生成执行 Plan"]

    subgraph Loop["Layer 4 — Tool Execution Loop (max_steps=8)"]
      direction LR
      Decide["LLM 决定下一步"]
      Exec["Executor 调真实 API"]
      Check{"4 终止条件<br/>满足?"}
      Decide --> Exec --> Check
      Check -->|否| Decide
    end

    Tools[("Tool Registry<br/>5-12 工具池")]
    Mem[("Layer 5 — Memory<br/>L1 Session / L2 User / L3 Biz")]
    Synth["Layer 6 — Synthesizer<br/>Haiku 综合 + 引用"]
    Validator{"Layer 7 — Validator<br/>Faithfulness + Citation<br/>+ PII + Guardrail"}
    Cost(["Cost Controller<br/>cost / steps / repeat / timeout<br/>超预算硬熔断"])
    Answer["💬 答案 + 引用 + trace"]

    User --> QU --> Router
    Router -->|simple 80-95%| RAG
    Router -->|complex 5-20%| Plan
    Plan --> Loop
    Loop <--> Tools
    Loop <--> Mem
    Check -->|是| Synth
    RAG --> Validator
    Synth --> Validator
    Validator -->|通过| Answer
    Validator -.->|不通过| Plan
    Cost -.->|监控| Plan
    Cost -.->|监控| Loop
    Cost -.->|监控| Synth

    style User fill:#3B82F6,color:#fff
    style RAG fill:#10B981,color:#fff
    style Plan fill:#A855F7,color:#fff
    style Synth fill:#A855F7,color:#fff
    style Validator fill:#F59E0B,color:#fff
    style Cost fill:#EF4444,color:#fff
    style Answer fill:#10B981,color:#fff"""
    ),

    # ===== 章节开头思维导图 (flowchart LR 树状从左到右, 取代散状 mindmap) =====
    "§0 速览思维导图": (
        "🗺️ §0 速览全景: 核心概念 / 架构层级 / 演进史 / 决策原则 四大类.",
        """flowchart LR
    R(("速览"))
    R --> A["核心概念"]
    R --> B["架构层级"]
    R --> C["演进四代"]
    R --> D["决策原则"]

    A --> A1["RAG 定义 (Retrieval-Augmented Generation)"]
    A --> A2["Dense / Sparse / Hybrid 三类检索"]
    A --> A3["三阶段架构 (Index/Retrieval/Generation)"]
    A --> A4["喂 LLM 的数据真相"]
    A --> A5["完整数据流 (离线+在线)"]

    B --> B1["L1 数据治理 (Governance)"]
    B --> B2["L2 索引 (Indexing)"]
    B --> B3["L3 检索 (Retrieval)"]
    B --> B4["L4 Router 路由分流"]
    B --> B5["L5 Agent 智能体"]

    C --> C1["Naive 朴素 (Gen 1)"]
    C --> C2["Advanced 增强 (Gen 2)"]
    C --> C3["Modular 模块化 (Gen 3)"]
    C --> C4["Agent"]

    D --> D1["Anthropic 三层模型"]
    D --> D2["80/15/5 流量分流"]
    D --> D3["Hybrid 必选原则"]
    D --> D4["60+ 术语速查"]

    classDef root fill:#3B82F6,color:#fff,stroke:#1e40af,stroke-width:2px
    classDef cat fill:#A855F7,color:#fff,stroke:#6b21a8,stroke-width:1px
    classDef leaf fill:#f6f8fa,color:#1f2328,stroke:#d1d9e0
    class R root
    class A,B,C,D cat
    class A1,A2,A3,A4,A5,B1,B2,B3,B4,B5,C1,C2,C3,C4,D1,D2,D3,D4 leaf"""
    ),

    "§4 L1 数据治理思维导图": (
        "🛡️ §4 L1 数据治理全景: 七大职责 / 七类脏数据 / 工具栈 / 核心指标 / 实战 SOP.",
        """flowchart LR
    R(("数据治理"))
    R --> A["七大职责"]
    R --> B["七类脏数据"]
    R --> C["工具栈"]
    R --> D["核心指标"]
    R --> E["实战 SOP"]

    A --> A1["多源接入 (Connector + Upload)"]
    A --> A2["解析 (Parsing)"]
    A --> A3["噪声过滤 (Boilerplate)"]
    A --> A4["PII 脱敏 (隐私保护)"]
    A --> A5["去重 (Deduplication)"]
    A --> A6["质量评估 (Quality Gating)"]
    A --> A7["元数据丰富 (Metadata)"]

    B --> B1["重复 / 近似重复 (20-40%)"]
    B --> B2["过时未删 Stale (15-30%)"]
    B --> B3["格式破坏 (PDF 表格)"]
    B --> B4["噪声 (页眉/页脚/广告)"]
    B --> B5["多语言混杂 (中英混排)"]
    B --> B6["PII 敏感信息 (5-20%)"]
    B --> B7["版本爆炸 (V1/V2/Final)"]

    C --> C1["LlamaParse (复杂 PDF 解析)"]
    C --> C2["Presidio (PII 检测引擎)"]
    C --> C3["MinHash + LSH (近似去重)"]
    C --> C4["Claude Haiku (LLM 质量评分)"]
    C --> C5["Spark + Airflow (大规模 Pipeline)"]

    D --> D1["召回率 Recall@10"]
    D --> D2["忠实度 Faithfulness"]
    D --> D3["重复率 (Dedup 效果)"]
    D --> D4["PII 漏检率 (合规)"]
    D --> D5["平均质量分"]

    E --> E1["端到端实战 walkthrough"]
    E --> E2["Spark 100 万文档 Pipeline"]
    E --> E3["KB Health 7 大指标"]
    E --> E4["Bad case 5 类根因闭环"]

    classDef root fill:#3B82F6,color:#fff,stroke:#1e40af,stroke-width:2px
    classDef cat fill:#A855F7,color:#fff,stroke:#6b21a8,stroke-width:1px
    classDef leaf fill:#f6f8fa,color:#1f2328,stroke:#d1d9e0
    class R root
    class A,B,C,D,E cat
    class A1,A2,A3,A4,A5,A6,A7,B1,B2,B3,B4,B5,B6,B7,C1,C2,C3,C4,C5,D1,D2,D3,D4,D5,E1,E2,E3,E4 leaf"""
    ),

    "§5 L2 索引思维导图": (
        "📚 §5 L2 索引全景: Chunking 策略 / Embedder 选型 / ANN 索引 / 多模态 / Fine-tune.",
        """flowchart LR
    R(("索引"))
    R --> A["Chunking 策略"]
    R --> B["Embedder 选型"]
    R --> C["ANN 索引"]
    R --> D["多模态"]
    R --> E["Fine-tune"]

    A --> A1["固定窗口分块 (Fixed Window)"]
    A --> A2["递归字符分块 (Recursive Char)"]
    A --> A3["父子分块 (Parent-Child, 业界主流)"]
    A --> A4["语义分块 (Semantic Chunking)"]
    A --> A5["Late Chunking (Jina 2024)"]
    A --> A6["Contextual Retrieval (Anthropic 2024)"]
    A --> A7["AST-aware (代码专用)"]

    B --> B1["BGE-M3 (中文/混合, 1024 维)"]
    B --> B2["Voyage-3 (英文 SOTA, 1024 维)"]
    B --> B3["OpenAI text-embedding-3-large (3072 维)"]
    B --> B4["Cohere embed-v3 (多语言)"]
    B --> B5["Qwen3-Embedding (中文 SOTA)"]

    C --> C1["HNSW (多层近邻图, 主流)"]
    C --> C2["IVF (倒排索引, 大规模)"]
    C --> C3["DiskANN (磁盘存储, 极大规模)"]

    D --> D1["CLIP (OpenAI 图文对齐)"]
    D --> D2["BLIP (图像描述生成)"]
    D --> D3["ColPali (PDF 视觉 RAG)"]

    E --> E1["Triplet Loss (三元组损失)"]
    E --> E2["InfoNCE (对比学习损失)"]
    E --> E3["Hard Negatives (硬负样本挖掘)"]

    classDef root fill:#3B82F6,color:#fff,stroke:#1e40af,stroke-width:2px
    classDef cat fill:#A855F7,color:#fff,stroke:#6b21a8,stroke-width:1px
    classDef leaf fill:#f6f8fa,color:#1f2328,stroke:#d1d9e0
    class R root
    class A,B,C,D,E cat
    class A1,A2,A3,A4,A5,A6,A7,B1,B2,B3,B4,B5,C1,C2,C3,D1,D2,D3,E1,E2,E3 leaf"""
    ),

    "§6 L3 检索思维导图": (
        "🔍 §6 L3 检索全景: Hybrid 三通道 / RRF 融合 / Reranker / Query 改写 / 后处理.",
        """flowchart LR
    R(("检索"))
    R --> A["Hybrid 三通道"]
    R --> B["融合排序"]
    R --> C["Reranker"]
    R --> D["Query 改写"]
    R --> E["后处理"]

    A --> A1["Dense ANN (语义近邻检索)"]
    A --> A2["Sparse BM25 (字面匹配)"]
    A --> A3["SPLADE (神经稀疏检索)"]

    B --> B1["RRF (倒数排名融合)"]
    B --> B2["加权融合 (Weighted Sum)"]
    B --> B3["k 调参经验 (k=60 最优)"]

    C --> C1["BGE-Reranker (Cross-Encoder)"]
    C --> C2["Cohere Rerank-3.5 (API)"]
    C --> C3["ColBERT-v2 (后期交互)"]
    C --> C4["LLM Reranker Cascade (RankGPT)"]

    D --> D1["HyDE (假设文档生成)"]
    D --> D2["Multi-Query (多变体改写)"]
    D --> D3["Step-Back (抽象提问)"]
    D --> D4["Decomposition (子问题拆解)"]
    D --> D5["RAG-Fusion (多 query 融合)"]

    E --> E1["MMR (最大边际相关, 多样性)"]
    E --> E2["LongContextReorder (长文重排)"]
    E --> E3["Adaptive K (自适应 top-K)"]
    E --> E4["CRAG (Web Search 兜底)"]

    classDef root fill:#3B82F6,color:#fff,stroke:#1e40af,stroke-width:2px
    classDef cat fill:#A855F7,color:#fff,stroke:#6b21a8,stroke-width:1px
    classDef leaf fill:#f6f8fa,color:#1f2328,stroke:#d1d9e0
    class R root
    class A,B,C,D,E cat
    class A1,A2,A3,B1,B2,B3,C1,C2,C3,C4,D1,D2,D3,D4,D5,E1,E2,E3,E4 leaf"""
    ),

    "§7 L4 Router 思维导图": (
        "🚦 §7 L4 Router 全景: 三层路由 / Query 分类 / 路径输出 / 流量分流.",
        """flowchart LR
    R(("Router"))
    R --> A["三层路由"]
    R --> B["Query 分类"]
    R --> C["路径输出"]
    R --> D["80/15/5 流量分流"]
    R --> E["监控"]

    A --> A1["规则正则匹配 (最快, 70%)"]
    A --> A2["语义匹配 kNN (中等, 20%)"]
    A --> A3["LLM-as-judge 兜底 (10%)"]

    B --> B1["FAQ 简单查询"]
    B --> B2["编号 / SKU 查询"]
    B --> B3["复杂跨系统诊断"]
    B --> B4["实时状态查询"]
    B --> B5["跨多源 / 多步骤"]

    C --> C1["simple_rag (普通 RAG)"]
    C --> C2["enhanced_rag (HyDE/Multi-Query)"]
    C --> C3["agent (多步推理)"]
    C --> C4["text2sql (结构化数据)"]
    C --> C5["clarification (反问澄清)"]
    C --> C6["refusal (拒答)"]

    D --> D1["80% 简单 RAG ($0.008)"]
    D --> D2["15% 增强 RAG ($0.02)"]
    D --> D3["Agent"]

    E --> E1["Path 分布偏移监控"]
    E --> E2["Router 准确率 ≥ 0.95"]
    E --> E3["延迟"]

    classDef root fill:#3B82F6,color:#fff,stroke:#1e40af,stroke-width:2px
    classDef cat fill:#A855F7,color:#fff,stroke:#6b21a8,stroke-width:1px
    classDef leaf fill:#f6f8fa,color:#1f2328,stroke:#d1d9e0
    class R root
    class A,B,C,D,E cat
    class A1,A2,A3,B1,B2,B3,B4,B5,C1,C2,C3,C4,C5,C6,D1,D2,D3,E1,E2,E3 leaf"""
    ),

    "§8 L5 Agent 思维导图": (
        "🤖 §8 L5 Agent 全景: 框架 / Tool Calling / Memory 分层 / 高级模式 / Agent 代价.",
        """flowchart LR
    R(("Agent"))
    R --> A["Agent 框架"]
    R --> B["Tool Calling 工具调用 (双手)"]
    R --> C["Memory 分层"]
    R --> D["高级模式"]
    R --> E["Agent 代价"]

    A --> A1["LangGraph (LangChain 图状)"]
    A --> A2["LlamaIndex Agents (RAG 集成)"]
    A --> A3["AutoGen (Microsoft 多 Agent)"]
    A --> A4["CrewAI (角色化, 易上手)"]
    A --> A5["OpenAI Agents SDK (前 Swarm)"]
    A --> A6["Anthropic Claude Agent SDK"]

    B --> B1["定义 Tool JSON Schema"]
    B --> B2["LLM 选 Tool + 输出参数"]
    B --> B3["执行 + 序列化结果回传"]
    B --> B4["多轮迭代 (循环)"]

    C --> C1["L1 Session (Redis, 6h TTL)"]
    C --> C2["L2 User Pref (Postgres JSONB)"]
    C --> C3["L3 Business Memory (Vector DB)"]

    D --> D1["Self-RAG (自反思, Asai 2023)"]
    D --> D2["CRAG (校正+兜底, Yan 2024)"]
    D --> D3["GraphRAG (图谱检索, Microsoft)"]
    D --> D4["LightRAG (轻量图谱, HKUDS)"]
    D --> D5["Adaptive RAG (自适应分流)"]

    E --> E1["延迟"]
    E --> E2["成本"]
    E --> E3["调试难 (LangSmith 必上)"]
    E --> E4["死循环 (max_steps 必设)"]

    classDef root fill:#3B82F6,color:#fff,stroke:#1e40af,stroke-width:2px
    classDef cat fill:#A855F7,color:#fff,stroke:#6b21a8,stroke-width:1px
    classDef leaf fill:#f6f8fa,color:#1f2328,stroke:#d1d9e0
    class R root
    class A,B,C,D,E cat
    class A1,A2,A3,A4,A5,A6,B1,B2,B3,B4,C1,C2,C3,D1,D2,D3,D4,D5,E1,E2,E3,E4 leaf"""
    ),

    "§9 横切思维导图": (
        "🛠️ §9 横切全景: 权限审计 / 缓存 / 拒答 / 可观测 / 部署 / 合规.",
        """flowchart LR
    R(("横切"))
    R --> A["权限审计"]
    R --> B["缓存策略"]
    R --> C["拒答机制"]
    R --> D["可观测"]
    R --> E["部署模式"]
    R --> F["合规"]

    A --> A1["Doc 级 ACL (文档权限)"]
    A --> A2["Chunk 级 metadata 隔离"]
    A --> A3["Output 二次过滤 (PII)"]
    A --> A4["Audit Log (完整审计)"]

    B --> B1["HTTP Cache (30-60% 命中)"]
    B --> B2["Embedding Cache (70-90%)"]
    B --> B3["Retrieval Cache (20-40%)"]
    B --> B4["Generation Cache (10-25%)"]
    B --> B5["Semantic Cache (GPTCache)"]

    C --> C1["Faithfulness 阈值调优"]
    C --> C2["拒答兜底回复"]
    C --> C3["Air Canada 法律事故教训"]

    D --> D1["LangSmith (LangChain 追踪)"]
    D --> D2["Phoenix (Arize, 开源)"]
    D --> D3["Langfuse (开源, 自托管)"]

    E --> E1["SaaS 公有云"]
    E --> E2["私有云 (VPC)"]
    E --> E3["混合云 (Hybrid Cloud)"]
    E --> E4["端侧 Local (浏览器/手机)"]
    E --> E5["边缘 Edge (CDN)"]

    F --> F1["GDPR (欧盟通用数据保护)"]
    F --> F2["EU AI Act (欧盟 AI 法案)"]
    F --> F3["中国个保法 (PIPL)"]
    F --> F4["HIPAA (美国医疗数据保护)"]

    classDef root fill:#3B82F6,color:#fff,stroke:#1e40af,stroke-width:2px
    classDef cat fill:#A855F7,color:#fff,stroke:#6b21a8,stroke-width:1px
    classDef leaf fill:#f6f8fa,color:#1f2328,stroke:#d1d9e0
    class R root
    class A,B,C,D,E,F cat
    class A1,A2,A3,A4,B1,B2,B3,B4,B5,C1,C2,C3,D1,D2,D3,E1,E2,E3,E4,E5,F1,F2,F3,F4 leaf"""
    ),

    "§20 Agent RAG 思维导图": (
        "🎯 §20 Agent RAG 全景: 三层模型 / Workflow Pattern / Agent 部件 / 架构层级 / Agent 形态 / 框架 / 防御.",
        """flowchart LR
    R(("Agent RAG"))
    R --> A["Anthropic 三层模型"]
    R --> B["Workflow Pattern"]
    R --> C["Agent 5 部件"]
    R --> D["架构七层"]
    R --> E["Agent 形态"]
    R --> F["主流框架"]
    R --> G["死循环防御"]
    R --> H["FinOps 杠杆"]

    A --> A1["Augmented LLM (单 LLM + 检索)"]
    A --> A2["Workflow (固定路径多步)"]
    A --> A3["Agent"]

    B --> B1["Prompt Chaining (链式调用)"]
    B --> B2["Routing (路由分流)"]
    B --> B3["Parallelization (并行化)"]
    B --> B4["Orchestrator-Workers (协调员-工人)"]
    B --> B5["Evaluator-Optimizer (评估-优化)"]

    C --> C1["Modular RAG 基座 (检索)"]
    C --> C2["Planner 规划器 (大脑)"]
    C --> C3["Tool Calling 工具调用 (双手)"]
    C --> C4["Memory 三层 (脊髓)"]
    C --> C5["多步推理 (心跳循环)"]

    D --> D1["L1 Query Understanding 入口"]
    D --> D2["L2 Router 路由"]
    D --> D3["Planner 规划器 (大脑)"]
    D --> D4["L4 Tool Loop 工具循环"]
    D --> D5["Memory 三层 (脊髓)"]
    D --> D6["L6 Synthesizer 综合"]
    D --> D7["L7 Validator 校验"]

    E --> E1["Plan-and-Execute (规划-执行)"]
    E --> E2["ReAct (推理-行动循环)"]
    E --> E3["Multi-Agent (多角色协作)"]
    E --> E4["Self-Reflection (自反思)"]
    E --> E5["Iterative (迭代检索)"]

    F --> F1["LangGraph (LangChain 图状)"]
    F --> F2["LlamaIndex Agents (RAG 集成)"]
    F --> F3["AutoGen (Microsoft 多 Agent)"]
    F --> F4["CrewAI (角色化, 易上手)"]
    F --> F5["OpenAI Agents SDK (前 Swarm)"]
    F --> F6["Anthropic Claude Agent SDK"]

    G --> G1["max_steps (硬上限)"]
    G --> G2["timeout (超时熔断)"]
    G --> G3["budget cap (预算上限)"]
    G --> G4["同 tool 重复检测"]

    H --> H1["选对层次 (10-50× 最大)"]
    H --> H2["80/15/5 流量分流"]
    H --> H3["Planner/Executor 模型分级"]
    H --> H4["Anthropic Prompt Caching (省 35-49%)"]
    H --> H5["Batch API (省 50%)"]

    classDef root fill:#3B82F6,color:#fff,stroke:#1e40af,stroke-width:2px
    classDef cat fill:#A855F7,color:#fff,stroke:#6b21a8,stroke-width:1px
    classDef leaf fill:#f6f8fa,color:#1f2328,stroke:#d1d9e0
    class R root
    class A,B,C,D,E,F,G,H cat
    class A1,A2,A3,B1,B2,B3,B4,B5,C1,C2,C3,C4,C5,D1,D2,D3,D4,D5,D6,D7,E1,E2,E3,E4,E5,F1,F2,F3,F4,F5,F6,G1,G2,G3,G4,H1,H2,H3,H4,H5 leaf"""
    ),
}


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<meta name="description" content="RAG (Retrieval-Augmented Generation) 知识地图 — 完整覆盖 5 层企业架构、Hybrid 检索、Modular RAG、Agent RAG (Gen 4)、22 真实生产案例、60+ 面试题、源码实现, 17000+ 行 / 12000+ 节点 / 60 张架构图.">
<meta name="keywords" content="RAG, 检索增强生成, LLM, Embedding, BM25, HNSW, Hybrid Search, Reranker, Modular RAG, Agent RAG, Vector Database, GraphRAG, Self-RAG, CRAG, RAGAS, 面试">
<meta name="author" content="RAG Knowledge Map">
<meta name="robots" content="index, follow">

<!-- Open Graph (社交分享) -->
<meta property="og:type" content="article">
<meta property="og:title" content="__TITLE__">
<meta property="og:description" content="完整 RAG 知识体系 — 从原理到生产部署, 含 60+ 面试题 + 22 真实案例">
<meta property="og:locale" content="zh_CN">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="__TITLE__">
<meta name="twitter:description" content="完整 RAG 知识体系 — 17000+ 行 / 60 张架构图 / 60+ 面试题">

<!-- Favicon (内嵌 SVG, 0 外部依赖) -->
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='20' fill='%230969da'/%3E%3Ctext x='50' y='65' font-size='52' font-family='Arial,sans-serif' font-weight='700' fill='white' text-anchor='middle'%3ER%3C/text%3E%3C/svg%3E">

<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
:root {
  --bg: #fdfcf9;
  --bg-alt: #f6f5f0;
  --bg-soft: #faf9f5;
  --text: #2a2e36;
  --text-muted: #656d76;
  --border: #d1d9e0;
  --border-light: #e5e9ee;
  --accent: #0969da;
  --accent-light: #54aeff;
  --code-bg: #f6f8fa;
  --code-inline-bg: #fff5e6;
  --code-inline-fg: #c25e00;
  --link: #0969da;
  --table-stripe: #f6f8fa;
  --table-header-bg: #eaeef2;
  --quote-bg: #fffbeb;
  --quote-border: #f0c850;
  --quote-fg: #5c4a00;
  --caption-bg: #fff8e1;
  --caption-fg: #6e5400;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0d1117;
    --bg-alt: #161b22;
    --bg-soft: #11161d;
    --text: #e6edf3;
    --text-muted: #7d8590;
    --border: #30363d;
    --border-light: #21262d;
    --accent: #58a6ff;
    --accent-light: #79b8ff;
    --code-bg: #161b22;
    --code-inline-bg: #2d2419;
    --code-inline-fg: #ffa657;
    --link: #58a6ff;
    --table-stripe: #161b22;
    --table-header-bg: #21262d;
    --quote-bg: #2a2310;
    --quote-border: #d4a72c;
    --quote-fg: #e8c547;
    --caption-bg: #2a2310;
    --caption-fg: #f5d57c;
  }
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  font-family: "HarmonyOS Sans SC", "PingFang SC", "Microsoft YaHei",
    "Source Han Sans SC", "Noto Sans SC", -apple-system, BlinkMacSystemFont,
    "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  font-size: 16px;
  line-height: 1.8;
  letter-spacing: 0.015em;
  color: var(--text);
  background: var(--bg);
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
.layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  min-height: 100vh;
}
nav.toc {
  background: var(--bg-alt);
  border-right: 1px solid var(--border);
  padding: 28px 18px;
  overflow-y: auto;
  height: 100vh;
  position: sticky;
  top: 0;
  font-size: 13px;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
nav.toc::-webkit-scrollbar { width: 8px; }
nav.toc::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
nav.toc::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
nav.toc > h2 {
  font-size: 13px;
  margin: 0 0 14px;
  padding: 0;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 700;
  background: none;
  border: none;
  border-radius: 0;
  box-shadow: none;
}
nav.toc ul { list-style: none; padding-left: 0; margin: 0; }
nav.toc li { margin: 1px 0; }
nav.toc a {
  color: var(--text);
  text-decoration: none;
  display: block;
  padding: 5px 10px;
  border-radius: 4px;
  border-left: 2px solid transparent;
  transition: all 0.15s;
  line-height: 1.4;
}
nav.toc a:hover {
  background: var(--border);
  color: var(--accent);
  border-left-color: var(--accent);
  text-decoration: none;
}
nav.toc .toc-h2 {
  font-weight: 700;
  margin-top: 12px;
  padding-left: 10px;
  font-size: 14px;
  color: var(--text);
}
nav.toc .toc-h2:first-child { margin-top: 0; }
nav.toc .toc-h3 {
  padding-left: 24px;
  color: var(--text-muted);
  font-size: 12px;
}

main {
  padding: 56px 80px;
  max-width: 1100px;
  overflow-x: auto;
}

/* ===== 标题层级 — 6 级清晰梯度 (字号 + 颜色 + 边框 三维渐变) ===== */

h1, h2, h3, h4, h5, h6 { scroll-margin-top: 24px; }

/* H1 — 文档主标题 */
h1 {
  font-size: 36px;
  margin: 0 0 28px;
  color: var(--text);
  border-bottom: 3px solid var(--accent);
  padding-bottom: 20px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

/* H2 — 章 (一/二/三...) — 8px 粗左条 + 大字 + 浅背景 */
h2 {
  font-size: 32px;
  margin: 80px 0 28px;
  padding: 18px 24px 14px;
  background: var(--bg-alt);
  border-left: 8px solid var(--accent);
  color: var(--text);
  font-weight: 700;
  letter-spacing: -0.01em;
  border-radius: 0 8px 8px 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
h2:first-of-type { margin-top: 32px; }

/* H3 — 节 (X.Y) — 5px 中粗左条 + 中字 + accent 色 (无背景, 跟 h2 区分) */
h3 {
  font-size: 24px;
  margin: 56px 0 16px;
  padding: 6px 0 6px 14px;
  border-left: 5px solid var(--accent);
  color: var(--accent);
  font-weight: 600;
  letter-spacing: -0.005em;
  background: none;
}

/* H4 — 子节 (X.Y.Z) — 3px 灰左条 + 较小 + text 色 */
h4 {
  font-size: 19px;
  margin: 36px 0 12px;
  padding: 4px 0 4px 12px;
  border-left: 3px solid var(--text-muted);
  color: var(--text);
  font-weight: 600;
}

/* H5 — 小节 — 圆点前缀 + 小字 + 普通 text 色 */
h5 {
  font-size: 16px;
  margin: 28px 0 10px;
  color: var(--text);
  font-weight: 600;
  padding-left: 0;
  border-left: none;
}
h5::before {
  content: "▸ ";
  color: var(--accent);
  font-weight: 700;
  margin-right: 2px;
}

/* H6 — 最细分 — 灰斜体 + 双引号前缀 */
h6 {
  font-size: 14px;
  margin: 18px 0 8px;
  color: var(--text-muted);
  font-weight: 600;
}
h6::before {
  content: "» ";
  color: var(--border);
  font-weight: normal;
}

/* ===== 段落 / 列表 ===== */

p { margin: 20px 0; max-width: 78ch; }

ul, ol { padding-left: 28px; margin: 16px 0; }
li { margin: 10px 0; line-height: 1.8; }
li > ul, li > ol { margin: 10px 0; }

/* 嵌套列表 marker 分级 */
ul { list-style-type: disc; }
ul ul { list-style-type: circle; }
ul ul ul { list-style-type: square; }
ul ul ul ul { list-style: none; }
ul ul ul ul li::before {
  content: "▸ ";
  color: var(--accent);
  margin-right: 4px;
  font-weight: 700;
}

/* ===== Inline code — 暖色调突出, 跟 pre code 区分 ===== */
code {
  font-family: "SF Mono", "Cascadia Code", "Source Code Pro", Consolas, monospace;
  background: var(--code-inline-bg);
  color: var(--code-inline-fg);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.88em;
  border: 1px solid var(--border-light);
}

/* ===== 表格 — 弱化表头, 浅 zebra, hover 高亮 ===== */
table {
  border-collapse: collapse;
  margin: 24px 0;
  font-size: 15px;
  width: 100%;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  border-radius: 6px;
  overflow: hidden;
}
th, td {
  border: 1px solid var(--border);
  padding: 12px 16px;
  text-align: left;
  vertical-align: top;
  line-height: 1.7;
}
th {
  background: var(--table-header-bg);
  color: var(--text);
  font-weight: 700;
  border-bottom: 2px solid var(--accent);
}
tr:nth-child(even) td { background: var(--bg-soft); }
tr:hover td { background: rgba(88, 166, 255, 0.08); }

/* ===== Blockquote — 软调浅黄, 跟 h2/h3 风格区分 ===== */
blockquote {
  border-left: 4px solid var(--quote-border);
  padding: 14px 22px;
  margin: 24px 0;
  background: var(--quote-bg);
  color: var(--quote-fg);
  border-radius: 0 6px 6px 0;
}
blockquote p { margin: 6px 0; }
blockquote p:first-child { margin-top: 0; }
blockquote p:last-child { margin-bottom: 0; }
blockquote p:first-child::before {
  content: "「";
  color: var(--quote-border);
  font-weight: 700;
  font-size: 1.3em;
  margin-right: 4px;
  vertical-align: -2px;
}

a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }

/* HR — 简化为低调细线, 减少跟 h2 80px margin 的视觉重复 */
hr {
  border: none;
  height: 1px;
  background: var(--border-light);
  margin: 48px 0;
}

/* Mermaid 容器 + caption */
.mermaid-figure {
  margin: 28px 0;
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  background: var(--bg-alt);
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.mermaid {
  padding: 32px 28px;
  text-align: center;
  background: var(--bg);
  border-bottom: 1px solid var(--border);
}
.mermaid svg { max-width: 100%; height: auto; }
.mermaid-caption {
  background: var(--caption-bg);
  color: var(--caption-fg);
  padding: 14px 22px;
  font-size: 13.5px;
  line-height: 1.75;
  border-left: 3px solid var(--caption-fg);
}

/* Pre 代码块 — 加右上角 language tag */
pre {
  background: var(--code-bg);
  padding: 22px 20px 18px;
  border-radius: 8px;
  overflow-x: auto;
  border: 1px solid var(--border);
  margin: 22px 0;
  font-size: 13.5px;
  line-height: 1.6;
  position: relative;
}
pre::before {
  content: "CODE";
  position: absolute;
  top: 0;
  right: 0;
  background: var(--text-muted);
  color: var(--bg);
  font-size: 10px;
  font-family: -apple-system, "SF Pro Display", sans-serif;
  font-weight: 700;
  padding: 3px 12px;
  border-radius: 0 8px 0 6px;
  letter-spacing: 0.08em;
}
pre code {
  background: none;
  padding: 0;
  border: none;
  font-size: inherit;
  color: var(--text);
}

/* Reading progress */
.progress {
  position: fixed; top: 0; left: 0; right: 0;
  height: 3px; background: transparent; z-index: 100;
}
.progress-bar {
  height: 100%; background: var(--accent);
  width: 0; transition: width 0.1s;
}

@media (max-width: 900px) {
  .layout { grid-template-columns: 1fr; }
  nav.toc {
    position: relative; height: auto; max-height: 300px;
    border-right: none; border-bottom: 1px solid var(--border);
  }
  main { padding: 28px 20px; }
  h1 { font-size: 26px; } h2 { font-size: 24px; } h3 { font-size: 20px; }
  h4 { font-size: 17px; }
}

h3:hover::before, h4:hover::before {
  content: "#"; color: var(--text-muted);
  margin-right: 8px; font-size: 0.7em;
}

/* Pronunciation — 默认隐藏音标和喇叭, 悬停时才显示 */
.pron {
  position: relative;
  border-bottom: 1px dashed var(--accent);
  cursor: pointer;
}
.pron .ipa {
  display: none;
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  background: var(--bg-alt);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 12px;
  color: var(--accent);
  font-style: italic;
  font-family: "Lucida Sans Unicode", "DejaVu Sans", sans-serif;
  white-space: nowrap;
  z-index: 10;
  box-shadow: 0 2px 6px rgba(0,0,0,0.15);
}
.pron .speak-btn {
  display: none;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 12px;
  padding: 0 2px;
  vertical-align: middle;
}
.pron:hover .ipa { display: block; }
.pron:hover .speak-btn { display: inline; }
.pron:hover { background: rgba(88, 166, 255, 0.1); border-radius: 3px; }
</style>
</head>
<body>
<div class="progress"><div class="progress-bar" id="progress"></div></div>
<div class="layout">
<nav class="toc">
<h2>📚 目录</h2>
__TOC__
</nav>
<main id="content">
__BODY__
</main>
</div>
<script>
mermaid.initialize({
  startOnLoad: true,
  theme: window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'default',
  flowchart: { curve: 'basis', useMaxWidth: true },
  sequence: { useMaxWidth: true },
  securityLevel: 'loose'
});

const progress = document.getElementById('progress');
window.addEventListener('scroll', () => {
  const total = document.body.scrollHeight - window.innerHeight;
  progress.style.width = ((window.scrollY / total) * 100) + '%';
});

const tocLinks = document.querySelectorAll('nav.toc a');
const headings = Array.from(document.querySelectorAll('h2[id], h3[id]'));
function updateActiveTOC() {
  const scrollPos = window.scrollY + 100;
  let active = null;
  for (const h of headings) {
    if (h.offsetTop <= scrollPos) active = h.id;
  }
  tocLinks.forEach(a => {
    if (a.getAttribute('href') === '#' + active) {
      a.style.background = 'var(--border)';
      a.style.color = 'var(--accent)';
    } else {
      a.style.background = ''; a.style.color = '';
    }
  });
}
window.addEventListener('scroll', updateActiveTOC);
updateActiveTOC();

/* ===== Pronunciation TTS (v2: 等 voice 加载 + 错误诊断 + Chrome 卡住修复) ===== */
window.__ttsVoices = [];

function _loadVoices() {
  if (!('speechSynthesis' in window)) return;
  window.__ttsVoices = window.speechSynthesis.getVoices();
  if (window.__ttsVoices.length === 0) {
    /* Chrome 异步加载, 给 voiceschanged 一次机会 */
    window.speechSynthesis.addEventListener('voiceschanged', function once() {
      window.__ttsVoices = window.speechSynthesis.getVoices();
      console.log('[TTS] voices loaded:', window.__ttsVoices.length);
      window.speechSynthesis.removeEventListener('voiceschanged', once);
    });
  } else {
    console.log('[TTS] voices ready (sync):', window.__ttsVoices.length);
  }
}

function _pickEnglishVoice(voices) {
  return voices.find(v => v.lang.startsWith('en') && /google/i.test(v.name))
    || voices.find(v => v.lang.startsWith('en') && /samantha|alex|daniel|karen/i.test(v.name))
    || voices.find(v => v.lang === 'en-US')
    || voices.find(v => v.lang.startsWith('en'))
    || voices[0]
    || null;
}

function _doSpeak(word) {
  try {
    window.speechSynthesis.cancel();  /* 清掉之前残留 */
    const u = new SpeechSynthesisUtterance(word);
    u.lang = 'en-US';
    u.rate = 0.85;
    u.pitch = 1;
    u.volume = 1.0;

    const v = _pickEnglishVoice(window.__ttsVoices);
    if (v) {
      u.voice = v;
      console.log('[TTS] speak "' + word + '" via:', v.name, '(' + v.lang + ')');
    } else {
      console.warn('[TTS] no voice picked, using browser default');
    }

    u.onstart = () => console.log('[TTS] start:', word);
    u.onend = () => console.log('[TTS] end:', word);
    u.onerror = (e) => {
      console.error('[TTS] utterance error:', e.error, 'word:', word);
      alert('语音播放出错: ' + e.error + ' (词: ' + word + ')\\n\\n常见原因:\\n1. 浏览器禁用了 Web Speech\\n2. 系统 TTS 引擎未启用\\n3. 用户未与页面交互');
    };

    window.speechSynthesis.speak(u);

    /* Chrome bug: 长文本/久等会 stall, 250ms 后 resume 一次 */
    setTimeout(() => {
      if (window.speechSynthesis.speaking || window.speechSynthesis.pending) {
        window.speechSynthesis.resume();
      }
    }, 250);
  } catch (e) {
    console.error('[TTS] exception:', e);
    alert('语音播放异常: ' + e.message);
  }
}

function speak(word) {
  console.log('[TTS] speak() called with:', word);
  if (!('speechSynthesis' in window)) {
    alert('浏览器不支持 Web Speech API');
    return;
  }
  /* 如果 voice 还没加载, 等一下再 speak */
  if (window.__ttsVoices.length === 0) {
    window.__ttsVoices = window.speechSynthesis.getVoices();
    if (window.__ttsVoices.length === 0) {
      console.log('[TTS] voices empty, waiting for voiceschanged...');
      window.speechSynthesis.addEventListener('voiceschanged', function once() {
        window.__ttsVoices = window.speechSynthesis.getVoices();
        console.log('[TTS] voices arrived after wait:', window.__ttsVoices.length);
        window.speechSynthesis.removeEventListener('voiceschanged', once);
        _doSpeak(word);
      });
      return;
    }
  }
  _doSpeak(word);
}

/* 页面加载后预热 voice 列表 */
_loadVoices();
window.addEventListener('load', _loadVoices);
</script>
</body>
</html>
"""


def build_toc(html: str) -> str:
    headings = re.findall(
        r'<h([23])\s+id="([^"]+)"[^>]*>(.*?)</h\1>', html, re.DOTALL
    )
    if not headings:
        return ""
    items: list[str] = []
    for level, anchor, text in headings:
        clean_text = re.sub(r"<[^>]+>", "", text).strip()
        cls = f"toc-h{level}"
        items.append(
            f'<li class="{cls}"><a href="#{anchor}">{clean_text}</a></li>'
        )
    return "<ul>" + "\n".join(items) + "</ul>"


def inject_mermaid(html: str) -> str:
    """在含特定文本的 heading 后插入 Mermaid 图 + caption."""
    inserted = 0
    for heading_text, (caption, mermaid_code) in MERMAID_DIAGRAMS.items():
        # 匹配 h3/h4/h5
        pattern = re.compile(
            r"(<h[345]\s+id=\"[^\"]+\"[^>]*>[^<]*"
            + re.escape(heading_text)
            + r"[^<]*</h[345]>)",
            re.IGNORECASE,
        )
        figure_html = (
            r"\1"
            + '\n<figure class="mermaid-figure">'
            + '\n<pre class="mermaid">'
            + mermaid_code.strip()
            + "</pre>"
            + f'\n<figcaption class="mermaid-caption">{caption}</figcaption>'
            + "\n</figure>"
        )
        new_html, n = pattern.subn(figure_html, html, count=1)
        if n == 0:
            pattern2 = re.compile(
                r"(<h[345][^>]*>[^<]*"
                + re.escape(heading_text)
                + r"[^<]*</h[345]>)",
                re.IGNORECASE,
            )
            new_html, n = pattern2.subn(figure_html, html, count=1)
        if n == 0:
            print(
                f"  [warn] heading not found for diagram: {heading_text}",
                file=sys.stderr,
            )
        else:
            inserted += 1
            html = new_html
    print(f"  插入 Mermaid 图: {inserted} / {len(MERMAID_DIAGRAMS)}")
    return html


# ============================================================
# Pronunciation Dictionary  (term → IPA)
# 点击 🔊 朗读, 音标显示在旁边
# ============================================================
PRONUNCIATION: dict[str, str] = {
    # Core architecture
    "RAG": "/ræɡ/",
    "LLM": "/ɛl ɛl ɛm/",
    "Embedding": "/ɪmˈbɛdɪŋ/",
    "Embedder": "/ɪmˈbɛdər/",
    "Agent": "/ˈeɪdʒənt/",
    "Pipeline": "/ˈpaɪplaɪn/",
    "Workflow": "/ˈwɜːrkfloʊ/",
    "Modular": "/ˈmɒdjʊlər/",
    # L1
    "Ingestion": "/ɪnˈdʒɛstʃən/",
    "Parser": "/ˈpɑːrsər/",
    "Chunking": "/ˈtʃʌŋkɪŋ/",
    "Chunk": "/tʃʌŋk/",
    "Deduplication": "/diːˌdjuːplɪˈkeɪʃən/",
    "Schema": "/ˈskiːmə/",
    "Governance": "/ˈɡʌvərnəns/",
    "Canonical": "/kəˈnɒnɪkəl/",
    # L2
    "Vector": "/ˈvɛktər/",
    "Dense": "/dɛns/",
    "Sparse": "/spɑːrs/",
    "Hybrid": "/ˈhaɪbrɪd/",
    "HNSW": "/eɪtʃ ɛn ɛs ˈdʌbəljuː/",
    "Cosine": "/ˈkoʊsaɪn/",
    "Matryoshka": "/ˌmætrɪˈɒʃkə/",
    # L3
    "Retrieval": "/rɪˈtriːvəl/",
    "Reranker": "/riːˈræŋkər/",
    "Query": "/ˈkwɪri/",
    "Fusion": "/ˈfjuːʒən/",
    "Cascade": "/kæˈskeɪd/",
    "Latency": "/ˈleɪtənsi/",
    "Throughput": "/ˈθruːpʊt/",
    "SPLADE": "/spleɪd/",
    "ColBERT": "/koʊlˈbɜːrt/",
    "HyDE": "/haɪd/",
    "CRAG": "/kræɡ/",
    # L4 + L5
    "Router": "/ˈruːtər/",
    "Planner": "/ˈplænər/",
    "Orchestration": "/ˌɔːrkɪˈstreɪʃən/",
    "Memory": "/ˈmɛməri/",
    "ReAct": "/riːˈækt/",
    "Iteration": "/ˌɪtəˈreɪʃən/",
    "Iterative": "/ˈɪtərətɪv/",
    # Generation & Eval
    "Inference": "/ˈɪnfərəns/",
    "Token": "/ˈtoʊkən/",
    "Tokenizer": "/ˈtoʊkənaɪzər/",
    "Streaming": "/ˈstriːmɪŋ/",
    "Prompt": "/prɑːmpt/",
    "Hallucination": "/həˌluːsɪˈneɪʃən/",
    "Faithfulness": "/ˈfeɪθfəlnəs/",
    "Relevancy": "/ˈrɛləvənsi/",
    "Precision": "/prɪˈsɪʒən/",
    "Recall": "/rɪˈkɔːl/",
    "Citation": "/saɪˈteɪʃən/",
    "Refusal": "/rɪˈfjuːzəl/",
    "Cache": "/kæʃ/",
    "RAGAS": "/ˈrɑːɡəs/",
    # Infra
    "Kubernetes": "/kuːbərˈnɛtiːz/",
    "Elasticsearch": "/ɪˌlæstɪkˈsɜːrtʃ/",
    "PostgreSQL": "/ˈpoʊstɡrɛs kjuː ɛl/",
    "Milvus": "/ˈmɪlvəs/",
    "Qdrant": "/ˈkwɒdrænt/",
    "Weaviate": "/ˈwiːviˌeɪt/",
    "Redis": "/ˈrɛdɪs/",
    "Pinecone": "/ˈpaɪnkoʊn/",
}


def inject_pronunciation(html: str) -> str:
    """给 body 中关键英文术语注入 🔊 发音按钮 + 音标.

    会保护 <pre class="mermaid">, <pre>, <code> 块不被注入 (否则破坏 Mermaid 渲染 / 代码可读性).
    """
    # ---- 1. 抽出受保护块, 占位符替换 ----
    protected: list[str] = []

    def _save(m: re.Match) -> str:
        protected.append(m.group(0))
        return f"___PROTECTED_BLOCK_{len(protected) - 1}___"

    # 顺序: 先 mermaid (最具体), 再 pre (含其它代码块), 最后 inline code
    # mermaid 用 div (md_to_html 注入后) 或 pre 包装, 都需保护
    html = re.sub(r'<div class="mermaid">.*?</div>', _save, html, flags=re.DOTALL)
    html = re.sub(r'<pre class="mermaid">.*?</pre>', _save, html, flags=re.DOTALL)
    html = re.sub(r"<pre[^>]*>.*?</pre>", _save, html, flags=re.DOTALL)
    html = re.sub(r"<code[^>]*>.*?</code>", _save, html, flags=re.DOTALL)

    # ---- 2. 在剩余 HTML 上做发音注入 ----
    injected = 0
    seen: dict[str, int] = {}  # 每个词已注入次数
    max_per_term = 2  # 每个术语最多注入 N 次 (避免满屏喇叭)

    for term, ipa in PRONUNCIATION.items():
        seen[term] = 0
        # 只匹配 body 文本中的独立单词, 不匹配标签内/属性内/已注入的
        pattern = re.compile(
            r'(?<![<\w\-/"\'])(' + re.escape(term) + r')(?![>\w\-/"\'])',
        )

        def _replacer(m: re.Match, _term: str = term, _ipa: str = ipa) -> str:
            if seen[_term] >= max_per_term:
                return m.group(0)
            seen[_term] += 1
            word = m.group(1)
            return (
                f'<span class="pron">{word}'
                f'<span class="ipa">{_ipa}</span>'
                f'<button class="speak-btn" onclick="speak(\'{_term}\')" '
                f'title="点击朗读 {_term}">🔊</button></span>'
            )

        html = pattern.sub(_replacer, html)
        injected += seen[term]

    # ---- 3. 恢复受保护块 ----
    for i, block in enumerate(protected):
        html = html.replace(f"___PROTECTED_BLOCK_{i}___", block)

    print(f"  注入发音按钮: {injected} 个 ({len(PRONUNCIATION)} 术语), 保护代码块: {len(protected)}")
    return html


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.md> <output.html>", file=sys.stderr)
        sys.exit(1)

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    md_text = in_path.read_text(encoding="utf-8")

    md = markdown.Markdown(
        extensions=["extra", "tables", "fenced_code", "toc", "sane_lists"],
        extension_configs={"toc": {"permalink": False}},
    )
    body_html = md.convert(md_text)

    title_match = re.search(r"<h1[^>]*>(.*?)</h1>", body_html)
    title = (
        re.sub(r"<[^>]+>", "", title_match.group(1)).strip()
        if title_match
        else "RAG 知识地图"
    )

    toc = build_toc(body_html)
    body_html = inject_mermaid(body_html)
    body_html = inject_pronunciation(body_html)

    full_html = HTML_TEMPLATE.replace("__TITLE__", title)
    full_html = full_html.replace("__TOC__", toc)
    full_html = full_html.replace("__BODY__", body_html)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(full_html, encoding="utf-8")

    print(f"✓ 写入 {out_path}  ({out_path.stat().st_size:,} bytes)")
    print(f"  - 章节数 (h2): {body_html.count('<h2 ')}")
    print(f"  - 子章节 (h3): {body_html.count('<h3 ')}")
    print("  浏览器双击打开 .html 文件即可查看")


if __name__ == "__main__":
    main()
