/**
 * UI 全局服务: toast 通知 + 确认弹窗.
 * - toast.success/info/warn/error(...) 替代浏览器 alert
 * - confirm(...) 返回 Promise<boolean>, 替代浏览器 confirm
 */

"use client";

export type ToastKind = "success" | "info" | "warn" | "error";

export interface ToastItem {
  id: string;
  kind: ToastKind;
  title: string;
  description?: string;
  /** 毫秒, 0 = 不自动关闭 */
  duration?: number;
}

export interface ConfirmOptions {
  title: string;
  description?: string;
  confirmText?: string;
  cancelText?: string;
  /** danger 的样式 (红色按钮) */
  danger?: boolean;
}

type ToastListener = (items: ToastItem[]) => void;
type ConfirmListener = (
  opts: (ConfirmOptions & { resolve: (b: boolean) => void }) | null,
) => void;

class UiBus {
  private toasts: ToastItem[] = [];
  private toastListeners = new Set<ToastListener>();
  private confirmListener: ConfirmListener | null = null;

  // ---------- toast ----------
  subscribeToasts(fn: ToastListener): () => void {
    this.toastListeners.add(fn);
    fn(this.toasts);
    return () => this.toastListeners.delete(fn);
  }

  push(item: Omit<ToastItem, "id">): string {
    const id = `t_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    const t: ToastItem = { duration: 3500, ...item, id };
    this.toasts = [...this.toasts, t];
    this.notifyToasts();
    if (t.duration && t.duration > 0) {
      setTimeout(() => this.dismiss(id), t.duration);
    }
    return id;
  }

  dismiss(id: string) {
    this.toasts = this.toasts.filter((t) => t.id !== id);
    this.notifyToasts();
  }

  private notifyToasts() {
    for (const fn of this.toastListeners) fn(this.toasts);
  }

  // ---------- confirm ----------
  setConfirmListener(fn: ConfirmListener | null) {
    this.confirmListener = fn;
  }

  confirm(opts: ConfirmOptions): Promise<boolean> {
    return new Promise<boolean>((resolve) => {
      if (!this.confirmListener) {
        // fallback: window.confirm
        const ok =
          typeof window !== "undefined"
            ? window.confirm(`${opts.title}\n${opts.description ?? ""}`)
            : false;
        resolve(ok);
        return;
      }
      this.confirmListener({
        ...opts,
        resolve: (b) => {
          this.confirmListener?.(null);
          resolve(b);
        },
      });
    });
  }
}

export const ui = new UiBus();

// 便捷 helper
export const toast = {
  success: (title: string, description?: string, duration?: number) =>
    ui.push({ kind: "success", title, description, duration }),
  info: (title: string, description?: string, duration?: number) =>
    ui.push({ kind: "info", title, description, duration }),
  warn: (title: string, description?: string, duration?: number) =>
    ui.push({ kind: "warn", title, description, duration }),
  error: (title: string, description?: string, duration?: number) =>
    ui.push({ kind: "error", title, description, duration: duration ?? 6000 }),
  fromError: (e: unknown, fallback = "操作失败") => {
    const msg = e instanceof Error ? e.message : String(e ?? fallback);
    return ui.push({ kind: "error", title: fallback, description: msg, duration: 6000 });
  },
};

export const confirmDialog = (opts: ConfirmOptions) => ui.confirm(opts);
