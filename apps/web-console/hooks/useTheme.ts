"use client";

import { useEffect, useState } from "react";

export type Theme = "light" | "dark";
const KEY = "ca:theme:v1";

function readInitial(): Theme {
  if (typeof window === "undefined") return "light";
  const stored = localStorage.getItem(KEY) as Theme | null;
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia?.("(prefers-color-scheme: dark)")?.matches
    ? "dark"
    : "light";
}

function apply(t: Theme) {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.theme = t;
}

export function useTheme(): {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggle: () => void;
} {
  const [theme, setThemeRaw] = useState<Theme>("light");

  useEffect(() => {
    const t = readInitial();
    setThemeRaw(t);
    apply(t);
  }, []);

  const setTheme = (t: Theme) => {
    setThemeRaw(t);
    apply(t);
    try {
      localStorage.setItem(KEY, t);
    } catch {
      /* ignore */
    }
  };

  const toggle = () => setTheme(theme === "light" ? "dark" : "light");
  return { theme, setTheme, toggle };
}
