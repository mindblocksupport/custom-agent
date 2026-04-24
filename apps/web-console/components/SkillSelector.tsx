"use client";

import { useState } from "react";
import type { Skill } from "../lib/types";

export function SkillSelector({
  skills,
  activeId,
  currentWorkspaceId,
  onSelect,
}: {
  skills: Skill[];
  activeId: string | null;
  currentWorkspaceId: string | null;
  onSelect: (id: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const active = skills.find((s) => s.id === activeId);

  const own = skills.filter((s) => s.workspace_id === currentWorkspaceId);
  const market = skills.filter(
    (s) => s.workspace_id !== currentWorkspaceId && s.visibility === "public",
  );

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs transition"
        style={{
          background: active ? "var(--accent-soft)" : "var(--bg-elev-2)",
          color: active ? "var(--accent-soft-fg)" : "var(--fg)",
          border: `1px solid ${active ? "var(--accent)" : "var(--border)"}`,
        }}
        onMouseEnter={(e) => {
          if (!active) e.currentTarget.style.borderColor = "var(--accent)";
        }}
        onMouseLeave={(e) => {
          if (!active) e.currentTarget.style.borderColor = "var(--border)";
        }}
        title="选择技能 (Skill) — 复用配方: prompt + 工具 + 默认 KB"
      >
        <span>🧩</span>
        <span className="font-medium">
          {active ? `${active.name} v${active.version}` : "通用对话"}
        </span>
        {active && active.workspace_id !== currentWorkspaceId && (
          <span
            className="text-[9px] px-1 rounded"
            style={{
              background: "var(--warning-soft)",
              color: "var(--warning-soft-fg)",
            }}
          >
            市场
          </span>
        )}
        <span style={{ color: "var(--fg-subtle)" }}>▾</span>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div
            className="absolute z-20 mt-1 right-0 w-80 rounded-lg max-h-[28rem] overflow-y-auto animate-in"
            style={{
              background: "var(--bg-elev)",
              border: "1px solid var(--border)",
              boxShadow: "var(--shadow-lg)",
            }}
          >
            {/* 通用对话 */}
            <button
              onClick={() => {
                onSelect(null);
                setOpen(false);
              }}
              className="w-full text-left px-3 py-2 text-xs border-b transition"
              style={{
                background: activeId === null ? "var(--primary-soft)" : "transparent",
                color: activeId === null ? "var(--primary-soft-fg)" : "var(--fg)",
                borderColor: "var(--border)",
              }}
              onMouseEnter={(e) => {
                if (activeId !== null)
                  e.currentTarget.style.background = "var(--surface-hover)";
              }}
              onMouseLeave={(e) => {
                if (activeId !== null)
                  e.currentTarget.style.background = "transparent";
              }}
            >
              <div className="font-medium flex items-center gap-1">
                通用对话
                {activeId === null && <span className="ml-auto">✓</span>}
              </div>
              <div
                className="text-[10px] mt-0.5"
                style={{
                  color:
                    activeId === null
                      ? "var(--primary-soft-fg)"
                      : "var(--fg-subtle)",
                }}
              >
                不绑定 skill, 默认 system prompt
              </div>
            </button>

            <SkillSection
              title="本工作空间"
              icon="🗂️"
              skills={own}
              activeId={activeId}
              onSelect={(id) => {
                onSelect(id);
                setOpen(false);
              }}
              emptyText="此 workspace 暂无 skill"
            />

            {market.length > 0 && (
              <SkillSection
                title="Skill 市场 (公开复用)"
                icon="🏪"
                skills={market}
                activeId={activeId}
                showWorkspaceBadge
                onSelect={(id) => {
                  onSelect(id);
                  setOpen(false);
                }}
              />
            )}
          </div>
        </>
      )}
    </div>
  );
}

function SkillSection({
  title,
  icon,
  skills,
  activeId,
  emptyText,
  showWorkspaceBadge,
  onSelect,
}: {
  title: string;
  icon: string;
  skills: Skill[];
  activeId: string | null;
  emptyText?: string;
  showWorkspaceBadge?: boolean;
  onSelect: (id: string) => void;
}) {
  return (
    <div>
      <div
        className="px-3 py-1.5 text-[10px] uppercase tracking-wide border-b"
        style={{
          color: "var(--fg-subtle)",
          background: "var(--bg-elev-2)",
          borderColor: "var(--border)",
        }}
      >
        {icon} {title}
      </div>
      {skills.length === 0 && emptyText && (
        <div className="px-3 py-2 text-xs" style={{ color: "var(--fg-subtle)" }}>
          {emptyText}
        </div>
      )}
      {skills.map((s) => {
        const isActive = s.id === activeId;
        return (
          <button
            key={s.id}
            onClick={() => onSelect(s.id)}
            className="w-full text-left px-3 py-2 text-xs transition"
            style={{
              background: isActive ? "var(--primary-soft)" : "transparent",
              color: isActive ? "var(--primary-soft-fg)" : "var(--fg)",
            }}
            onMouseEnter={(e) => {
              if (!isActive)
                e.currentTarget.style.background = "var(--surface-hover)";
            }}
            onMouseLeave={(e) => {
              if (!isActive)
                e.currentTarget.style.background = "transparent";
            }}
          >
            <div className="font-medium flex items-center gap-1.5 flex-wrap">
              {s.name}
              <span className="text-[9px]" style={{ color: "var(--fg-subtle)" }}>
                v{s.version}
              </span>
              {showWorkspaceBadge && (
                <span
                  className="text-[9px] px-1 rounded"
                  style={{
                    background: "var(--warning-soft)",
                    color: "var(--warning-soft-fg)",
                  }}
                  title={`来自 workspace: ${s.workspace_id.slice(0, 8)}...`}
                >
                  public
                </span>
              )}
              {isActive && <span className="ml-auto">✓</span>}
            </div>
            {s.description && (
              <div
                className="text-[10px] mt-0.5"
                style={{
                  color: isActive
                    ? "var(--primary-soft-fg)"
                    : "var(--fg-subtle)",
                }}
              >
                {s.description}
              </div>
            )}
            {s.tags.length > 0 && (
              <div className="flex gap-1 mt-1 flex-wrap">
                {s.tags.slice(0, 3).map((t) => (
                  <span
                    key={t}
                    className="text-[9px] px-1 rounded"
                    style={{
                      background: "var(--bg-elev-2)",
                      color: "var(--fg-muted)",
                    }}
                  >
                    {t}
                  </span>
                ))}
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
}
