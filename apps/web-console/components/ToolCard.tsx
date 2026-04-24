"use client";

import { useState } from "react";
import type { ToolInvocation } from "../lib/types";
import { CitationsCard } from "./CitationsCard";

const TOOL_ICON: Record<string, string> = {
  search_kb: "📚",
  get_time: "🕐",
  calculator: "🔢",
  web_search: "🌐",
};

function tryFormatJson(s: string): string {
  if (!s?.trim()) return "{}";
  try {
    return JSON.stringify(JSON.parse(s), null, 2);
  } catch {
    return s;
  }
}

function summarizeArgs(raw: string): string {
  if (!raw?.trim()) return "";
  try {
    const o = JSON.parse(raw);
    if (typeof o === "object" && o !== null) {
      const parts = Object.entries(o)
        .filter(([k]) => k !== "principal_token")
        .map(([k, v]) => {
          const sv =
            typeof v === "string"
              ? v.slice(0, 30)
              : JSON.stringify(v).slice(0, 30);
          return `${k}=${sv}`;
        });
      return parts.join(" ");
    }
  } catch {
    /* fallthrough */
  }
  return raw.slice(0, 80);
}

export function ToolCard({ inv }: { inv: ToolInvocation }) {
  const [open, setOpen] = useState(false);
  const isKb = inv.name === "search_kb";
  const icon = TOOL_ICON[inv.name] ?? "🔧";

  const statusEmoji =
    inv.status === "ok" ? "✓" : inv.status === "error" ? "✗" : "⏳";
  const palette =
    inv.status === "ok"
      ? { bg: "var(--info-soft)", fg: "var(--info-soft-fg)", border: "var(--primary)" }
      : inv.status === "error"
        ? { bg: "var(--danger-soft)", fg: "var(--danger-soft-fg)", border: "var(--danger)" }
        : { bg: "var(--bg-elev-2)", fg: "var(--fg-muted)", border: "var(--border)" };

  return (
    <div className="my-1.5 space-y-1">
      <div
        className="rounded-lg text-xs font-mono"
        style={{
          background: palette.bg,
          color: palette.fg,
          border: `1px solid ${palette.border}`,
        }}
      >
        <button
          onClick={() => setOpen(!open)}
          className="w-full text-left px-3 py-2 flex items-center gap-2"
        >
          <span className="text-sm">{icon}</span>
          <span className="font-semibold">{inv.name}</span>
          <span className="opacity-70 truncate flex-1 font-normal">
            {summarizeArgs(inv.argumentsRaw)}
          </span>
          {inv.elapsedMs != null && (
            <span className="text-[10px] opacity-70">{inv.elapsedMs}ms</span>
          )}
          <span className="text-sm">{statusEmoji}</span>
          <span className="opacity-50">{open ? "▾" : "▸"}</span>
        </button>
        {open && (
          <div
            className="px-3 pb-2 space-y-1.5"
            style={{ borderTop: "1px solid rgba(0,0,0,0.08)" }}
          >
            <Field label="arguments">
              {tryFormatJson(inv.argumentsRaw || "{}")}
            </Field>
            {inv.result !== undefined && (
              <Field label="result">{inv.result}</Field>
            )}
            {inv.error !== undefined && (
              <Field label="error">{inv.error}</Field>
            )}
          </div>
        )}
      </div>

      {/* search_kb: 检索过程 / 引用卡片 */}
      {isKb && inv.status === "running" && !inv.citations && (
        <div
          className="text-[11px] px-2 italic"
          style={{ color: "var(--success-soft-fg)" }}
        >
          🔍 正在检索"{inv.retrievalQuery ?? ""}"...
        </div>
      )}
      {isKb && inv.citations !== undefined && (
        <CitationsCard
          citations={inv.citations}
          refused={inv.refused}
          refusalReason={inv.refusalReason}
          elapsedMs={inv.elapsedMs}
          nDense={inv.nDense}
          nBm25={inv.nBm25}
          nRerankIn={inv.nRerankIn}
        />
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide opacity-60 pt-1">
        {label}
      </div>
      <pre className="text-xs whitespace-pre-wrap break-words leading-snug">
        {children}
      </pre>
    </div>
  );
}
