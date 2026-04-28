"use client";

/**
 * useSessions: 多浏览器/多终端可见 (Day 8 完成).
 *
 * 后端 /v1/sessions 是 source of truth, localStorage 离线 fallback.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { SessionsApi } from "../lib/api/sessions";
import { loadSessions, saveSessions } from "../lib/storage";
import type { Session } from "../lib/types";

function newLocalSession(): Session {
  const ts = Date.now();
  return {
    id: crypto.randomUUID(),
    title: "新会话",
    createdAt: ts,
    updatedAt: ts,
    messageCount: 0,
    totalCostUsd: 0,
  };
}

export function useSessions({
  apiKey,
  workspaceId,
  tagFilter,
}: {
  apiKey: string;
  workspaceId?: string | null;
  tagFilter?: string | null;
} = { apiKey: "" }) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [online, setOnline] = useState(false);
  const [allTags, setAllTags] = useState<string[]>([]);
  const apiRef = useRef<SessionsApi | null>(null);

  useEffect(() => {
    apiRef.current = apiKey ? new SessionsApi(apiKey) : null;
  }, [apiKey]);

  const refresh = useCallback(async () => {
    const api = apiRef.current;
    if (!api) {
      const local = loadSessions();
      if (local.length === 0) {
        const s = newLocalSession();
        setSessions([s]);
        setActiveId(s.id);
        saveSessions([s]);
      } else {
        setSessions(local);
        setActiveId((cur) => cur ?? local[0]!.id);
      }
      setOnline(false);
      return;
    }
    try {
      // v1.5: 按 workspace + tag 过滤
      const remote = await api.list(workspaceId ?? null, 50, tagFilter ?? null);
      setSessions(remote);
      setOnline(true);
      saveSessions(remote);
      // 同时刷新全部 tag (用于 sidebar chip 自动补全)
      try {
        setAllTags(await api.listTags());
      } catch { /* ignore */ }
      // 切 workspace/tag 时, 旧 active 不在新列表 → 自动选第一个
      setActiveId((cur) =>
        cur && remote.some((s) => s.id === cur) ? cur : remote[0]?.id ?? null,
      );
    } catch (e) {
      console.warn("[useSessions] remote list failed, fallback to local:", e);
      setOnline(false);
      const local = loadSessions();
      if (local.length === 0) {
        const s = newLocalSession();
        setSessions([s]);
        setActiveId(s.id);
        saveSessions([s]);
      } else {
        setSessions(local);
        setActiveId((cur) => cur ?? local[0]!.id);
      }
    }
  }, [workspaceId, tagFilter]);

  // workspace 切换 → 仅清空 sidebar 局部数据 (不动 ready, 不让整页进 Loading)
  useEffect(() => {
    setSessions([]);
    setActiveId(null);
  }, [workspaceId]);

  useEffect(() => {
    (async () => {
      await refresh();
      setReady(true);
    })();
  }, [refresh, apiKey]);

  const create = useCallback(async (): Promise<string | null> => {
    const api = apiRef.current;
    if (api && online) {
      try {
        // v1.5: 创建时绑定当前 workspace
        const s = await api.create("新会话", workspaceId ?? null);
        setSessions((prev) => {
          const next = [s, ...prev];
          saveSessions(next);
          return next;
        });
        setActiveId(s.id);
        return s.id;
      } catch (e) {
        console.warn("[useSessions] create remote failed:", e);
        setOnline(false);
      }
    }
    const s = newLocalSession();
    setSessions((prev) => {
      const next = [s, ...prev];
      saveSessions(next);
      return next;
    });
    setActiveId(s.id);
    return s.id;
  }, [online, workspaceId]);

  const remove = useCallback(
    async (id: string) => {
      const api = apiRef.current;
      if (api && online) {
        try {
          await api.delete(id);
        } catch (e) {
          console.warn("[useSessions] delete remote failed:", e);
        }
      }
      setSessions((prev) => {
        const next = prev.filter((s) => s.id !== id);
        saveSessions(next);
        if (activeId === id) {
          setActiveId(next[0]?.id ?? null);
        }
        return next;
      });
    },
    [activeId, online],
  );

  const rename = useCallback(
    async (id: string, title: string) => {
      const api = apiRef.current;
      setSessions((prev) => {
        const next = prev.map((s) =>
          s.id === id ? { ...s, title, updatedAt: Date.now() } : s,
        );
        saveSessions(next);
        return next;
      });
      if (api && online) {
        try {
          await api.rename(id, title);
        } catch (e) {
          console.warn("[useSessions] rename remote failed:", e);
        }
      }
    },
    [online],
  );

  const setTags = useCallback(
    async (id: string, tags: string[]) => {
      const api = apiRef.current;
      if (!api || !online) return;
      try {
        const updated = await api.setTags(id, tags);
        setSessions((prev) => {
          const next = prev.map((s) =>
            s.id === id ? { ...s, tags: updated.tags } : s,
          );
          saveSessions(next);
          return next;
        });
        // tag 列表也可能变化, 异步刷新
        try { setAllTags(await api.listTags()); } catch { /* ignore */ }
      } catch (e) {
        console.warn("[useSessions] setTags failed:", e);
        throw e;
      }
    },
    [online],
  );

  const bumpStats = useCallback(
    (id: string, addedMessages: number, addedCostUsd: number) => {
      setSessions((prev) => {
        const next = prev.map((s) =>
          s.id === id
            ? {
                ...s,
                messageCount: s.messageCount + addedMessages,
                totalCostUsd: s.totalCostUsd + addedCostUsd,
                updatedAt: Date.now(),
              }
            : s,
        );
        saveSessions(next);
        return next;
      });
    },
    [],
  );

  return {
    sessions,
    activeId,
    ready,
    online,
    allTags,
    setActive: setActiveId,
    create,
    remove,
    rename,
    setTags,
    bumpStats,
    refresh,
  };
}
