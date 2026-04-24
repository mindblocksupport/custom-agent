"use client";

import { useEffect, useMemo, useState } from "react";
import { ChatPanel } from "../components/ChatPanel";
import { CommandPalette } from "../components/CommandPalette";
import { CostDashboardDrawer } from "../components/CostDashboardDrawer";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { SettingsDrawer } from "../components/SettingsDrawer";
import { Sidebar } from "../components/Sidebar";
import { WorkspaceSettingsDrawer } from "../components/WorkspaceSettingsDrawer";
import { useMe } from "../hooks/useMe";
import { useSessions } from "../hooks/useSessions";
import { useSettings } from "../hooks/useSettings";
import { useSkills } from "../hooks/useSkills";
import { useTheme } from "../hooks/useTheme";
import { useWorkspaces } from "../hooks/useWorkspaces";

const SIDEBAR_KEY = "ca:sidebar_collapsed:v1";

function ConsoleApp() {
  const settingsHook = useSettings();
  const apiKey = settingsHook.settings.apiKey;
  const wsHook = useWorkspaces({ apiKey });
  const sessionsHook = useSessions({ apiKey, workspaceId: wsHook.activeId });
  const skillsHook = useSkills({ apiKey, workspaceId: wsHook.activeId });
  const meHook = useMe({ apiKey });
  const { toggle: toggleTheme } = useTheme();

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [wsSettingsOpen, setWsSettingsOpen] = useState(false);
  const [costOpen, setCostOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  const [health, setHealth] = useState<{ ok: boolean; label: string }>({
    ok: false, label: "checking",
  });

  // 持久化 sidebar 折叠状态
  useEffect(() => {
    try {
      const v = localStorage.getItem(SIDEBAR_KEY);
      if (v === "1") setCollapsed(true);
    } catch { /* ignore */ }
  }, []);
  const toggleCollapsed = () => {
    setCollapsed((c) => {
      try { localStorage.setItem(SIDEBAR_KEY, c ? "0" : "1"); } catch { /* ignore */ }
      return !c;
    });
  };

  // 全局 ⌘K / Ctrl+K 快捷键
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const isPalette =
        (e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K");
      if (isPalette) {
        e.preventDefault();
        setPaletteOpen((v) => !v);
        return;
      }
      // ⌘N 新会话
      if ((e.metaKey || e.ctrlKey) && (e.key === "n" || e.key === "N")) {
        // 不抢浏览器 Cmd+N (新窗口) — 改 Shift+Cmd+O 之类的
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const url = settingsHook.settings.baseUrl
      ? `${settingsHook.settings.baseUrl.replace(/\/$/, "")}/health/`
      : "/api/health";
    let mounted = true;
    const check = async () => {
      try {
        const r = await fetch(url);
        if (mounted) {
          setHealth(
            r.ok ? { ok: true, label: "在线" } : { ok: false, label: `${r.status}` },
          );
        }
      } catch {
        if (mounted) setHealth({ ok: false, label: "离线" });
      }
    };
    check();
    const t = setInterval(check, 5000);
    return () => { mounted = false; clearInterval(t); };
  }, [settingsHook.settings.baseUrl]);

  const activeWorkspace = useMemo(
    () => wsHook.workspaces.find((w) => w.id === wsHook.activeId) ?? null,
    [wsHook.workspaces, wsHook.activeId],
  );

  if (!sessionsHook.ready || !settingsHook.ready) {
    return (
      <div
        className="h-screen flex items-center justify-center"
        style={{ background: "var(--bg)", color: "var(--fg-muted)" }}
      >
        <div className="text-center">
          <div
            className="w-10 h-10 mx-auto mb-3 rounded-full flex items-center justify-center text-lg animate-pulse-soft"
            style={{
              background: "linear-gradient(135deg, var(--primary), var(--accent))",
              color: "white",
            }}
          >
            🤖
          </div>
          <div className="text-sm">Loading Custom Agent...</div>
        </div>
      </div>
    );
  }

  const activeSession =
    sessionsHook.sessions.find((s) => s.id === sessionsHook.activeId) ?? null;

  return (
    <div className="h-screen flex relative" style={{ background: "var(--bg)" }}>
      <Sidebar
        sessions={sessionsHook.sessions}
        activeId={sessionsHook.activeId}
        onSelect={sessionsHook.setActive}
        onNew={() => sessionsHook.create()}
        onDelete={sessionsHook.remove}
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenWorkspaceSettings={() => setWsSettingsOpen(true)}
        onOpenCostDashboard={() => setCostOpen(true)}
        status={health}
        apiKey={apiKey}
        workspaces={wsHook.workspaces}
        activeWorkspaceId={wsHook.activeId}
        onSelectWorkspace={wsHook.setActiveId}
        onCreateWorkspace={wsHook.create}
        skills={skillsHook.skills}
        onCreateSkill={skillsHook.create}
        onUpdateSkill={skillsHook.update}
        onRemoveSkill={skillsHook.remove}
        onInstallSkill={skillsHook.install}
        onRefreshSkills={skillsHook.refresh}
        collapsed={collapsed}
        onToggleCollapsed={toggleCollapsed}
        profile={meHook.profile}
      />

      <ChatPanel
        session={activeSession}
        settings={settingsHook.settings}
        workspaceId={wsHook.activeId}
        skills={skillsHook.skills}
        activeSkillId={skillsHook.activeId}
        onSelectSkill={skillsHook.setActiveId}
        onSessionStats={(cost, msgs) => {
          if (activeSession) sessionsHook.bumpStats(activeSession.id, msgs, cost);
        }}
        onTitleHint={(title) => {
          if (activeSession) sessionsHook.rename(activeSession.id, title);
        }}
        onModelChange={(model) =>
          settingsHook.update({ ...settingsHook.settings, model })
        }
      />

      <SettingsDrawer
        open={settingsOpen}
        settings={settingsHook.settings}
        onClose={() => setSettingsOpen(false)}
        onSave={(s) => settingsHook.update(s)}
      />

      <WorkspaceSettingsDrawer
        open={wsSettingsOpen}
        workspace={activeWorkspace}
        apiKey={apiKey}
        onClose={() => setWsSettingsOpen(false)}
        onUpdated={() => {
          wsHook.refresh();
        }}
      />

      <CostDashboardDrawer
        open={costOpen}
        onClose={() => setCostOpen(false)}
        workspace={activeWorkspace}
        sessions={sessionsHook.sessions}
        apiKey={apiKey}
      />

      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        sessions={sessionsHook.sessions}
        workspaces={wsHook.workspaces}
        skills={skillsHook.skills}
        activeWorkspaceId={wsHook.activeId}
        onSelectSession={sessionsHook.setActive}
        onSelectWorkspace={wsHook.setActiveId}
        onSelectSkill={skillsHook.setActiveId}
        onNewSession={() => sessionsHook.create()}
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenWorkspaceSettings={() => setWsSettingsOpen(true)}
        onOpenCostDashboard={() => setCostOpen(true)}
        onToggleTheme={toggleTheme}
        onToggleSidebar={toggleCollapsed}
      />
    </div>
  );
}

export default function Page() {
  return (
    <ErrorBoundary>
      <ConsoleApp />
    </ErrorBoundary>
  );
}
