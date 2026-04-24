"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { WorkspacesApi, type WorkspacePatch } from "../lib/api/workspaces";
import type { Workspace } from "../lib/types";

const ACTIVE_KEY = "ca:active_workspace_id:v1";

function safeGet(k: string): string | null {
  try { return typeof window !== "undefined" ? localStorage.getItem(k) : null; }
  catch { return null; }
}
function safeSet(k: string, v: string) {
  try { typeof window !== "undefined" && localStorage.setItem(k, v); } catch {}
}

export function useWorkspaces({ apiKey }: { apiKey: string } = { apiKey: "" }) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeId, setActiveIdRaw] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const apiRef = useRef<WorkspacesApi | null>(null);

  useEffect(() => {
    apiRef.current = apiKey ? new WorkspacesApi(apiKey) : null;
  }, [apiKey]);

  const setActiveId = useCallback((id: string | null) => {
    setActiveIdRaw(id);
    if (id) safeSet(ACTIVE_KEY, id);
  }, []);

  const refresh = useCallback(async () => {
    const api = apiRef.current;
    if (!api) return;
    try {
      const list = await api.list(true);
      setWorkspaces(list);
      const stored = safeGet(ACTIVE_KEY);
      const validStored = stored && list.some((w) => w.id === stored) ? stored : null;
      setActiveIdRaw(validStored ?? list[0]?.id ?? null);
    } catch (e) {
      console.warn("[useWorkspaces] list failed:", e);
    }
  }, []);

  useEffect(() => {
    (async () => { await refresh(); setReady(true); })();
  }, [refresh, apiKey]);

  const create = useCallback(async (name: string) => {
    const api = apiRef.current;
    if (!api) return;
    const ws = await api.create(name);
    setWorkspaces((prev) => [ws, ...prev]);
    setActiveId(ws.id);
  }, [setActiveId]);

  const update = useCallback(
    async (id: string, payload: WorkspacePatch): Promise<Workspace> => {
      const api = apiRef.current;
      if (!api) throw new Error("api not ready");
      const updated = await api.patch(id, payload);
      setWorkspaces((prev) => prev.map((w) => (w.id === id ? updated : w)));
      return updated;
    },
    [],
  );

  return { workspaces, activeId, ready, setActiveId, create, update, refresh };
}
