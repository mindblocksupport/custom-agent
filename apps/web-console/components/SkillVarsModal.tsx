"use client";

import { useEffect, useState } from "react";
import { applyVars } from "../lib/templating";

/**
 * 弹层让用户填 skill.system_prompt 中的 {{ var }}.
 * - 表单 ↔ 实时预览替换后的 system_prompt
 * - 保存后由调用方持久化 (use useSkillVars hook)
 */
export function SkillVarsModal({
  open,
  onClose,
  skillName,
  systemPromptTemplate,
  required,
  values,
  onSave,
}: {
  open: boolean;
  onClose: () => void;
  skillName: string;
  systemPromptTemplate: string;
  required: string[];
  values: Record<string, string>;
  onSave: (next: Record<string, string>) => void;
}) {
  const [draft, setDraft] = useState<Record<string, string>>(values);

  useEffect(() => {
    if (open) setDraft(values);
  }, [open, values]);

  // ESC 关闭
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const allFilled = required.every((v) => (draft[v] ?? "").trim().length > 0);
  const previewText = applyVars(systemPromptTemplate, draft);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      style={{ background: "var(--bg-overlay)" }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg max-h-[88vh] overflow-y-auto rounded-xl p-5 animate-modal"
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
            填 Skill 模板变量
          </div>
          <h3 className="font-semibold text-base">
            🪄 {skillName}
          </h3>
        </div>

        <div className="space-y-2 text-sm mb-4">
          {required.map((v) => (
            <div key={v}>
              <label
                className="text-[11px] font-mono mb-1 block"
                style={{ color: "var(--fg-muted)" }}
              >
                {`{{ ${v} }}`}
              </label>
              <input
                autoFocus={v === required[0]}
                value={draft[v] ?? ""}
                onChange={(e) => setDraft({ ...draft, [v]: e.target.value })}
                placeholder={`填一个 ${v}...`}
                className="w-full px-2.5 py-1.5 rounded-md text-sm outline-none"
                style={{
                  background: "var(--bg-elev-2)",
                  color: "var(--fg)",
                  border: "1px solid var(--border)",
                }}
              />
            </div>
          ))}
        </div>

        {/* 预览 */}
        <div className="mb-4">
          <div
            className="text-[10px] uppercase tracking-wide mb-1"
            style={{ color: "var(--fg-subtle)" }}
          >
            预览 system_prompt
          </div>
          <pre
            className="text-[11px] font-mono whitespace-pre-wrap p-2 rounded max-h-48 overflow-y-auto leading-snug"
            style={{
              background: "var(--bg-elev-2)",
              color: "var(--fg-muted)",
              border: "1px solid var(--border)",
            }}
          >
            {previewText.length > 0 ? previewText : "(skill 无 system_prompt)"}
          </pre>
        </div>

        <div
          className="text-[10px] mb-3"
          style={{ color: "var(--fg-subtle)" }}
        >
          ℹ️ 值仅保存在浏览器 localStorage (per session+skill); 删除会话或换 skill 自动失效。
        </div>

        <div className="flex justify-end gap-2">
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
            onClick={() => onSave(draft)}
            disabled={!allFilled}
            className="px-4 py-1.5 rounded-md text-sm font-semibold text-white disabled:opacity-40"
            style={{ background: "var(--primary)" }}
            title={allFilled ? "保存并关闭" : "全部变量都填了才能保存"}
          >
            保存
          </button>
        </div>
      </div>
    </div>
  );
}
