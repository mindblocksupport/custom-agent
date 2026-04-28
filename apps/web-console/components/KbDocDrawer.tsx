"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { MeApi, type KbChunk } from "../lib/api/me";
import { toast } from "../lib/ui";
import type { KbDoc } from "../lib/types";

/**
 * KbDocDrawer 既支持「点 KB 文档行」打开 (传 doc 完整对象), 也支持
 * 「点 chat 引用」打开 (只有 docId, 自动 fetch 文档元 + chunks; 自动滚到 highlightChunkId).
 */
export function KbDocDrawer({
  doc,
  docId,
  highlightChunkId,
  apiKey,
  onClose,
}: {
  doc?: KbDoc | null;
  docId?: string | null;
  highlightChunkId?: string | null;
  apiKey: string;
  onClose: () => void;
}) {
  const [resolvedDoc, setResolvedDoc] = useState<KbDoc | null>(doc ?? null);
  const [chunks, setChunks] = useState<KbChunk[]>([]);
  const [loading, setLoading] = useState(false);
  const [truncated, setTruncated] = useState(false);
  const [filter, setFilter] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const targetId = doc?.id ?? docId ?? null;
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!targetId || !apiKey) return;
    setResolvedDoc(doc ?? null);
    setLoading(true);
    setChunks([]);
    setOpenId(highlightChunkId ?? null);

    const api = new MeApi(apiKey);
    const fetchChunks = api.kbDocChunks(targetId, 200);

    // 如果只有 docId, 没传 doc, 通过 /api/kb/docs/{id} 拿元信息
    const fetchDoc: Promise<KbDoc | null> = doc
      ? Promise.resolve(doc)
      : fetch(`/api/kb/docs/${targetId}`, {
          headers: { Authorization: `Bearer ${apiKey}` },
        })
          .then((r) => (r.ok ? r.json() : null))
          .catch(() => null);

    Promise.all([fetchChunks, fetchDoc])
      .then(([cl, d]) => {
        setChunks(cl.items);
        setTruncated(cl.truncated);
        if (d) setResolvedDoc(d);
      })
      .catch((e) => toast.fromError(e, "加载 chunks 失败"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetId, apiKey, highlightChunkId]);

  // chunks 加载完后, 滚到目标 chunk
  useLayoutEffect(() => {
    if (!highlightChunkId || chunks.length === 0) return;
    const el = containerRef.current?.querySelector<HTMLElement>(
      `[data-chunk-id="${highlightChunkId}"]`,
    );
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [chunks, highlightChunkId]);

  if (!targetId) return null;

  const d = resolvedDoc;
  const filtered = chunks.filter(
    (c) => !filter.trim() || c.content.toLowerCase().includes(filter.toLowerCase()),
  );

  return (
    <div
      className="fixed inset-0 z-40 flex justify-end"
      style={{ background: "var(--bg-overlay)" }}
      onClick={onClose}
    >
      <div
        className="responsive-drawer w-[36rem] max-w-full h-full flex flex-col animate-in"
        style={{
          background: "var(--bg-elev)",
          boxShadow: "var(--shadow-lg)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="px-4 py-3 border-b flex items-start justify-between gap-2"
          style={{ borderColor: "var(--border)" }}
        >
          <div className="min-w-0 flex-1">
            <div
              className="text-[10px] uppercase tracking-wide"
              style={{ color: "var(--fg-subtle)" }}
            >
              文档详情
              {highlightChunkId && (
                <span
                  className="ml-2 px-1 rounded normal-case"
                  style={{
                    background: "var(--accent-soft)",
                    color: "var(--accent-soft-fg)",
                  }}
                >
                  ← 引用反查
                </span>
              )}
            </div>
            <h2
              className="font-semibold text-base truncate"
              style={{ color: "var(--fg)" }}
              title={d?.source_uri}
            >
              📄 {d?.title ?? d?.source_uri?.split("/").pop() ?? targetId.slice(0, 8)}
            </h2>
            {d && (
              <div
                className="text-[10px] font-mono mt-0.5 flex gap-2 flex-wrap"
                style={{ color: "var(--fg-subtle)" }}
              >
                <span>{d.chunk_count} chunks</span>
                <span>v{d.current_version}</span>
                <span
                  className="px-1 rounded"
                  style={{
                    background: "var(--accent-soft)",
                    color: "var(--accent-soft-fg)",
                  }}
                >
                  {d.collection}
                </span>
                <span>{d.status}</span>
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

        <div
          className="px-4 py-2 border-b"
          style={{ borderColor: "var(--border)" }}
        >
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="🔎 在 chunks 内搜文字..."
            className="w-full px-2.5 py-1.5 rounded-md text-xs outline-none"
            style={{
              background: "var(--bg-elev-2)",
              color: "var(--fg)",
              border: "1px solid var(--border)",
            }}
          />
        </div>

        <div ref={containerRef} className="flex-1 overflow-y-auto p-4 space-y-2">
          {loading && (
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-20 skeleton rounded-md" />
              ))}
            </div>
          )}
          {!loading && filtered.length === 0 && (
            <div
              className="text-center py-8 text-sm"
              style={{ color: "var(--fg-subtle)" }}
            >
              {filter ? "无匹配 chunk" : "无 chunks"}
            </div>
          )}
          {filtered.map((c) => {
            const open = openId === c.id;
            const isHighlighted = highlightChunkId === c.id;
            const preview = c.content.length > 200 && !open
              ? highlight(c.content.slice(0, 200), filter) + "..."
              : highlight(c.content, filter);
            return (
              <div
                key={c.id}
                data-chunk-id={c.id}
                className="rounded-md p-2.5 transition cursor-pointer"
                style={{
                  background: open || isHighlighted
                    ? "var(--primary-soft)"
                    : "var(--bg-elev-2)",
                  border: `1px solid ${
                    isHighlighted
                      ? "var(--accent)"
                      : open
                        ? "var(--primary)"
                        : "var(--border)"
                  }`,
                  boxShadow: isHighlighted ? "var(--shadow-md)" : "none",
                }}
                onClick={() => setOpenId(open ? null : c.id)}
              >
                <div
                  className="flex items-center justify-between text-[10px] font-mono mb-1"
                  style={{ color: open ? "var(--primary-soft-fg)" : "var(--fg-subtle)" }}
                >
                  <span className="flex items-center gap-1">
                    {isHighlighted && <span>🎯</span>}
                    chunk #{c.chunk_seq} · v{c.doc_version}
                    {c.parent_id && " · 子块"}
                  </span>
                  <span className="flex gap-2">
                    {c.page != null && <span>p.{c.page}</span>}
                    {c.char_offset_start != null && (
                      <span>
                        offset {c.char_offset_start}
                        {c.char_offset_end != null && ` - ${c.char_offset_end}`}
                      </span>
                    )}
                  </span>
                </div>
                <div
                  className="text-xs whitespace-pre-wrap leading-relaxed break-words"
                  style={{
                    color: open ? "var(--primary-soft-fg)" : "var(--fg)",
                    maxHeight: open ? undefined : "8rem",
                    overflow: open ? undefined : "hidden",
                  }}
                  dangerouslySetInnerHTML={{ __html: preview }}
                />
                {!open && c.content.length > 200 && (
                  <div
                    className="text-[10px] mt-1"
                    style={{ color: "var(--fg-subtle)" }}
                  >
                    展开查看完整 ({c.content.length} 字符)
                  </div>
                )}
              </div>
            );
          })}

          {truncated && d && (
            <div
              className="text-[10px] text-center py-2 rounded-md"
              style={{
                background: "var(--warning-soft)",
                color: "var(--warning-soft-fg)",
              }}
            >
              ⚠️ 仅展示前 200 个 chunks (有更多, 用 doc.chunk_count = {d.chunk_count})
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function highlight(text: string, q: string): string {
  const esc = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  if (!q.trim()) return esc;
  const safeQ = q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(safeQ, "gi");
  return esc.replace(
    re,
    (m) =>
      `<mark style="background: var(--warning); color: var(--bg-elev); padding: 0 2px; border-radius: 2px;">${m}</mark>`,
  );
}
