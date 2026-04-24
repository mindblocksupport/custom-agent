"use client";

import { useEffect, useState } from "react";

interface SystemStatus {
  backendOk: boolean;
  toolCount: number;
  kbDocCount: number;
  ragMcpReady: boolean;
}

export function StatusBar({ apiKey }: { apiKey: string }) {
  const [s, setS] = useState<SystemStatus>({
    backendOk: false,
    toolCount: 0,
    kbDocCount: 0,
    ragMcpReady: false,
  });

  useEffect(() => {
    let mounted = true;
    const fetchAll = async () => {
      const next: SystemStatus = {
        backendOk: false, toolCount: 0, kbDocCount: 0, ragMcpReady: false,
      };
      try {
        const h = await fetch("/api/health");
        next.backendOk = h.ok;
      } catch { /* ignore */ }
      try {
        const r = await fetch("/api/kb/docs", {
          headers: { Authorization: `Bearer ${apiKey}` },
        });
        if (r.ok) {
          const j = await r.json();
          next.kbDocCount = (j.items as unknown[])?.length ?? 0;
        }
      } catch { /* ignore */ }
      next.toolCount = next.backendOk ? 4 : 0;
      next.ragMcpReady = next.backendOk;
      if (mounted) setS(next);
    };
    fetchAll();
    const t = setInterval(fetchAll, 10000);
    return () => { mounted = false; clearInterval(t); };
  }, [apiKey]);

  const Pill = ({
    ok, icon, label, hint,
  }: { ok: boolean; icon: string; label: string; hint?: string }) => (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] transition"
      style={{
        background: ok ? "var(--success-soft)" : "var(--bg-elev-2)",
        color: ok ? "var(--success-soft-fg)" : "var(--fg-subtle)",
      }}
      title={hint ?? label}
    >
      <span>{icon}</span>
      <span>{label}</span>
    </span>
  );

  return (
    <div className="hidden md:flex items-center gap-1 flex-wrap">
      <Pill
        ok={s.backendOk}
        icon={s.backendOk ? "●" : "○"}
        label={s.backendOk ? "在线" : "离线"}
        hint="后端 api-server 健康状态 (10 秒刷新)"
      />
      <Pill
        ok={s.toolCount > 0}
        icon="🔧"
        label={`${s.toolCount}`}
        hint="agent 当前可调用的工具数 (time/calc/web-search/search_kb)"
      />
      <Pill
        ok={s.kbDocCount > 0}
        icon="📚"
        label={`${s.kbDocCount}`}
        hint="知识库当前已 ingest 的文档数"
      />
      <Pill
        ok={s.ragMcpReady}
        icon="🔒"
        label="ACL"
        hint="访问控制 (per-call JWT 注入), LLM 看不到 token"
      />
    </div>
  );
}
