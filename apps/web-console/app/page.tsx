"use client";

import { useEffect, useState } from "react";
import { ChatPanel } from "../components/ChatPanel";
import { SettingsDrawer } from "../components/SettingsDrawer";
import { Sidebar } from "../components/Sidebar";
import { useSessions } from "../hooks/useSessions";
import { useSettings } from "../hooks/useSettings";

export default function Page() {
  const sessionsHook = useSessions();
  const settingsHook = useSettings();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [health, setHealth] = useState<{ ok: boolean; label: string }>({
    ok: false,
    label: "checking",
  });

  // 健康检查 (5s 一次)
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
            r.ok ? { ok: true, label: "✓ ok" } : { ok: false, label: `HTTP ${r.status}` },
          );
        }
      } catch {
        if (mounted) setHealth({ ok: false, label: "down" });
      }
    };
    check();
    const t = setInterval(check, 5000);
    return () => {
      mounted = false;
      clearInterval(t);
    };
  }, [settingsHook.settings.baseUrl]);

  if (!sessionsHook.ready || !settingsHook.ready) {
    return <div className="p-8 text-sm text-neutral-500">Loading...</div>;
  }

  const activeSession =
    sessionsHook.sessions.find((s) => s.id === sessionsHook.activeId) ?? null;

  return (
    <div className="h-screen flex">
      <Sidebar
        sessions={sessionsHook.sessions}
        activeId={sessionsHook.activeId}
        onSelect={sessionsHook.setActive}
        onNew={() => sessionsHook.create()}
        onDelete={sessionsHook.remove}
        onOpenSettings={() => setSettingsOpen(true)}
        status={health}
      />

      <ChatPanel
        session={activeSession}
        settings={settingsHook.settings}
        onSessionStats={(cost, msgs) => {
          if (activeSession) sessionsHook.bumpStats(activeSession.id, msgs, cost);
        }}
        onTitleHint={(title) => {
          if (activeSession) sessionsHook.rename(activeSession.id, title);
        }}
      />

      <SettingsDrawer
        open={settingsOpen}
        settings={settingsHook.settings}
        onClose={() => setSettingsOpen(false)}
        onSave={(s) => settingsHook.update(s)}
      />
    </div>
  );
}
