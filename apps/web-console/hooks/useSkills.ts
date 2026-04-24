"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  SkillsApi,
  type SkillCreatePayload,
  type SkillUpdatePayload,
} from "../lib/api/skills";
import type { Skill } from "../lib/types";

const ACTIVE_SKILL_KEY = (wid: string) => `ca:active_skill:${wid}:v1`;

function safeGet(k: string): string | null {
  try { return typeof window !== "undefined" ? localStorage.getItem(k) : null; }
  catch { return null; }
}
function safeSet(k: string, v: string) {
  try { typeof window !== "undefined" && localStorage.setItem(k, v); } catch {}
}
function safeRemove(k: string) {
  try { typeof window !== "undefined" && localStorage.removeItem(k); } catch {}
}

export function useSkills({
  apiKey,
  workspaceId,
}: {
  apiKey: string;
  workspaceId: string | null;
}) {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [activeId, setActiveIdRaw] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const apiRef = useRef<SkillsApi | null>(null);

  useEffect(() => {
    apiRef.current = apiKey ? new SkillsApi(apiKey) : null;
  }, [apiKey]);

  const setActiveId = useCallback((id: string | null) => {
    setActiveIdRaw(id);
    if (!workspaceId) return;
    if (id) safeSet(ACTIVE_SKILL_KEY(workspaceId), id);
    else safeRemove(ACTIVE_SKILL_KEY(workspaceId));
  }, [workspaceId]);

  useEffect(() => {
    if (!workspaceId || !apiRef.current) {
      setSkills([]);
      setActiveIdRaw(null);
      setReady(true);
      return;
    }
    setReady(false);
    (async () => {
      try {
        // include_public=true → 同时拿其他 workspace 的 public skill (Skill 市场)
        const list = await apiRef.current!.listForWorkspace(workspaceId, true);
        setSkills(list);
        const stored = safeGet(ACTIVE_SKILL_KEY(workspaceId));
        const validStored = stored && list.some((s) => s.id === stored) ? stored : null;
        setActiveIdRaw(validStored);
      } catch (e) {
        console.warn("[useSkills] list failed:", e);
        setSkills([]);
      } finally {
        setReady(true);
      }
    })();
  }, [workspaceId, apiKey]);

  const refresh = useCallback(async () => {
    if (!workspaceId || !apiRef.current) return;
    try {
      const list = await apiRef.current.listForWorkspace(workspaceId, true);
      setSkills(list);
    } catch (e) {
      console.warn("[useSkills] refresh failed:", e);
    }
  }, [workspaceId]);

  const create = useCallback(async (payload: SkillCreatePayload) => {
    if (!workspaceId || !apiRef.current) {
      throw new Error("no workspace selected");
    }
    const s = await apiRef.current.create(workspaceId, payload);
    setSkills((prev) => [...prev, s]);
    return s;
  }, [workspaceId]);

  const update = useCallback(async (sid: string, payload: SkillUpdatePayload) => {
    if (!apiRef.current) throw new Error("api not ready");
    const updated = await apiRef.current.patch(sid, payload);
    setSkills((prev) => prev.map((s) => (s.id === sid ? updated : s)));
    return updated;
  }, []);

  const remove = useCallback(async (sid: string) => {
    if (!apiRef.current) return;
    await apiRef.current.delete(sid);
    setSkills((prev) => prev.filter((s) => s.id !== sid));
    if (activeId === sid) setActiveIdRaw(null);
  }, [activeId]);

  const install = useCallback(async (sourceSkillId: string) => {
    if (!workspaceId || !apiRef.current) {
      throw new Error("no workspace selected");
    }
    const installed = await apiRef.current.install(sourceSkillId, workspaceId);
    // 添加到列表 (如果同名已存在, refresh 会去重)
    await refresh();
    return installed;
  }, [workspaceId, refresh]);

  const active = skills.find((s) => s.id === activeId) ?? null;
  return {
    skills, activeId, active, ready,
    setActiveId, refresh, create, update, remove, install,
  };
}
