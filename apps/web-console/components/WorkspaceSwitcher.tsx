"use client";

import { useState } from "react";
import { toast } from "../lib/ui";
import type { Workspace } from "../lib/types";

export function WorkspaceSwitcher({
  workspaces,
  activeId,
  onSelect,
  onCreate,
  onOpenSettings,
}: {
  workspaces: Workspace[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onCreate: (name: string) => Promise<void>;
  onOpenSettings?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const active = workspaces.find((w) => w.id === activeId);

  return (
    <div className="relative">
      <div className="flex gap-1">
        <button
          onClick={() => setOpen(!open)}
          className="flex-1 flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-lg text-xs transition"
          style={{
            background: "var(--bg-elev-2)",
            color: "var(--fg)",
            border: "1px solid var(--border)",
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.borderColor = "var(--primary)")
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.borderColor = "var(--border)")
          }
          title="切换工作空间 (Workspace)"
        >
          <span className="flex items-center gap-1.5 truncate">
            <span>🗂️</span>
            <span className="font-medium truncate">
              {active?.name ?? "(无 workspace)"}
            </span>
          </span>
          <span style={{ color: "var(--fg-subtle)" }}>▾</span>
        </button>
        {onOpenSettings && active && (
          <button
            onClick={onOpenSettings}
            className="px-2 rounded-lg text-xs transition"
            style={{
              color: "var(--fg-subtle)",
              border: "1px solid var(--border)",
              background: "var(--bg-elev-2)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "var(--primary)";
              e.currentTarget.style.borderColor = "var(--primary)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "var(--fg-subtle)";
              e.currentTarget.style.borderColor = "var(--border)";
            }}
            title="工作空间设置 (成员/预算/默认模型)"
          >
            ⚙
          </button>
        )}
      </div>

      {open && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => {
              setOpen(false);
              setCreating(false);
            }}
          />
          <div
            className="absolute z-20 mt-1 w-full rounded-lg max-h-72 overflow-y-auto animate-in"
            style={{
              background: "var(--bg-elev)",
              border: "1px solid var(--border)",
              boxShadow: "var(--shadow-lg)",
            }}
          >
            <div
              className="px-3 py-1.5 text-[10px] uppercase tracking-wide border-b"
              style={{
                color: "var(--fg-subtle)",
                borderColor: "var(--border)",
              }}
            >
              工作空间
            </div>
            {workspaces.length === 0 && (
              <div className="px-3 py-2 text-xs" style={{ color: "var(--fg-subtle)" }}>
                无
              </div>
            )}
            {workspaces.map((w) => {
              const isActive = w.id === activeId;
              return (
                <button
                  key={w.id}
                  onClick={() => {
                    onSelect(w.id);
                    setOpen(false);
                  }}
                  className="w-full text-left px-3 py-2 text-xs transition flex items-start gap-2"
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
                  title={w.description}
                >
                  <span className="text-sm leading-none mt-0.5">🗂️</span>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate">{w.name}</div>
                    {w.description && (
                      <div
                        className="text-[10px] truncate mt-0.5"
                        style={{
                          color: isActive
                            ? "var(--primary-soft-fg)"
                            : "var(--fg-subtle)",
                        }}
                      >
                        {w.description}
                      </div>
                    )}
                  </div>
                  {isActive && <span className="text-[10px]">✓</span>}
                </button>
              );
            })}
            <div className="border-t" style={{ borderColor: "var(--border)" }}>
              {creating ? (
                <div className="p-2 flex gap-1">
                  <input
                    autoFocus
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    onKeyDown={async (e) => {
                      if (e.key === "Enter") {
                        const n = newName.trim();
                        if (!n) return;
                        try {
                          await onCreate(n);
                          toast.success("工作空间已创建", n);
                          setCreating(false);
                          setNewName("");
                          setOpen(false);
                        } catch (err) {
                          toast.fromError(err, "创建失败");
                        }
                      }
                      if (e.key === "Escape") {
                        setCreating(false);
                        setNewName("");
                      }
                    }}
                    placeholder="名称, Enter 确认"
                    className="flex-1 px-2 py-1 rounded text-xs outline-none"
                    style={{
                      background: "var(--bg-elev-2)",
                      color: "var(--fg)",
                      border: "1px solid var(--primary)",
                    }}
                  />
                  <button
                    onClick={() => {
                      setCreating(false);
                      setNewName("");
                    }}
                    className="px-2 text-xs"
                    style={{ color: "var(--fg-subtle)" }}
                  >
                    ✕
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setCreating(true)}
                  className="w-full text-left px-3 py-2 text-xs transition"
                  style={{ color: "var(--primary)" }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.background = "var(--primary-soft)")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.background = "transparent")
                  }
                >
                  + 新建工作空间
                </button>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
