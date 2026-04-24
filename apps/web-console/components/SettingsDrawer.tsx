"use client";

import { useEffect, useState } from "react";
import { toast } from "../lib/ui";
import type { Settings } from "../lib/types";

const COMMON_MODELS = [
  "deepseek/deepseek-chat",
  "deepseek/deepseek-reasoner",
  "claude-sonnet-4-5-20250929",
  "claude-opus-4-7",
  "gpt-4o-mini",
  "gpt-5-mini",
  "qwen/qwen-max-latest",
  "gemini/gemini-2.0-flash-exp",
];

export function SettingsDrawer({
  open,
  settings,
  onClose,
  onSave,
}: {
  open: boolean;
  settings: Settings;
  onClose: () => void;
  onSave: (s: Settings) => void;
}) {
  const [draft, setDraft] = useState<Settings>(settings);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    setDraft(settings);
  }, [settings, open]);

  if (!open) return null;

  const testConnection = async () => {
    setTesting(true);
    try {
      const url = draft.baseUrl
        ? `${draft.baseUrl.replace(/\/$/, "")}/health/`
        : "/api/health";
      const r = await fetch(url, {
        headers: { Authorization: `Bearer ${draft.apiKey}` },
      });
      if (r.ok) {
        toast.success("连接成功", url);
      } else {
        toast.error(`HTTP ${r.status}`, url);
      }
    } catch (e) {
      toast.fromError(e, "连接失败");
    } finally {
      setTesting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      style={{ background: "var(--bg-overlay)" }}
      onClick={onClose}
    >
      <div
        className="w-96 max-w-full h-full flex flex-col animate-in"
        style={{
          background: "var(--bg-elev)",
          boxShadow: "var(--shadow-lg)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="p-4 border-b flex items-center justify-between"
          style={{ borderColor: "var(--border)" }}
        >
          <h2 className="font-semibold" style={{ color: "var(--fg)" }}>
            ⚙ 设置
          </h2>
          <button
            onClick={onClose}
            className="text-xl leading-none"
            style={{ color: "var(--fg-subtle)" }}
          >
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          <Field label="API Key" hint="后端鉴权 token; 默认 dev-key-change-me">
            <input
              type="password"
              value={draft.apiKey}
              onChange={(e) => setDraft({ ...draft, apiKey: e.target.value })}
              className="w-full px-2.5 py-1.5 rounded-md text-sm outline-none font-mono"
              style={{
                background: "var(--bg-elev-2)",
                color: "var(--fg)",
                border: "1px solid var(--border)",
              }}
            />
          </Field>

          <Field
            label="Backend URL"
            hint="留空 = 走当前域 /api/chat 代理 (推荐); 否则填 http://host:8000"
          >
            <input
              type="text"
              value={draft.baseUrl}
              onChange={(e) => setDraft({ ...draft, baseUrl: e.target.value })}
              placeholder="http://localhost:8000 (可空)"
              className="w-full px-2.5 py-1.5 rounded-md text-sm outline-none font-mono"
              style={{
                background: "var(--bg-elev-2)",
                color: "var(--fg)",
                border: "1px solid var(--border)",
              }}
            />
          </Field>

          <Field label="默认模型" hint="LiteLLM 兼容 ID; auto = 智能路由">
            <input
              type="text"
              value={draft.model}
              onChange={(e) => setDraft({ ...draft, model: e.target.value })}
              list="model-list"
              className="w-full px-2.5 py-1.5 rounded-md text-sm outline-none font-mono"
              style={{
                background: "var(--bg-elev-2)",
                color: "var(--fg)",
                border: "1px solid var(--border)",
              }}
            />
            <datalist id="model-list">
              <option value="auto" />
              {COMMON_MODELS.map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
          </Field>

          <button
            onClick={testConnection}
            disabled={testing}
            className="w-full py-1.5 rounded-md text-xs font-medium transition"
            style={{
              background: "var(--bg-elev-2)",
              color: "var(--fg)",
              border: "1px solid var(--border)",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--primary)")}
            onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--border)")}
          >
            {testing ? "测试中..." : "🧪 测试连接"}
          </button>

          <div
            className="text-[11px] leading-relaxed pt-3 border-t"
            style={{ color: "var(--fg-subtle)", borderColor: "var(--border)" }}
          >
            🔒 设置仅存于浏览器 localStorage, 不会上传; 切换设备需重新填。
          </div>
        </div>

        <div
          className="p-4 border-t flex gap-2"
          style={{ borderColor: "var(--border)" }}
        >
          <button
            onClick={onClose}
            className="flex-1 py-2 text-sm rounded-md transition"
            style={{
              color: "var(--fg-muted)",
              border: "1px solid var(--border)",
            }}
          >
            取消
          </button>
          <button
            onClick={() => {
              onSave(draft);
              toast.success("设置已保存");
              onClose();
            }}
            className="flex-1 py-2 text-sm rounded-md font-semibold text-white"
            style={{ background: "var(--primary)" }}
          >
            保存
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label
        className="text-xs font-semibold block mb-1"
        style={{ color: "var(--fg-muted)" }}
      >
        {label}
      </label>
      {children}
      {hint && (
        <div
          className="text-[11px] mt-1 leading-snug"
          style={{ color: "var(--fg-subtle)" }}
        >
          {hint}
        </div>
      )}
    </div>
  );
}
