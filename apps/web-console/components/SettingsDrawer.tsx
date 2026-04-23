"use client";

import { useEffect, useState } from "react";
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

  useEffect(() => {
    setDraft(settings);
  }, [settings, open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/30"
      onClick={onClose}
    >
      <div
        className="w-96 bg-white h-full shadow-xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-4 border-b border-neutral-200 flex items-center justify-between">
          <h2 className="font-semibold">设置</h2>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-700 text-xl leading-none"
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
              className="w-full px-3 py-1.5 border border-neutral-300 rounded-md text-sm focus:outline-none focus:border-blue-500"
            />
          </Field>

          <Field
            label="Backend URL"
            hint="留空 = 走当前域 /api/chat 代理(推荐); 否则填 http://host:8000"
          >
            <input
              type="text"
              value={draft.baseUrl}
              onChange={(e) => setDraft({ ...draft, baseUrl: e.target.value })}
              placeholder="http://localhost:8000 (可空)"
              className="w-full px-3 py-1.5 border border-neutral-300 rounded-md text-sm focus:outline-none focus:border-blue-500"
            />
          </Field>

          <Field label="模型" hint="LiteLLM 兼容 ID">
            <input
              type="text"
              value={draft.model}
              onChange={(e) => setDraft({ ...draft, model: e.target.value })}
              list="model-list"
              className="w-full px-3 py-1.5 border border-neutral-300 rounded-md text-sm focus:outline-none focus:border-blue-500"
            />
            <datalist id="model-list">
              {COMMON_MODELS.map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
          </Field>

          <div className="pt-2 text-[11px] text-neutral-500 leading-relaxed">
            设置仅存于浏览器 localStorage,**不会上传**;切换设备需重新填。
          </div>
        </div>

        <div className="p-4 border-t border-neutral-200 flex gap-2">
          <button
            onClick={onClose}
            className="flex-1 py-2 text-sm rounded-md border border-neutral-300 hover:bg-neutral-50"
          >
            取消
          </button>
          <button
            onClick={() => {
              onSave(draft);
              onClose();
            }}
            className="flex-1 py-2 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700"
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
      <label className="text-xs font-semibold text-neutral-700">{label}</label>
      {children}
      {hint && (
        <div className="text-[11px] text-neutral-500 mt-1 leading-snug">
          {hint}
        </div>
      )}
    </div>
  );
}
