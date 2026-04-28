"use client";

import { useState } from "react";
import { kbViewer } from "../lib/ui";
import type { CitationData } from "../lib/types";

export function CitationsCard({
  citations,
  refused,
  refusalReason,
  elapsedMs,
  nDense,
  nBm25,
  nRerankIn,
}: {
  citations: CitationData[];
  refused?: boolean;
  refusalReason?: string | null;
  elapsedMs?: number | null;
  nDense?: number;
  nBm25?: number;
  nRerankIn?: number;
}) {
  const [open, setOpen] = useState(false);

  if (refused) {
    return (
      <div
        className="my-1.5 px-3 py-2 rounded-md text-xs"
        style={{
          background: "var(--warning-soft)",
          color: "var(--warning-soft-fg)",
          border: "1px solid var(--warning)",
        }}
      >
        <div className="flex items-center gap-1.5">
          <span>⚠️</span>
          <span className="font-semibold">知识库无相关命中</span>
          {refusalReason && (
            <span className="font-mono opacity-80">({refusalReason})</span>
          )}
          {elapsedMs != null && (
            <span className="ml-auto font-mono opacity-80">{elapsedMs}ms</span>
          )}
        </div>
      </div>
    );
  }

  if (citations.length === 0) return null;

  return (
    <div
      className="my-1.5 rounded-md text-xs"
      style={{
        background: "var(--success-soft)",
        color: "var(--success-soft-fg)",
        border: "1px solid var(--success)",
      }}
    >
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-3 py-2 flex items-center gap-2"
      >
        <span>📚</span>
        <span className="font-semibold">{citations.length} 条引用</span>
        <span className="font-mono text-[10px] opacity-80">
          {nDense != null && `dense:${nDense}`}
          {nBm25 != null && ` · bm25:${nBm25}`}
          {nRerankIn != null && ` · rerank:${nRerankIn}`}
        </span>
        {elapsedMs != null && (
          <span className="ml-auto font-mono opacity-80">{elapsedMs}ms</span>
        )}
        <span className="opacity-70">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <ul
          className="px-3 pb-2 space-y-1.5"
          style={{ borderTop: "1px solid var(--success)" }}
        >
          {citations.map((c, i) => (
            <li
              key={`${c.doc_id}-${c.chunk_id}-${i}`}
              className="rounded p-2 cursor-pointer transition"
              style={{
                background: "var(--bg-elev)",
                border: "1px solid var(--success)",
              }}
              onClick={() =>
                kbViewer.open({
                  docId: c.doc_id,
                  chunkId: c.chunk_id,
                  hintTitle: c.title ?? null,
                })
              }
              onMouseEnter={(e) => {
                e.currentTarget.style.boxShadow = "var(--shadow-md)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.boxShadow = "none";
              }}
              title="点击查看原文 chunk"
            >
              <div className="flex items-center justify-between mb-1">
                <span
                  className="font-semibold truncate flex-1"
                  style={{ color: "var(--success-soft-fg)" }}
                >
                  {c.title ?? c.source_uri}
                </span>
                {c.page != null && (
                  <span
                    className="text-[10px] font-mono ml-2"
                    style={{ color: "var(--success-soft-fg)" }}
                  >
                    p.{c.page}
                  </span>
                )}
                {c.score > 0 && (
                  <span
                    className="text-[10px] font-mono ml-2"
                    style={{ color: "var(--success-soft-fg)" }}
                  >
                    {c.score.toFixed(3)}
                  </span>
                )}
                <span
                  className="text-[10px] ml-2 opacity-60"
                  style={{ color: "var(--success-soft-fg)" }}
                >
                  ↗
                </span>
              </div>
              <div
                className="text-[11px] line-clamp-3 leading-snug whitespace-pre-wrap"
                style={{ color: "var(--fg-muted)" }}
              >
                {c.snippet}
              </div>
              <div
                className="text-[9px] font-mono mt-1 truncate opacity-80"
                style={{ color: "var(--success-soft-fg)" }}
              >
                {c.source_uri}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
