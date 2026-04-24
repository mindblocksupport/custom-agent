"use client";

import React from "react";

/**
 * ErrorBoundary: React 未捕获异常兜底, 避免整页白屏.
 */
export class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { err: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { err: null };
  }
  static getDerivedStateFromError(err: Error) {
    return { err };
  }
  componentDidCatch(err: Error, info: React.ErrorInfo) {
    console.error("[ErrorBoundary]", err, info);
  }
  reset = () => this.setState({ err: null });

  render() {
    if (!this.state.err) return this.props.children;
    return (
      <div
        className="h-screen flex items-center justify-center p-6"
        style={{ background: "var(--bg)", color: "var(--fg)" }}
      >
        <div
          className="max-w-lg w-full rounded-xl p-5"
          style={{
            background: "var(--bg-elev)",
            border: "1px solid var(--danger)",
            boxShadow: "var(--shadow-lg)",
          }}
        >
          <div className="flex items-center gap-2 mb-3">
            <span className="text-2xl">💥</span>
            <h2 className="font-semibold text-base">界面崩了一下</h2>
          </div>
          <p
            className="text-sm leading-relaxed mb-3"
            style={{ color: "var(--fg-muted)" }}
          >
            某个组件抛了未捕获的异常。后端数据不受影响, 你可以尝试恢复。
          </p>
          <pre
            className="text-xs p-2.5 rounded-md overflow-auto max-h-48 font-mono"
            style={{
              background: "var(--danger-soft)",
              color: "var(--danger-soft-fg)",
              border: "1px solid var(--danger)",
            }}
          >
            {this.state.err.message}
            {"\n"}
            {this.state.err.stack?.split("\n").slice(0, 6).join("\n")}
          </pre>
          <div className="flex gap-2 mt-4">
            <button
              onClick={this.reset}
              className="flex-1 py-2 rounded-md text-sm"
              style={{
                border: "1px solid var(--border)",
                color: "var(--fg)",
              }}
            >
              🔄 重试渲染
            </button>
            <button
              onClick={() => window.location.reload()}
              className="flex-1 py-2 rounded-md text-sm font-semibold text-white"
              style={{ background: "var(--primary)" }}
            >
              刷新页面
            </button>
          </div>
        </div>
      </div>
    );
  }
}
