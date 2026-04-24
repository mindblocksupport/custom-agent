"use client";

const CATEGORIES = [
  {
    title: "基础对话",
    icon: "💬",
    desc: "短问、闲聊、解释概念",
    examples: ["现在几点", "用一首五言绝句解释 RAG", "今天周几"],
  },
  {
    title: "知识库 (RAG)",
    icon: "📚",
    desc: "搜索内部文档, 带引用回答",
    examples: [
      "项目用的什么 LLM",
      "ACL 怎么注入的",
      "我们的 RAG pipeline 几个阶段",
    ],
  },
  {
    title: "工具调用",
    icon: "🔧",
    desc: "调外部能力 (calc / time / web / KB)",
    examples: [
      "Calculate sqrt(144) + 23 * 47",
      "北京时间几点然后算 99×88",
      "搜索一下最新的 langchain 新闻",
    ],
  },
  {
    title: "复合任务",
    icon: "🧠",
    desc: "需要多步推理 + 工具 + 知识库",
    examples: [
      "对比下我们和 Coze 的差异",
      "为什么我们选 pgvector 不选 Milvus",
      "分析一下今天的 trace 失败率",
    ],
  },
];

export function Welcome({
  onPick,
  starterExamples,
  skillName,
}: {
  onPick: (text: string) => void;
  starterExamples?: string[];
  skillName?: string;
}) {
  const showSkillStarters = starterExamples && starterExamples.length > 0;

  return (
    <div className="max-w-3xl mx-auto py-10 space-y-6 animate-in">
      <div className="text-center">
        <div
          className="inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-3 text-2xl"
          style={{
            background: "linear-gradient(135deg, var(--primary), var(--accent))",
            color: "white",
            boxShadow: "var(--shadow-md)",
          }}
        >
          🤖
        </div>
        <div
          className="text-2xl font-semibold"
          style={{ color: "var(--fg)" }}
        >
          Custom Agent
        </div>
        <div
          className="text-sm mt-1.5"
          style={{ color: "var(--fg-muted)" }}
        >
          带引用 · 可审计 · 成本可控
        </div>
        <div
          className="flex justify-center gap-1.5 mt-3"
        >
          {["🔍 RAG", "🔒 ACL", "📊 路由", "📈 可观测"].map((t) => (
            <span
              key={t}
              className="text-[10px] px-2 py-0.5 rounded-full"
              style={{
                background: "var(--bg-elev-2)",
                color: "var(--fg-muted)",
                border: "1px solid var(--border)",
              }}
            >
              {t}
            </span>
          ))}
        </div>
      </div>

      {showSkillStarters && (
        <div
          className="rounded-xl p-4"
          style={{
            background: "var(--accent-soft)",
            border: "1px solid var(--accent)",
          }}
        >
          <div
            className="font-semibold text-sm mb-2 flex items-center gap-1.5"
            style={{ color: "var(--accent-soft-fg)" }}
          >
            🧩 Skill「{skillName}」 推荐问法
          </div>
          <div className="space-y-1">
            {starterExamples!.map((ex) => (
              <button
                key={ex}
                onClick={() => onPick(ex)}
                className="block w-full text-left text-xs px-2.5 py-1.5 rounded-md truncate transition"
                style={{ color: "var(--accent-soft-fg)" }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.background = "rgba(255,255,255,0.4)")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = "transparent")
                }
                title={ex}
              >
                → {ex}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {CATEGORIES.map((cat) => (
          <div
            key={cat.title}
            className="p-4 rounded-xl transition cursor-default"
            style={{
              background: "var(--bg-elev)",
              border: "1px solid var(--border)",
              boxShadow: "var(--shadow-sm)",
            }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.borderColor = "var(--primary)")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.borderColor = "var(--border)")
            }
          >
            <div className="flex items-start gap-2 mb-2">
              <span className="text-xl leading-none">{cat.icon}</span>
              <div className="min-w-0">
                <div
                  className="font-semibold text-sm"
                  style={{ color: "var(--fg)" }}
                >
                  {cat.title}
                </div>
                <div
                  className="text-[11px] mt-0.5"
                  style={{ color: "var(--fg-muted)" }}
                >
                  {cat.desc}
                </div>
              </div>
            </div>
            <div className="space-y-1">
              {cat.examples.map((ex) => (
                <button
                  key={ex}
                  onClick={() => onPick(ex)}
                  className="block w-full text-left text-xs px-2 py-1 rounded-md truncate transition"
                  style={{ color: "var(--fg-muted)" }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "var(--primary-soft)";
                    e.currentTarget.style.color = "var(--primary-soft-fg)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "transparent";
                    e.currentTarget.style.color = "var(--fg-muted)";
                  }}
                  title={ex}
                >
                  → {ex}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div
        className="text-center text-[10px] pt-2"
        style={{ color: "var(--fg-subtle)" }}
      >
        💡 Tip: 切换"📚 知识库"上传文档 · "🧩 技能"复用配方 · 右上角"⚙ 工作空间设置"管成员/预算
      </div>
    </div>
  );
}
