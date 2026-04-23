"use client";

import { useCallback, useEffect, useState } from "react";
import {
  deleteSession as deleteSessionStorage,
  loadSessions,
  saveSessions,
} from "../lib/storage";
import type { Session } from "../lib/types";

function newSession(): Session {
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

export function useSessions(): {
  sessions: Session[];
  activeId: string | null;
  ready: boolean;
  setActive: (id: string) => void;
  create: () => string;
  remove: (id: string) => void;
  rename: (id: string, title: string) => void;
  bumpStats: (id: string, addedMessages: number, addedCostUsd: number) => void;
} {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const loaded = loadSessions();
    if (loaded.length === 0) {
      const s = newSession();
      setSessions([s]);
      setActiveId(s.id);
      saveSessions([s]);
    } else {
      setSessions(loaded);
      setActiveId(loaded[0]!.id);
    }
    setReady(true);
  }, []);

  const persist = useCallback((next: Session[]) => {
    setSessions(next);
    saveSessions(next);
  }, []);

  const create = useCallback(() => {
    const s = newSession();
    setSessions((prev) => {
      const next = [s, ...prev];
      saveSessions(next);
      return next;
    });
    setActiveId(s.id);
    return s.id;
  }, []);

  const remove = useCallback(
    (id: string) => {
      deleteSessionStorage(id);
      setSessions((prev) => {
        const next = prev.filter((s) => s.id !== id);
        if (next.length === 0) {
          const s = newSession();
          saveSessions([s]);
          setActiveId(s.id);
          return [s];
        }
        saveSessions(next);
        if (activeId === id) setActiveId(next[0]!.id);
        return next;
      });
    },
    [activeId],
  );

  const rename = useCallback((id: string, title: string) => {
    setSessions((prev) => {
      const next = prev.map((s) =>
        s.id === id ? { ...s, title, updatedAt: Date.now() } : s,
      );
      saveSessions(next);
      return next;
    });
  }, []);

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
    setActive: setActiveId,
    create,
    remove,
    rename,
    bumpStats,
  };
}
