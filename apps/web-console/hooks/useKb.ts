"use client";

import { useCallback, useEffect, useState } from "react";
import { MeApi, type KbCollections } from "../lib/api/me";
import type { KbDoc, KbJob } from "../lib/types";

export function useKb({
  apiKey,
  workspaceId,
  collection,
}: {
  apiKey: string;
  workspaceId?: string | null;
  collection?: string | null;
}) {
  const [docs, setDocs] = useState<KbDoc[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeJobs, setActiveJobs] = useState<KbJob[]>([]);
  const [collections, setCollections] = useState<KbCollections>({
    used: [],
    allowed: [],
    default: "default",
  });

  const refreshCollections = useCallback(async () => {
    if (!apiKey) return;
    try {
      const c = await new MeApi(apiKey).kbCollections(workspaceId);
      setCollections(c);
    } catch {
      /* ignore */
    }
  }, [apiKey, workspaceId]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = collection ? `?collection=${encodeURIComponent(collection)}` : "";
      const r = await fetch(`/api/kb/docs${qs}`, {
        headers: { Authorization: `Bearer ${apiKey}` },
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setDocs(j.items as KbDoc[]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [apiKey, collection]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    refreshCollections();
  }, [refreshCollections]);

  const upload = useCallback(
    async (file: File, overrideCollection?: string) => {
      const fd = new FormData();
      fd.append("file", file);
      const useCol = overrideCollection ?? collection;
      if (useCol) fd.append("collection", useCol);
      if (workspaceId) fd.append("workspace_id", workspaceId);
      const r = await fetch("/api/kb/upload", {
        method: "POST",
        headers: { Authorization: `Bearer ${apiKey}` },
        body: fd,
      });
      if (!r.ok) {
        const t = await r.text();
        throw new Error(`upload failed: ${r.status} ${t.slice(0, 100)}`);
      }
      const j = (await r.json()) as { job_id: string; collection: string };
      pollJob(j.job_id);
      return j;
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [apiKey, collection, workspaceId],
  );

  const pollJob = useCallback(
    async (jobId: string) => {
      const placeholder: KbJob = {
        id: jobId, doc_id: null, collection: collection ?? "default",
        source_uri: "uploading",
        status: "pending", progress: 0, stage: null, error: null,
        chunks_created: 0, chunks_reused: 0,
        created_at: new Date().toISOString(), finished_at: null,
      };
      setActiveJobs((prev) => [...prev, placeholder]);
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        try {
          const r = await fetch(`/api/kb/jobs/${jobId}`, {
            headers: { Authorization: `Bearer ${apiKey}` },
          });
          if (!r.ok) continue;
          const j = (await r.json()) as KbJob;
          setActiveJobs((prev) =>
            prev.map((x) => (x.id === jobId ? j : x)),
          );
          if (j.status === "done" || j.status === "failed") {
            setTimeout(() => {
              setActiveJobs((prev) => prev.filter((x) => x.id !== jobId));
            }, 3000);
            await refresh();
            await refreshCollections();
            break;
          }
        } catch {
          /* keep polling */
        }
      }
    },
    [apiKey, collection, refresh, refreshCollections],
  );

  const remove = useCallback(
    async (docId: string) => {
      const r = await fetch(`/api/kb/docs/${docId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${apiKey}` },
      });
      if (!r.ok) throw new Error(`delete failed: ${r.status}`);
      await refresh();
    },
    [apiKey, refresh],
  );

  return {
    docs, loading, error, refresh, upload, remove, activeJobs,
    collections, refreshCollections,
  };
}
