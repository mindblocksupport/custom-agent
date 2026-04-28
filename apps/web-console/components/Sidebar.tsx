"use client";

import { useMemo, useState } from "react";
import { useTheme } from "../hooks/useTheme";
import { confirmDialog, toast } from "../lib/ui";
import { KbPanel } from "./KbPanel";
import { SessionTagsModal } from "./SessionTagsModal";
import { SkillsPanel } from "./SkillsPanel";
import { WorkspaceSwitcher } from "./WorkspaceSwitcher";
import type { MeProfile, MyBudget } from "../lib/api/me";
import type { Session, Skill, Workspace } from "../lib/types";
import type { SkillCreatePayload, SkillUpdatePayload } from "../lib/api/skills";

type Tab = "sessions" | "kb" | "skills";

export function Sidebar({
  sessions,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onOpenSettings,
  onOpenWorkspaceSettings,
  onOpenCostDashboard,
  status,
  apiKey,
  workspaces,
  activeWorkspaceId,
  onSelectWorkspace,
  onCreateWorkspace,
  skills,
  onCreateSkill,
  onUpdateSkill,
  onRemoveSkill,
  onInstallSkill,
  onRefreshSkills,
  collapsed,
  onToggleCollapsed,
  profile,
  isMobile,
  allTags,
  tagFilter,
  onTagFilter,
  onSetTags,
  myBudget,
}: {
  sessions: Session[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  allTags: string[];
  tagFilter: string | null;
  onTagFilter: (t: string | null) => void;
  onSetTags: (id: string, tags: string[]) => Promise<void>;
  myBudget: MyBudget | null;
  onOpenSettings: () => void;
  onOpenWorkspaceSettings: () => void;
  onOpenCostDashboard: () => void;
  status: { ok: boolean; label: string };
  apiKey: string;
  workspaces: Workspace[];
  activeWorkspaceId: string | null;
  onSelectWorkspace: (id: string) => void;
  onCreateWorkspace: (name: string) => Promise<void>;
  skills: Skill[];
  onCreateSkill: (payload: SkillCreatePayload) => Promise<Skill>;
  onUpdateSkill: (sid: string, payload: SkillUpdatePayload) => Promise<Skill>;
  onRemoveSkill: (sid: string) => Promise<void>;
  onInstallSkill: (sourceSkillId: string) => Promise<Skill>;
  onRefreshSkills: () => Promise<void>;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  profile: MeProfile | null;
  isMobile: boolean;
}) {
  const [tab, setTab] = useState<Tab>("sessions");
  const [search, setSearch] = useState("");
  const { theme, toggle: toggleTheme } = useTheme();
  const [editingTagsFor, setEditingTagsFor] = useState<Session | null>(null);

  const filteredSessions = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return sessions;
    return sessions.filter((s) => s.title.toLowerCase().includes(q));
  }, [sessions, search]);

  // 移动端 collapsed = 完全隐藏 (左侧用 chat 头部的 ☰ 按钮唤起)
  if (collapsed && isMobile) {
    return null;
  }

  // 桌面 collapsed: 只显示 icon-rail
  if (collapsed) {
    return (
      <aside
        className="shrink-0 flex flex-col items-center py-3 gap-2 border-r"
        style={{
          width: "var(--sidebar-w-collapsed)",
          background: "var(--bg-elev)",
          borderColor: "var(--border)",
        }}
      >
        <RailButton icon="🤖" title="展开侧栏" onClick={onToggleCollapsed} />
        <div className="flex-1" />
        <RailButton
          icon="💬"
          title="会话"
          active={tab === "sessions"}
          onClick={() => {
            setTab("sessions");
            onToggleCollapsed();
          }}
        />
        <RailButton
          icon="📚"
          title="知识库"
          active={tab === "kb"}
          onClick={() => {
            setTab("kb");
            onToggleCollapsed();
          }}
        />
        <RailButton
          icon="🧩"
          title="技能"
          active={tab === "skills"}
          onClick={() => {
            setTab("skills");
            onToggleCollapsed();
          }}
        />
        <RailButton
          icon="📊"
          title="成本"
          onClick={onOpenCostDashboard}
        />
        <div className="flex-1" />
        <RailButton
          icon={theme === "dark" ? "☀️" : "🌙"}
          title="切换主题"
          onClick={toggleTheme}
        />
        <RailButton icon="⚙️" title="设置" onClick={onOpenSettings} />
      </aside>
    );
  }

  return (
    <>
      {isMobile && !collapsed && (
        <div className="mobile-sidebar-overlay" onClick={onToggleCollapsed} />
      )}
      <aside
        className={`shrink-0 border-r flex flex-col ${isMobile ? "mobile-sidebar is-open" : ""}`}
        style={{
          width: "var(--sidebar-w)",
          background: "var(--bg-elev)",
          borderColor: "var(--border)",
        }}
      >
      {/* Header */}
      <div
        className="px-3 py-3 border-b space-y-2.5"
        style={{ borderColor: "var(--border)" }}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center text-sm shrink-0"
              style={{
                background: "linear-gradient(135deg, var(--primary), var(--accent))",
                color: "white",
              }}
            >
              🤖
            </div>
            <h1
              className="font-semibold text-sm truncate"
              style={{ color: "var(--fg)" }}
            >
              Custom Agent
            </h1>
          </div>
          <div className="flex items-center gap-1">
            <span
              className="text-[10px] px-1.5 py-0.5 rounded-full font-mono inline-flex items-center gap-1"
              style={{
                background: status.ok ? "var(--success-soft)" : "var(--danger-soft)",
                color: status.ok ? "var(--success-soft-fg)" : "var(--danger-soft-fg)",
              }}
              title="后端健康状态"
            >
              <span
                className="w-1.5 h-1.5 rounded-full"
                style={{
                  background: status.ok ? "var(--success)" : "var(--danger)",
                }}
              />
              {status.label}
            </span>
            <button
              onClick={onToggleCollapsed}
              className="p-1 rounded text-xs transition"
              style={{ color: "var(--fg-subtle)" }}
              title="收起侧栏"
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-hover)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              ◀
            </button>
          </div>
        </div>

        <WorkspaceSwitcher
          workspaces={workspaces}
          activeId={activeWorkspaceId}
          onSelect={onSelectWorkspace}
          onCreate={onCreateWorkspace}
          onOpenSettings={onOpenWorkspaceSettings}
        />

        {myBudget && myBudget.has_limit && <MyBudgetBar budget={myBudget} />}

        {/* Tab switcher (segmented) */}
        <div
          className="flex gap-0.5 rounded-lg p-0.5"
          style={{ background: "var(--bg-elev-2)" }}
        >
          <TabBtn active={tab === "sessions"} onClick={() => setTab("sessions")}>
            💬 <span className="ml-0.5">会话</span>
            <Badge>{sessions.length}</Badge>
          </TabBtn>
          <TabBtn active={tab === "kb"} onClick={() => setTab("kb")}>
            📚 <span className="ml-0.5">知识库</span>
          </TabBtn>
          <TabBtn active={tab === "skills"} onClick={() => setTab("skills")}>
            🧩 <span className="ml-0.5">技能</span>
            <Badge>
              {skills.filter((s) => s.workspace_id === activeWorkspaceId).length}
            </Badge>
          </TabBtn>
        </div>

        {tab === "sessions" && (
          <>
            <button
              onClick={onNew}
              className="w-full text-sm py-1.5 px-3 rounded-lg font-medium transition flex items-center justify-center gap-1.5"
              style={{
                background: "var(--primary)",
                color: "var(--fg-on-primary)",
                boxShadow: "var(--shadow-sm)",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--primary-hover)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "var(--primary)")}
            >
              <span className="text-base leading-none">＋</span> 新会话
            </button>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="🔎 搜索会话..."
              className="w-full px-2.5 py-1.5 rounded-md text-xs outline-none transition"
              style={{
                background: "var(--bg-elev-2)",
                color: "var(--fg)",
                border: "1px solid transparent",
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = "var(--primary)")}
              onBlur={(e) => (e.currentTarget.style.borderColor = "transparent")}
            />
          </>
        )}
      </div>

      {/* Tab body */}
      {tab === "sessions" && (
        <div className="flex-1 overflow-y-auto py-2">
          {/* Tag 筛选 chips */}
          {allTags.length > 0 && (
            <div
              className="px-2 pb-2 flex gap-1 flex-wrap border-b mb-1"
              style={{ borderColor: "var(--border)" }}
            >
              <button
                onClick={() => onTagFilter(null)}
                className="text-[10px] px-1.5 py-0.5 rounded transition"
                style={{
                  background: tagFilter === null ? "var(--primary)" : "var(--bg-elev-2)",
                  color: tagFilter === null ? "var(--fg-on-primary)" : "var(--fg-muted)",
                }}
              >
                全部
              </button>
              {allTags.map((t) => (
                <button
                  key={t}
                  onClick={() => onTagFilter(tagFilter === t ? null : t)}
                  className="text-[10px] px-1.5 py-0.5 rounded font-mono transition"
                  style={{
                    background:
                      tagFilter === t ? "var(--accent)" : "var(--bg-elev-2)",
                    color:
                      tagFilter === t ? "white" : "var(--fg-muted)",
                  }}
                >
                  #{t}
                </button>
              ))}
            </div>
          )}

          {filteredSessions.length === 0 && (
            <EmptyState
              icon="💬"
              title={
                search
                  ? "无匹配会话"
                  : tagFilter
                    ? `「#${tagFilter}」下无会话`
                    : "此工作空间无会话"
              }
              hint={search ? "换个关键字试试" : tagFilter ? "试切回 全部" : "点上方「+ 新会话」开始"}
            />
          )}
          {filteredSessions.map((s) => (
            <SessionRow
              key={s.id}
              session={s}
              active={s.id === activeId}
              onSelect={() => onSelect(s.id)}
              onEditTags={() => setEditingTagsFor(s)}
              onDelete={async () => {
                const ok = await confirmDialog({
                  title: `删除会话「${s.title}」?`,
                  description: "对话历史将被永久移除, 不可恢复。",
                  confirmText: "删除",
                  danger: true,
                });
                if (ok) {
                  try {
                    onDelete(s.id);
                    toast.success("已删除会话");
                  } catch (e) {
                    toast.fromError(e, "删除失败");
                  }
                }
              }}
            />
          ))}
        </div>
      )}
      {tab === "kb" && <KbPanel apiKey={apiKey} workspaceId={activeWorkspaceId} />}
      {tab === "skills" && (
        <SkillsPanel
          skills={skills}
          currentWorkspaceId={activeWorkspaceId}
          apiKey={apiKey}
          onCreate={onCreateSkill}
          onUpdate={onUpdateSkill}
          onRemove={onRemoveSkill}
          onInstall={onInstallSkill}
          onRefresh={onRefreshSkills}
        />
      )}

      {/* Footer */}
      <div
        className="border-t"
        style={{ borderColor: "var(--border)" }}
      >
        {profile && (
          <div
            className="px-3 py-2 flex items-center gap-2 border-b"
            style={{ borderColor: "var(--border)" }}
            title={`tenant: ${profile.tenant_id}\nactor: ${profile.actor_id}\nprincipals: ${profile.principals.join(", ")}`}
          >
            <div
              className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-semibold shrink-0"
              style={{
                background: "var(--primary-soft)",
                color: "var(--primary-soft-fg)",
              }}
            >
              {(profile.actor_id || "U").slice(0, 2).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <div
                className="text-[11px] font-medium truncate"
                style={{ color: "var(--fg)" }}
              >
                {profile.actor_id}
              </div>
              <div
                className="text-[9px] font-mono truncate"
                style={{ color: "var(--fg-subtle)" }}
              >
                {profile.workspace_count} ws · {profile.skill_count_visible} skill
              </div>
            </div>
          </div>
        )}
        <div className="p-2 flex items-center gap-1">
          <FooterBtn
            icon="📊"
            label="成本"
            onClick={onOpenCostDashboard}
            title="本工作空间累计成本与会话用量"
          />
          <FooterBtn
            icon={theme === "dark" ? "☀️" : "🌙"}
            label={theme === "dark" ? "亮色" : "深色"}
            onClick={toggleTheme}
            title="切换主题"
          />
          <FooterBtn
            icon="⚙️"
            label="设置"
            onClick={onOpenSettings}
            title="API Key / Backend / 默认模型"
          />
        </div>
      </div>
      </aside>

      {editingTagsFor && (
        <SessionTagsModal
          open={!!editingTagsFor}
          onClose={() => setEditingTagsFor(null)}
          sessionTitle={editingTagsFor.title}
          initial={editingTagsFor.tags ?? []}
          knownTags={allTags}
          onSave={async (tags) => {
            try {
              await onSetTags(editingTagsFor.id, tags);
              toast.success("标签已更新");
            } catch (e) {
              toast.fromError(e, "保存标签失败");
            }
          }}
        />
      )}
    </>
  );
}

function TabBtn({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className="flex-1 text-[11px] py-1.5 rounded-md transition flex items-center justify-center gap-0.5 font-medium"
      style={{
        background: active ? "var(--bg-elev)" : "transparent",
        color: active ? "var(--fg)" : "var(--fg-muted)",
        boxShadow: active ? "var(--shadow-sm)" : "none",
      }}
    >
      {children}
    </button>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="text-[9px] px-1 rounded-full font-mono"
      style={{
        background: "var(--surface-pressed)",
        color: "var(--fg-muted)",
        marginLeft: 2,
      }}
    >
      {children}
    </span>
  );
}

function FooterBtn({
  icon,
  label,
  onClick,
  title,
}: {
  icon: string;
  label: string;
  onClick: () => void;
  title?: string;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="flex-1 text-[11px] py-1.5 px-1.5 rounded-md transition flex items-center justify-center gap-1"
      style={{ color: "var(--fg-muted)" }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = "var(--surface-hover)";
        e.currentTarget.style.color = "var(--fg)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "transparent";
        e.currentTarget.style.color = "var(--fg-muted)";
      }}
    >
      <span>{icon}</span>
      <span>{label}</span>
    </button>
  );
}

function RailButton({
  icon,
  title,
  active,
  onClick,
}: {
  icon: string;
  title: string;
  active?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="w-9 h-9 rounded-lg flex items-center justify-center text-base transition"
      style={{
        background: active ? "var(--primary-soft)" : "transparent",
        color: active ? "var(--primary-soft-fg)" : "var(--fg-muted)",
      }}
      onMouseEnter={(e) => {
        if (!active) e.currentTarget.style.background = "var(--surface-hover)";
      }}
      onMouseLeave={(e) => {
        if (!active) e.currentTarget.style.background = "transparent";
      }}
    >
      {icon}
    </button>
  );
}

function MyBudgetBar({ budget }: { budget: MyBudget }) {
  const dayPct =
    budget.budget_daily_usd && budget.budget_daily_usd > 0
      ? (budget.today_cost_usd / budget.budget_daily_usd) * 100
      : null;
  const monthPct =
    budget.budget_monthly_usd && budget.budget_monthly_usd > 0
      ? (budget.month_cost_usd / budget.budget_monthly_usd) * 100
      : null;
  const worstPct = Math.max(dayPct ?? 0, monthPct ?? 0);
  const danger = worstPct >= 80;
  const critical = worstPct >= 100;
  const fg = critical
    ? "var(--danger-soft-fg)"
    : danger
      ? "var(--warning-soft-fg)"
      : "var(--fg-muted)";
  const bg = critical
    ? "var(--danger-soft)"
    : danger
      ? "var(--warning-soft)"
      : "var(--bg-elev-2)";

  return (
    <div
      className="px-2 py-1 rounded-md text-[10px] font-mono flex items-center gap-1"
      style={{ background: bg, color: fg }}
      title={`你 (this user) 在本工作空间的预算 — 实时, 5min 自动刷`}
    >
      <span>💵</span>
      {dayPct !== null && (
        <span>
          日 ${budget.today_cost_usd.toFixed(4)}/${budget.budget_daily_usd!.toFixed(2)} (
          {dayPct.toFixed(0)}%)
        </span>
      )}
      {dayPct !== null && monthPct !== null && <span>·</span>}
      {monthPct !== null && (
        <span>
          月 ${budget.month_cost_usd.toFixed(4)}/${budget.budget_monthly_usd!.toFixed(2)} (
          {monthPct.toFixed(0)}%)
        </span>
      )}
    </div>
  );
}

function EmptyState({
  icon,
  title,
  hint,
}: {
  icon: string;
  title: string;
  hint?: string;
}) {
  return (
    <div className="px-3 py-8 text-center animate-in">
      <div className="text-3xl opacity-40 mb-2">{icon}</div>
      <div className="text-xs font-medium" style={{ color: "var(--fg-muted)" }}>
        {title}
      </div>
      {hint && (
        <div className="text-[11px] mt-1" style={{ color: "var(--fg-subtle)" }}>
          {hint}
        </div>
      )}
    </div>
  );
}

function SessionRow({
  session,
  active,
  onSelect,
  onDelete,
  onEditTags,
}: {
  session: Session;
  active: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onEditTags: () => void;
}) {
  return (
    <div
      onClick={onSelect}
      className="group mx-2 px-2.5 py-2 rounded-lg cursor-pointer transition"
      style={{
        background: active ? "var(--primary-soft)" : "transparent",
        color: active ? "var(--primary-soft-fg)" : "var(--fg)",
      }}
      onMouseEnter={(e) => {
        if (!active) e.currentTarget.style.background = "var(--surface-hover)";
      }}
      onMouseLeave={(e) => {
        if (!active) e.currentTarget.style.background = "transparent";
      }}
    >
      <div className="flex items-center gap-2">
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium truncate">{session.title}</div>
          <div
            className="text-[10px] mt-0.5 flex gap-2 font-mono"
            style={{ color: active ? "var(--primary-soft-fg)" : "var(--fg-subtle)" }}
          >
            <span>{session.messageCount} 条</span>
            {session.totalCostUsd > 0 && (
              <span title="累计成本">${session.totalCostUsd.toFixed(4)}</span>
            )}
          </div>
          {session.tags && session.tags.length > 0 && (
            <div className="flex gap-1 mt-1 flex-wrap">
              {session.tags.slice(0, 4).map((t) => (
                <span
                  key={t}
                  className="text-[9px] px-1 rounded font-mono"
                  style={{
                    background: active
                      ? "rgba(255,255,255,0.45)"
                      : "var(--accent-soft)",
                    color: active
                      ? "var(--primary-soft-fg)"
                      : "var(--accent-soft-fg)",
                  }}
                >
                  #{t}
                </span>
              ))}
              {session.tags.length > 4 && (
                <span className="text-[9px]" style={{ color: "var(--fg-subtle)" }}>
                  +{session.tags.length - 4}
                </span>
              )}
            </div>
          )}
        </div>
        <div className="flex flex-col gap-0.5 opacity-0 group-hover:opacity-100 transition">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onEditTags();
            }}
            className="text-xs px-1 transition"
            style={{ color: "var(--fg-subtle)" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "var(--accent)")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "var(--fg-subtle)")}
            title="编辑标签"
          >
            🏷
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            className="text-xs px-1 transition"
            style={{ color: "var(--fg-subtle)" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "var(--danger)")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "var(--fg-subtle)")}
            title="删除"
          >
            ✕
          </button>
        </div>
      </div>
    </div>
  );
}
