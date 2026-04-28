"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MeApi, type MyBudget } from "../lib/api/me";

/** 拉当前 actor 在指定 workspace 的预算用量. workspaceId 为 null → 不拉.
 * 自动 5 分钟刷一次, 也暴露 refresh() 让外部 (e.g. chat send 完) 触发。
 */
export function useMyBudget({
  apiKey,
  workspaceId,
}: {
  apiKey: string;
  workspaceId: string | null;
}) {
  const [budget, setBudget] = useState<MyBudget | null>(null);
  const apiRef = useRef<MeApi | null>(null);

  useEffect(() => {
    apiRef.current = apiKey ? new MeApi(apiKey) : null;
  }, [apiKey]);

  const refresh = useCallback(async () => {
    if (!apiRef.current || !workspaceId) {
      setBudget(null);
      return;
    }
    try {
      const b = await apiRef.current.myBudget(workspaceId);
      setBudget(b);
    } catch {
      setBudget(null);
    }
  }, [workspaceId]);

  useEffect(() => {
    refresh();
    if (!workspaceId) return;
    const t = setInterval(refresh, 5 * 60 * 1000);
    return () => clearInterval(t);
  }, [refresh, workspaceId]);

  return { budget, refresh };
}
