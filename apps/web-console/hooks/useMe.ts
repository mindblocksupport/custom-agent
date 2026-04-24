"use client";

import { useEffect, useRef, useState } from "react";
import { MeApi, type MeProfile } from "../lib/api/me";

export function useMe({ apiKey }: { apiKey: string }) {
  const [profile, setProfile] = useState<MeProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const apiRef = useRef<MeApi | null>(null);

  useEffect(() => {
    if (!apiKey) {
      setProfile(null);
      apiRef.current = null;
      return;
    }
    apiRef.current = new MeApi(apiKey);
    apiRef.current
      .me()
      .then((p) => {
        setProfile(p);
        setError(null);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : String(e));
        setProfile(null);
      });
  }, [apiKey]);

  return { profile, error };
}
