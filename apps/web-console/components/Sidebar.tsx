"use client";

import type { Session } from "../lib/types";

export function Sidebar({
  sessions,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onOpenSettings,
  status,
}: {
  sessions: Session[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onOpenSettings: () => void;
  status: { ok: boolean; label: string };
}) {
  return (
    <aside className="w-64 shrink-0 border-r border-neutral-200 bg-neutral-50 flex flex-col">
      {/* Header */}
      <div className="p-3 border-b border-neutral-200">
        <div className="flex items-center justify-between mb-2">
          <h1 className="font-semibold text-sm">Custom Agent</h1>
          <span
            className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${
              status.ok
                ? "bg-green-100 text-green-700"
                : "bg-red-100 text-red-700"
            }`}
            title="Backend health"
          >
            {status.label}
          </span>
        </div>
        <button
          onClick={onNew}
          className="w-full text-sm py-1.5 px-3 rounded-md bg-neutral-900 text-white hover:bg-neutral-700 transition"
        >
          + 新会话
        </button>
      </div>

      {/* Sessions */}
      <div className="flex-1 overflow-y-auto py-2">
        {sessions.length === 0 && (
          <div className="text-xs text-neutral-400 px-3 py-4">无会话</div>
        )}
        {sessions.map((s) => (
          <SessionRow
            key={s.id}
            session={s}
            active={s.id === activeId}
            onSelect={() => onSelect(s.id)}
            onDelete={() => {
              if (confirm(`删除「${s.title}」?`)) onDelete(s.id);
            }}
          />
        ))}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-neutral-200">
        <button
          onClick={onOpenSettings}
          className="w-full text-xs py-1.5 px-2 rounded-md text-neutral-600 hover:bg-neutral-200 transition text-left"
        >
          ⚙ 设置
        </button>
      </div>
    </aside>
  );
}

function SessionRow({
  session,
  active,
  onSelect,
  onDelete,
}: {
  session: Session;
  active: boolean;
  onSelect: () => void;
  onDelete: () => void;
}) {
  return (
    <div
      onClick={onSelect}
      className={`group mx-2 px-2 py-1.5 rounded-md cursor-pointer transition ${
        active ? "bg-neutral-200" : "hover:bg-neutral-100"
      }`}
    >
      <div className="flex items-center gap-2">
        <div className="flex-1 min-w-0">
          <div className="text-sm truncate">{session.title}</div>
          <div className="text-[10px] text-neutral-500 mt-0.5 flex gap-2">
            <span>{session.messageCount} 条</span>
            {session.totalCostUsd > 0 && (
              <span title="累计成本">
                ${session.totalCostUsd.toFixed(4)}
              </span>
            )}
          </div>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="opacity-0 group-hover:opacity-100 text-neutral-400 hover:text-red-500 text-xs px-1"
          title="删除"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
