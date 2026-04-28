"use client";

import { useEffect, useMemo, useState } from "react";
import { extractVars } from "../lib/templating";

const KEY = (sessionId: string, skillId: string) =>
  `ca:skill_vars:${sessionId}:${skillId}:v1`;

function safeRead(k: string): Record<string, string> {
  try {
    if (typeof localStorage === "undefined") return {};
    const raw = localStorage.getItem(k);
    return raw ? (JSON.parse(raw) as Record<string, string>) : {};
  } catch {
    return {};
  }
}

function safeWrite(k: string, v: Record<string, string>) {
  try {
    typeof localStorage !== "undefined" && localStorage.setItem(k, JSON.stringify(v));
  } catch { /* ignore */ }
}

/** 给 (sessionId, skillId) 维护 system_prompt 中的 {{ var }} 填值, localStorage 持久化.
 *
 * 切 session/skill 自动重新读. system_prompt 为空 → required 为空数组, missing=false.
 */
export function useSkillVars({
  sessionId,
  skillId,
  systemPrompt,
}: {
  sessionId: string | null;
  skillId: string | null;
  systemPrompt: string | null;
}) {
  const required = useMemo(
    () => (systemPrompt ? extractVars(systemPrompt) : []),
    [systemPrompt],
  );
  const [values, setValues] = useState<Record<string, string>>({});

  // 切 session/skill 时重新读取
  useEffect(() => {
    if (!sessionId || !skillId) {
      setValues({});
      return;
    }
    setValues(safeRead(KEY(sessionId, skillId)));
  }, [sessionId, skillId]);

  const update = (next: Record<string, string>) => {
    setValues(next);
    if (sessionId && skillId) safeWrite(KEY(sessionId, skillId), next);
  };

  const missing = required.filter((v) => !(values[v] ?? "").trim());

  return {
    required,
    values,
    update,
    missing,
    hasUnfilled: required.length > 0 && missing.length > 0,
  };
}
