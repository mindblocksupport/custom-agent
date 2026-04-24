"use client";

import type { UiMessage } from "../lib/types";

/**
 * TraceInspector: 把单条 assistant 消息的所有事件画成时间线.
 * 数据来源: useAgent 已经塞进 UiMessage 的 blocks (text + tool 交错) + done.
 *
 * 设计:
 * - 完全离线、本地数据
 * - 不调后端 trace API (后续 v2 接入 Langfuse 嵌入)
 */
export function TraceInspector({
  msg,
  onClose,
}: {
  msg: UiMessage | null;
  onClose: () => void;
}) {
  if (!msg) return null;

  const events: Array<{
    icon: string;
    title: string;
    detail?: string;
    accent?: "primary" | "tool" | "kb" | "error" | "done";
  }> = [];

  events.push({
    icon: "▶️",
    title: "请求开始",
    detail: msg.model ? `模型: ${msg.model}` : undefined,
    accent: "primary",
  });
  if (msg.routeReason) {
    events.push({
      icon: "🧭",
      title: "路由决策",
      detail: msg.routeReason,
      accent: "primary",
    });
  }

  let textCounter = 0;
  for (const b of msg.blocks) {
    if (b.kind === "text") {
      textCounter += 1;
      const t = b.text.trim();
      if (t.length > 0) {
        events.push({
          icon: "💬",
          title: `文本输出 ${textCounter}`,
          detail: t.length > 240 ? t.slice(0, 240) + "..." : t,
        });
      }
    } else {
      const inv = b.invocation;
      events.push({
        icon: inv.name === "search_kb" ? "📚" : "🔧",
        title: `工具: ${inv.name} (${inv.status})`,
        detail: inv.argumentsRaw.slice(0, 160),
        accent: inv.name === "search_kb" ? "kb" : "tool",
      });
      if (inv.retrievalQuery) {
        events.push({
          icon: "🔍",
          title: `检索 query`,
          detail: inv.retrievalQuery,
          accent: "kb",
        });
      }
      if (inv.citations) {
        events.push({
          icon: "📎",
          title: `命中 ${inv.citations.length} 条引用`,
          detail: `dense=${inv.nDense ?? "·"} bm25=${inv.nBm25 ?? "·"} rerank=${inv.nRerankIn ?? "·"} · ${inv.elapsedMs ?? "?"}ms`,
          accent: "kb",
        });
      }
      if (inv.refused) {
        events.push({
          icon: "⚠️",
          title: "命中拒绝阈值",
          detail: inv.refusalReason ?? "below threshold",
          accent: "error",
        });
      }
      if (inv.error) {
        events.push({
          icon: "❌",
          title: "工具错误",
          detail: inv.error.slice(0, 200),
          accent: "error",
        });
      } else if (inv.result) {
        events.push({
          icon: "📥",
          title: "工具返回",
          detail: inv.result.slice(0, 160),
          accent: "tool",
        });
      }
    }
  }
  if (msg.error) {
    events.push({
      icon: "💥",
      title: "Agent 错误",
      detail: msg.error,
      accent: "error",
    });
  }
  if (msg.done) {
    events.push({
      icon: "🏁",
      title: "完成",
      detail: `${msg.done.steps} 步 · ↑${msg.done.input_tokens ?? "?"} ↓${msg.done.output_tokens ?? "?"} tok · $${msg.done.cost_usd.toFixed(6)}`,
      accent: "done",
    });
  }

  return (
    <div
      className="fixed inset-0 z-40 flex justify-end"
      style={{ background: "var(--bg-overlay)" }}
      onClick={onClose}
    >
      <div
        className="w-[28rem] max-w-full h-full flex flex-col animate-in"
        style={{
          background: "var(--bg-elev)",
          boxShadow: "var(--shadow-lg)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="px-4 py-3 border-b flex items-start justify-between"
          style={{ borderColor: "var(--border)" }}
        >
          <div className="min-w-0">
            <div
              className="text-[10px] uppercase tracking-wide"
              style={{ color: "var(--fg-subtle)" }}
            >
              Trace inspector
            </div>
            <h2 className="font-semibold text-base" style={{ color: "var(--fg)" }}>
              🔍 单条响应的时间线
            </h2>
            {msg.traceId && (
              <div
                className="text-[10px] font-mono mt-1 truncate"
                style={{ color: "var(--fg-subtle)" }}
                title={msg.traceId}
              >
                trace: {msg.traceId}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-xl leading-none"
            style={{ color: "var(--fg-subtle)" }}
            aria-label="关闭"
          >
            ✕
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          <div className="relative pl-5">
            <div
              className="absolute top-2 bottom-2 left-1.5 w-px"
              style={{ background: "var(--border)" }}
            />
            <ul className="space-y-3">
              {events.map((ev, i) => (
                <li key={i} className="relative">
                  <span
                    className="absolute -left-[18px] top-1 w-3 h-3 rounded-full flex items-center justify-center text-[8px]"
                    style={{
                      background: pickBg(ev.accent),
                      color: "white",
                    }}
                  >
                    •
                  </span>
                  <div
                    className="rounded-md p-2"
                    style={{
                      background: "var(--bg-elev-2)",
                      border: "1px solid var(--border)",
                    }}
                  >
                    <div className="flex items-center gap-1.5">
                      <span className="text-sm">{ev.icon}</span>
                      <span
                        className="text-xs font-medium"
                        style={{ color: "var(--fg)" }}
                      >
                        {ev.title}
                      </span>
                    </div>
                    {ev.detail && (
                      <pre
                        className="text-[10px] font-mono whitespace-pre-wrap break-words mt-1 leading-snug"
                        style={{ color: "var(--fg-muted)" }}
                      >
                        {ev.detail}
                      </pre>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </div>

          {msg.traceId && (
            <div
              className="mt-5 p-2.5 rounded-md text-[10px] leading-relaxed"
              style={{
                background: "var(--info-soft)",
                color: "var(--info-soft-fg)",
                border: "1px solid var(--primary)",
              }}
            >
              💡 <b>外部追踪</b>: 把上方 trace ID 粘到 Langfuse / Jaeger 可看完整 span 树
              (DB 查询、LLM 调用细节、token cost)。后续会在此嵌入 Langfuse iframe.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function pickBg(accent?: "primary" | "tool" | "kb" | "error" | "done") {
  switch (accent) {
    case "primary":
      return "var(--primary)";
    case "tool":
      return "var(--accent)";
    case "kb":
      return "var(--success)";
    case "error":
      return "var(--danger)";
    case "done":
      return "var(--success)";
    default:
      return "var(--fg-subtle)";
  }
}
