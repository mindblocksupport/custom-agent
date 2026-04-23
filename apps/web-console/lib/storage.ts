/** 极简 localStorage 封装(SSR 安全) */

import type { Session, Settings, UiMessage } from "./types";

const SESSIONS_KEY = "ca:sessions:v1";
const SESSION_MSGS_KEY = (id: string) => `ca:session:${id}:msgs:v1`;
const SETTINGS_KEY = "ca:settings:v1";

const isBrowser = typeof window !== "undefined";

function safeGet(key: string): string | null {
  if (!isBrowser) return null;
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key: string, value: string): void {
  if (!isBrowser) return;
  try {
    localStorage.setItem(key, value);
  } catch {
    /* quota / privacy mode - ignore */
  }
}

function safeRemove(key: string): void {
  if (!isBrowser) return;
  try {
    localStorage.removeItem(key);
  } catch {
    /* ignore */
  }
}

// ---- Sessions ----
export function loadSessions(): Session[] {
  const raw = safeGet(SESSIONS_KEY);
  if (!raw) return [];
  try {
    return JSON.parse(raw) as Session[];
  } catch {
    return [];
  }
}

export function saveSessions(sessions: Session[]): void {
  safeSet(SESSIONS_KEY, JSON.stringify(sessions));
}

export function loadMessages(sessionId: string): UiMessage[] {
  const raw = safeGet(SESSION_MSGS_KEY(sessionId));
  if (!raw) return [];
  try {
    return JSON.parse(raw) as UiMessage[];
  } catch {
    return [];
  }
}

export function saveMessages(sessionId: string, msgs: UiMessage[]): void {
  safeSet(SESSION_MSGS_KEY(sessionId), JSON.stringify(msgs));
}

export function deleteSession(sessionId: string): void {
  safeRemove(SESSION_MSGS_KEY(sessionId));
}

// ---- Settings ----
export const DEFAULT_SETTINGS: Settings = {
  apiKey: "dev-key-change-me",
  baseUrl: "", // 空 = 走同源 /api/chat 代理
  model: "deepseek/deepseek-chat",
};

export function loadSettings(): Settings {
  const raw = safeGet(SETTINGS_KEY);
  if (!raw) return DEFAULT_SETTINGS;
  try {
    return { ...DEFAULT_SETTINGS, ...(JSON.parse(raw) as Settings) };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export function saveSettings(s: Settings): void {
  safeSet(SETTINGS_KEY, JSON.stringify(s));
}
