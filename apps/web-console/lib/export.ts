/** 会话导出 helpers (Markdown / JSON). */

import type { Session, UiMessage } from "./types";

export function messagesToJson(session: Session, messages: UiMessage[]): string {
  // Strip transient UI 字段 (e.g. local IDs, hover state); 保留语义数据.
  const out = {
    session: {
      id: session.id,
      title: session.title,
      created_at: new Date(session.createdAt).toISOString(),
      updated_at: new Date(session.updatedAt).toISOString(),
      message_count: session.messageCount,
      total_cost_usd: session.totalCostUsd,
    },
    messages: messages.map((m) => ({
      id: m.id,
      role: m.role,
      created_at: new Date(m.createdAt).toISOString(),
      ...(m.text !== undefined ? { text: m.text } : {}),
      blocks: m.blocks.map((b) => {
        if (b.kind === "text") return { kind: "text", text: b.text };
        const inv = b.invocation;
        return {
          kind: "tool",
          name: inv.name,
          arguments_raw: inv.argumentsRaw,
          status: inv.status,
          result: inv.result,
          error: inv.error,
          elapsed_ms: inv.elapsedMs,
          retrieval: inv.citations
            ? {
                query: inv.retrievalQuery,
                refused: inv.refused,
                refusal_reason: inv.refusalReason,
                n_dense: inv.nDense,
                n_bm25: inv.nBm25,
                n_rerank_in: inv.nRerankIn,
                citations: inv.citations,
              }
            : undefined,
        };
      }),
      ...(m.error ? { error: m.error } : {}),
      ...(m.done
        ? {
            done: m.done,
            model: m.model,
            route_reason: m.routeReason,
            trace_id: m.traceId,
          }
        : {}),
    })),
    exported_at: new Date().toISOString(),
    schema_version: 1,
  };
  return JSON.stringify(out, null, 2);
}

export function messagesToMarkdown(session: Session, messages: UiMessage[]): string {
  const lines: string[] = [];
  lines.push(`# ${session.title}`);
  lines.push("");
  lines.push(`> 会话 ID: \`${session.id}\``);
  lines.push(`> 创建: ${new Date(session.createdAt).toLocaleString()}`);
  lines.push(`> 累计成本: $${session.totalCostUsd.toFixed(6)}`);
  lines.push(`> 消息: ${session.messageCount} 条`);
  lines.push("");
  lines.push("---");
  lines.push("");

  for (const m of messages) {
    if (m.role === "user") {
      lines.push("## 👤 User");
      lines.push("");
      lines.push((m.text ?? "").trim() || "(empty)");
      lines.push("");
      continue;
    }
    if (m.role === "assistant") {
      lines.push("## 🤖 Assistant");
      lines.push("");
      for (const b of m.blocks) {
        if (b.kind === "text") {
          lines.push(b.text.trim());
          lines.push("");
        } else if (b.kind === "tool") {
          const inv = b.invocation;
          lines.push(`<details>`);
          lines.push(`<summary>🔧 <code>${inv.name}</code> · ${inv.status}${inv.elapsedMs ? ` · ${inv.elapsedMs}ms` : ""}</summary>`);
          lines.push("");
          lines.push("```json");
          lines.push(`// arguments`);
          lines.push(safeJson(inv.argumentsRaw));
          lines.push("```");
          if (inv.result) {
            lines.push("");
            lines.push("```");
            lines.push(`// result`);
            lines.push(inv.result.slice(0, 4000));
            lines.push("```");
          }
          if (inv.error) {
            lines.push("");
            lines.push("```");
            lines.push(`// error`);
            lines.push(inv.error);
            lines.push("```");
          }
          if (inv.citations && inv.citations.length > 0) {
            lines.push("");
            lines.push(`**📚 ${inv.citations.length} 引用:**`);
            for (const c of inv.citations) {
              lines.push(`- [${c.title ?? c.source_uri}](${c.source_uri}) — \`${c.score.toFixed(3)}\``);
            }
          }
          lines.push("");
          lines.push(`</details>`);
          lines.push("");
        }
      }
      if (m.error) {
        lines.push("");
        lines.push(`> ❌ **error**: ${m.error}`);
        lines.push("");
      }
      if (m.done) {
        const meta = [
          `${m.done.steps} 步`,
          `↑${m.done.input_tokens ?? "?"}/↓${m.done.output_tokens ?? "?"} tok`,
          `$${m.done.cost_usd.toFixed(6)}`,
          m.model ? `model: \`${m.model}\`` : null,
          m.routeReason ? `route: \`${m.routeReason}\`` : null,
          m.traceId ? `trace: \`${m.traceId.slice(0, 12)}\`` : null,
        ].filter(Boolean);
        lines.push(`*${meta.join(" · ")}*`);
        lines.push("");
      }
    }
  }
  return lines.join("\n");
}

function safeJson(s: string): string {
  if (!s.trim()) return "{}";
  try {
    return JSON.stringify(JSON.parse(s), null, 2);
  } catch {
    return s;
  }
}

export function downloadText(filename: string, content: string, mime = "text/markdown") {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
