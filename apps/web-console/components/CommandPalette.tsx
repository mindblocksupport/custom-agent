"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { MeApi, type SessionSearchHit } from "../lib/api/me";
import type { Session, Skill, Workspace } from "../lib/types";

export interface CommandAction {
  id: string;
  group: string;
  label: string;
  hint?: string;
  icon?: string;
  keywords?: string;
  shortcut?: string;
  perform: () => void | Promise<void>;
}

export function CommandPalette({
  open,
  onClose,
  sessions,
  workspaces,
  skills,
  activeWorkspaceId,
  apiKey,
  onSelectSession,
  onSelectWorkspace,
  onSelectSkill,
  onNewSession,
  onOpenSettings,
  onOpenWorkspaceSettings,
  onOpenCostDashboard,
  onToggleTheme,
  onToggleSidebar,
}: {
  open: boolean;
  onClose: () => void;
  sessions: Session[];
  workspaces: Workspace[];
  skills: Skill[];
  activeWorkspaceId: string | null;
  apiKey: string;
  onSelectSession: (id: string) => void;
  onSelectWorkspace: (id: string) => void;
  onSelectSkill: (id: string | null) => void;
  onNewSession: () => void;
  onOpenSettings: () => void;
  onOpenWorkspaceSettings: () => void;
  onOpenCostDashboard: () => void;
  onToggleTheme: () => void;
  onToggleSidebar: () => void;
}) {
  const [q, setQ] = useState("");
  const [hover, setHover] = useState(0);
  const [remoteHits, setRemoteHits] = useState<SessionSearchHit[]>([]);
  const [searching, setSearching] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<number | null>(null);

  useEffect(() => {
    if (open) {
      setQ("");
      setHover(0);
      setRemoteHits([]);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  // 全文搜后端 (debounce 250ms, 仅 query 长度 ≥ 2)
  useEffect(() => {
    if (debounceRef.current) {
      window.clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
    const query = q.trim();
    if (query.length < 2 || !apiKey) {
      setRemoteHits([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    debounceRef.current = window.setTimeout(async () => {
      try {
        const r = await new MeApi(apiKey).searchSessions(query, {
          workspaceId: activeWorkspaceId, limit: 8,
        });
        setRemoteHits(r.items);
      } catch {
        setRemoteHits([]);
      } finally {
        setSearching(false);
      }
    }, 250);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
  }, [q, apiKey, activeWorkspaceId]);

  const actions: CommandAction[] = useMemo(() => {
    const out: CommandAction[] = [];
    out.push(
      {
        id: "act:new",
        group: "操作",
        icon: "＋",
        label: "新建会话",
        hint: "在当前 workspace 下",
        shortcut: "⌘N",
        perform: () => {
          onClose();
          onNewSession();
        },
      },
      {
        id: "act:cost",
        group: "操作",
        icon: "📊",
        label: "打开成本看板",
        perform: () => {
          onClose();
          onOpenCostDashboard();
        },
      },
      {
        id: "act:wssettings",
        group: "操作",
        icon: "⚙️",
        label: "打开工作空间设置",
        perform: () => {
          onClose();
          onOpenWorkspaceSettings();
        },
      },
      {
        id: "act:settings",
        group: "操作",
        icon: "🔧",
        label: "打开全局设置",
        perform: () => {
          onClose();
          onOpenSettings();
        },
      },
      {
        id: "act:theme",
        group: "操作",
        icon: "🌓",
        label: "切换主题 (亮 / 深)",
        perform: () => {
          onClose();
          onToggleTheme();
        },
      },
      {
        id: "act:sidebar",
        group: "操作",
        icon: "◀▶",
        label: "折叠 / 展开 侧栏",
        perform: () => {
          onClose();
          onToggleSidebar();
        },
      },
    );

    workspaces.forEach((w) =>
      out.push({
        id: `ws:${w.id}`,
        group: "工作空间",
        icon: "🗂️",
        label: w.name,
        keywords: `workspace ${w.description}`,
        hint: w.id === activeWorkspaceId ? "当前" : undefined,
        perform: () => {
          onClose();
          onSelectWorkspace(w.id);
        },
      }),
    );

    out.push({
      id: "skill:none",
      group: "技能",
      icon: "💬",
      label: "通用对话 (取消 skill)",
      perform: () => {
        onClose();
        onSelectSkill(null);
      },
    });
    skills.forEach((s) =>
      out.push({
        id: `skill:${s.id}`,
        group: "技能",
        icon: "🧩",
        label: `${s.name} v${s.version}`,
        keywords: `${s.description} ${s.tags.join(" ")}`,
        hint:
          s.workspace_id === activeWorkspaceId ? "本空间" : "市场",
        perform: () => {
          onClose();
          onSelectSkill(s.id);
        },
      }),
    );

    // 全文搜命中 (后端) — 高亮 snippet
    remoteHits.forEach((h) => {
      out.push({
        id: `hit:${h.session.id}`,
        group: "搜索命中",
        icon: "🔎",
        label: h.session.title,
        hint: h.snippet ? truncate(h.snippet, 40) : `${h.session.message_count} 条`,
        perform: () => {
          onClose();
          onSelectSession(h.session.id);
        },
      });
    });

    sessions.slice(0, 30).forEach((s) =>
      out.push({
        id: `sess:${s.id}`,
        group: "会话",
        icon: "💬",
        label: s.title,
        hint: `${s.messageCount} 条 · $${s.totalCostUsd.toFixed(4)}`,
        perform: () => {
          onClose();
          onSelectSession(s.id);
        },
      }),
    );
    return out;
  }, [
    workspaces, skills, sessions, activeWorkspaceId, remoteHits,
    onClose, onSelectSession, onSelectWorkspace, onSelectSkill,
    onNewSession, onOpenSettings, onOpenCostDashboard, onOpenWorkspaceSettings,
    onToggleTheme, onToggleSidebar,
  ]);

  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase();
    if (!query) return actions;
    return actions.filter((a) => {
      const hay = `${a.label} ${a.keywords ?? ""} ${a.group}`.toLowerCase();
      // 简化模糊匹配: 每个空格分词必须命中
      return query.split(/\s+/).every((tok) => hay.includes(tok));
    });
  }, [q, actions]);

  // 分组渲染顺序 (搜索命中放最前)
  const grouped = useMemo(() => {
    const order = ["搜索命中", "操作", "工作空间", "技能", "会话"];
    const map = new Map<string, CommandAction[]>();
    filtered.forEach((a) => {
      if (!map.has(a.group)) map.set(a.group, []);
      map.get(a.group)!.push(a);
    });
    return order
      .filter((g) => map.has(g))
      .map((g) => ({ group: g, items: map.get(g)! }));
  }, [filtered]);

  const flat = useMemo(() => grouped.flatMap((g) => g.items), [grouped]);

  // 键盘
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setHover((h) => Math.min(flat.length - 1, h + 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setHover((h) => Math.max(0, h - 1));
      } else if (e.key === "Enter") {
        e.preventDefault();
        const a = flat[hover];
        if (a) a.perform();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, hover, flat, onClose]);

  // hover 重置
  useEffect(() => {
    setHover(0);
  }, [q]);

  // hover 跟随滚动
  useEffect(() => {
    if (!listRef.current) return;
    const el = listRef.current.querySelector<HTMLElement>(`[data-idx="${hover}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [hover]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[150] flex items-start justify-center pt-[12vh] px-4"
      style={{ background: "var(--bg-overlay)" }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl rounded-xl overflow-hidden animate-modal"
        style={{
          background: "var(--bg-elev)",
          border: "1px solid var(--border)",
          boxShadow: "var(--shadow-lg)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="flex items-center gap-2 px-4 py-2.5 border-b"
          style={{ borderColor: "var(--border)" }}
        >
          <span className="text-base" style={{ color: "var(--fg-subtle)" }}>
            ⌘
          </span>
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="跳转 / 搜索 / 命令... (会话名 / 消息内容 / 技能 / 设置)"
            className="flex-1 bg-transparent outline-none text-sm py-1"
            style={{ color: "var(--fg)" }}
          />
          {searching && (
            <span
              className="text-[10px] animate-pulse-soft"
              style={{ color: "var(--fg-subtle)" }}
            >
              搜索中
            </span>
          )}
          <span
            className="text-[10px] font-mono px-1.5 py-0.5 rounded"
            style={{
              background: "var(--bg-elev-2)",
              color: "var(--fg-subtle)",
            }}
          >
            esc
          </span>
        </div>

        <div
          ref={listRef}
          className="max-h-[50vh] overflow-y-auto"
        >
          {grouped.length === 0 && (
            <div
              className="px-4 py-8 text-center text-xs"
              style={{ color: "var(--fg-subtle)" }}
            >
              无匹配项
            </div>
          )}
          {grouped.map((g) => {
            const startIdx = flat.indexOf(g.items[0]!);
            return (
              <div key={g.group}>
                <div
                  className="px-3 py-1.5 text-[10px] uppercase tracking-wide"
                  style={{
                    color: "var(--fg-subtle)",
                    background: "var(--bg-elev-2)",
                  }}
                >
                  {g.group}
                </div>
                {g.items.map((a, i) => {
                  const idx = startIdx + i;
                  const active = idx === hover;
                  return (
                    <button
                      key={a.id}
                      data-idx={idx}
                      onMouseEnter={() => setHover(idx)}
                      onClick={() => a.perform()}
                      className="w-full text-left px-3 py-2 flex items-center gap-2 transition"
                      style={{
                        background: active ? "var(--primary-soft)" : "transparent",
                        color: active ? "var(--primary-soft-fg)" : "var(--fg)",
                      }}
                    >
                      <span className="text-sm w-5 text-center shrink-0">
                        {a.icon ?? "•"}
                      </span>
                      <span className="flex-1 truncate text-sm">{a.label}</span>
                      {a.hint && (
                        <span
                          className="text-[10px] font-mono shrink-0 truncate"
                          style={{
                            color: active
                              ? "var(--primary-soft-fg)"
                              : "var(--fg-subtle)",
                          }}
                        >
                          {a.hint}
                        </span>
                      )}
                      {a.shortcut && (
                        <span
                          className="text-[10px] font-mono px-1.5 py-0.5 rounded shrink-0"
                          style={{
                            background: active
                              ? "rgba(255,255,255,0.4)"
                              : "var(--bg-elev-2)",
                            color: active
                              ? "var(--primary-soft-fg)"
                              : "var(--fg-subtle)",
                          }}
                        >
                          {a.shortcut}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>

        <div
          className="px-3 py-1.5 border-t flex items-center justify-between text-[10px] font-mono"
          style={{
            borderColor: "var(--border)",
            color: "var(--fg-subtle)",
          }}
        >
          <span>
            <Kbd>↑</Kbd> <Kbd>↓</Kbd> 选择 · <Kbd>↵</Kbd> 执行 · <Kbd>esc</Kbd> 关闭
          </span>
          <span>{flat.length} 项</span>
        </div>
      </div>
    </div>
  );
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n) + "..." : s;
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="inline-block px-1 rounded"
      style={{
        background: "var(--bg-elev-2)",
        color: "var(--fg-muted)",
      }}
    >
      {children}
    </span>
  );
}
