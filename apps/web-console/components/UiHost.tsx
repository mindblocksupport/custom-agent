"use client";

/**
 * UiHost: 全局挂在 layout 顶部, 渲染 toast 容器 + confirm 模态.
 * 通过 lib/ui.ts 的 EventBus 订阅状态.
 */

import { useEffect, useState } from "react";
import {
  ui,
  type ConfirmOptions,
  type ToastItem,
  type ToastKind,
} from "../lib/ui";

const KIND_STYLE: Record<ToastKind, { icon: string; bg: string; fg: string; border: string }> = {
  success: {
    icon: "✓",
    bg: "var(--success-soft)",
    fg: "var(--success-soft-fg)",
    border: "var(--success)",
  },
  info: {
    icon: "ℹ",
    bg: "var(--info-soft)",
    fg: "var(--info-soft-fg)",
    border: "var(--primary)",
  },
  warn: {
    icon: "⚠",
    bg: "var(--warning-soft)",
    fg: "var(--warning-soft-fg)",
    border: "var(--warning)",
  },
  error: {
    icon: "✕",
    bg: "var(--danger-soft)",
    fg: "var(--danger-soft-fg)",
    border: "var(--danger)",
  },
};

export function UiHost() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [confirmState, setConfirmState] = useState<
    (ConfirmOptions & { resolve: (b: boolean) => void }) | null
  >(null);

  useEffect(() => {
    const off = ui.subscribeToasts(setToasts);
    ui.setConfirmListener((s) => setConfirmState(s));
    return () => {
      off();
      ui.setConfirmListener(null);
    };
  }, []);

  // ESC 关闭 confirm
  useEffect(() => {
    if (!confirmState) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") confirmState.resolve(false);
      if (e.key === "Enter") confirmState.resolve(true);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [confirmState]);

  return (
    <>
      {/* Toast 堆 */}
      <div
        className="fixed top-4 right-4 z-[200] flex flex-col gap-2 pointer-events-none"
        style={{ maxWidth: "min(90vw, 380px)" }}
      >
        {toasts.map((t) => {
          const s = KIND_STYLE[t.kind];
          return (
            <div
              key={t.id}
              className="animate-toast pointer-events-auto rounded-lg px-3 py-2.5 text-sm shadow-lg"
              style={{
                background: s.bg,
                color: s.fg,
                borderLeft: `3px solid ${s.border}`,
                boxShadow: "var(--shadow-md)",
              }}
            >
              <div className="flex items-start gap-2.5">
                <span className="text-base leading-none mt-0.5">{s.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-[13px] leading-snug">
                    {t.title}
                  </div>
                  {t.description && (
                    <div className="text-[12px] mt-1 leading-relaxed opacity-90 break-words">
                      {t.description}
                    </div>
                  )}
                </div>
                <button
                  onClick={() => ui.dismiss(t.id)}
                  className="opacity-50 hover:opacity-100 text-xs leading-none -mr-1"
                  aria-label="关闭"
                >
                  ✕
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Confirm 模态 */}
      {confirmState && (
        <div
          className="fixed inset-0 z-[210] flex items-center justify-center px-4"
          style={{ background: "var(--bg-overlay)" }}
          onClick={() => confirmState.resolve(false)}
        >
          <div
            className="animate-modal w-full max-w-sm rounded-xl p-5"
            style={{
              background: "var(--bg-elev)",
              boxShadow: "var(--shadow-lg)",
              border: "1px solid var(--border)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="font-semibold text-base mb-1.5" style={{ color: "var(--fg)" }}>
              {confirmState.title}
            </div>
            {confirmState.description && (
              <div
                className="text-sm leading-relaxed mb-4"
                style={{ color: "var(--fg-muted)" }}
              >
                {confirmState.description}
              </div>
            )}
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => confirmState.resolve(false)}
                className="px-3.5 py-1.5 rounded-md text-sm font-medium transition"
                style={{
                  color: "var(--fg-muted)",
                  background: "transparent",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-hover)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                {confirmState.cancelText ?? "取消"}
              </button>
              <button
                onClick={() => confirmState.resolve(true)}
                autoFocus
                className="px-3.5 py-1.5 rounded-md text-sm font-semibold text-white transition"
                style={{
                  background: confirmState.danger ? "var(--danger)" : "var(--primary)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.opacity = "0.85";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.opacity = "1";
                }}
              >
                {confirmState.confirmText ?? "确定"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
