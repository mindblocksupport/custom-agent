"use client";

import { useState } from "react";
import type { ToolInvocation } from "../lib/types";

export function ToolCard({ inv }: { inv: ToolInvocation }) {
  const [open, setOpen] = useState(false);
  const statusEmoji =
    inv.status === "ok" ? "✓" : inv.status === "error" ? "✗" : "⏳";
  const statusColor =
    inv.status === "ok"
      ? "border-blue-200 bg-blue-50 text-blue-900"
      : inv.status === "error"
        ? "border-red-200 bg-red-50 text-red-900"
        : "border-neutral-200 bg-neutral-50 text-neutral-700";

  return (
    <div
      className={`my-2 border rounded-md text-xs font-mono ${statusColor}`}
    >
      <button
        onClick={() => setOpen(!open)}
        className="w-full text-left px-3 py-2 flex items-center gap-2"
      >
        <span>{statusEmoji}</span>
        <span className="font-semibold">🔧 {inv.name}</span>
        <span className="text-neutral-500 truncate flex-1">
          ({inv.argumentsRaw})
        </span>
        <span className="text-neutral-400">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="px-3 pb-2 space-y-1.5 border-t border-current/10">
          <Field label="arguments">{inv.argumentsRaw || "{}"}</Field>
          {inv.result !== undefined && <Field label="result">{inv.result}</Field>}
          {inv.error !== undefined && <Field label="error">{inv.error}</Field>}
        </div>
      )}
    </div>
  );
}

function Field({ label, children }: { label: string; children: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-neutral-500 pt-1">
        {label}
      </div>
      <pre className="text-xs whitespace-pre-wrap break-words">{children}</pre>
    </div>
  );
}
