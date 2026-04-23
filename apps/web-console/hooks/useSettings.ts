"use client";

import { useEffect, useState } from "react";
import { DEFAULT_SETTINGS, loadSettings, saveSettings } from "../lib/storage";
import type { Settings } from "../lib/types";

export function useSettings(): {
  settings: Settings;
  ready: boolean;
  update: (patch: Partial<Settings>) => void;
} {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setSettings(loadSettings());
    setReady(true);
  }, []);

  const update = (patch: Partial<Settings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      saveSettings(next);
      return next;
    });
  };

  return { settings, ready, update };
}
