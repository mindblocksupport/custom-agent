"use client";

import { useEffect, useMemo, useState } from "react";

/** 给一个 session 编辑 tags. chip 加/删 + 自动补全 (从已有 tags 抽). */
export function SessionTagsModal({
  open,
  onClose,
  sessionTitle,
  initial,
  knownTags,
  onSave,
}: {
  open: boolean;
  onClose: () => void;
  sessionTitle: string;
  initial: string[];
  knownTags: string[];
  onSave: (tags: string[]) => void | Promise<void>;
}) {
  const [draft, setDraft] = useState<string[]>(initial);
  const [input, setInput] = useState("");

  useEffect(() => {
    if (open) {
      setDraft([...initial]);
      setInput("");
    }
  }, [open, initial]);

  // ESC 关闭
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const suggestions = useMemo(() => {
    const inputN = input.trim().toLowerCase();
    if (!inputN) return [];
    return knownTags
      .filter((t) => !draft.includes(t) && t.includes(inputN))
      .slice(0, 6);
  }, [input, knownTags, draft]);

  if (!open) return null;

  const add = (raw: string) => {
    const t = raw.trim().toLowerCase().replace(/\s+/g, "_");
    if (!t) return;
    if (draft.includes(t)) {
      setInput("");
      return;
    }
    setDraft([...draft, t]);
    setInput("");
  };

  const remove = (t: string) => setDraft(draft.filter((x) => x !== t));

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      style={{ background: "var(--bg-overlay)" }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-xl p-5 animate-modal"
        style={{
          background: "var(--bg-elev)",
          color: "var(--fg)",
          boxShadow: "var(--shadow-lg)",
          border: "1px solid var(--border)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3">
          <div
            className="text-[10px] uppercase tracking-wide"
            style={{ color: "var(--fg-subtle)" }}
          >
            会话标签
          </div>
          <h3 className="font-semibold text-base truncate" title={sessionTitle}>
            🏷 {sessionTitle}
          </h3>
        </div>

        <div className="flex flex-wrap gap-1.5 mb-2 min-h-[1.5rem]">
          {draft.length === 0 && (
            <span className="text-xs italic" style={{ color: "var(--fg-subtle)" }}>
              暂无标签
            </span>
          )}
          {draft.map((t) => (
            <span
              key={t}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-mono"
              style={{
                background: "var(--accent-soft)",
                color: "var(--accent-soft-fg)",
                border: "1px solid var(--accent)",
              }}
            >
              {t}
              <button
                type="button"
                onClick={() => remove(t)}
                className="opacity-60 hover:opacity-100"
                title="移除"
              >
                ✕
              </button>
            </span>
          ))}
        </div>

        <div className="relative">
          <input
            autoFocus
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                add(input);
              } else if (e.key === "Backspace" && !input && draft.length > 0) {
                remove(draft[draft.length - 1]!);
              }
            }}
            placeholder="新 tag (Enter 添加, Backspace 删尾)"
            className="w-full px-2.5 py-1.5 rounded-md text-sm outline-none font-mono"
            style={{
              background: "var(--bg-elev-2)",
              color: "var(--fg)",
              border: "1px solid var(--border)",
            }}
          />
          {suggestions.length > 0 && (
            <div
              className="absolute z-10 left-0 right-0 mt-1 rounded-md overflow-hidden"
              style={{
                background: "var(--bg-elev)",
                border: "1px solid var(--border)",
                boxShadow: "var(--shadow-md)",
              }}
            >
              {suggestions.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => add(s)}
                  className="w-full text-left text-xs px-2.5 py-1.5 transition"
                  style={{ color: "var(--fg)" }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-hover)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  <span className="opacity-60">+ </span>
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>

        <div
          className="text-[10px] mt-2"
          style={{ color: "var(--fg-subtle)" }}
        >
          ℹ️ tag 自动小写, 空格变 _; 点 sidebar 顶部 chip 可按 tag 筛会话
        </div>

        <div className="flex justify-end gap-2 mt-4">
          <button
            onClick={onClose}
            className="px-3.5 py-1.5 rounded-md text-sm transition"
            style={{ color: "var(--fg-muted)" }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-hover)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            取消
          </button>
          <button
            onClick={async () => {
              await onSave(draft);
              onClose();
            }}
            className="px-4 py-1.5 rounded-md text-sm font-semibold text-white"
            style={{ background: "var(--primary)" }}
          >
            保存
          </button>
        </div>
      </div>
    </div>
  );
}
