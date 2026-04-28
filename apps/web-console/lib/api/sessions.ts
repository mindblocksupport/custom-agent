/**
 * Sessions typed API client (Day 8 finishing).
 * 后端: /v1/sessions/*  (services/api-server/routes/sessions.py)
 * 前端代理: /api/sessions/[...path]
 */

import type { Session } from "../types";

interface RemoteSession {
  id: string;
  title: string;
  message_count: number;
  total_cost_usd: number;
  created_at: string;
  updated_at: string;
  tags?: string[];
}

interface ListResp {
  items: RemoteSession[];
  next_cursor: string | null;
}

function toSession(r: RemoteSession): Session {
  return {
    id: r.id,
    title: r.title,
    createdAt: new Date(r.created_at).getTime() || Date.now(),
    updatedAt: new Date(r.updated_at).getTime() || Date.now(),
    messageCount: r.message_count,
    totalCostUsd: Number(r.total_cost_usd),
    tags: r.tags ?? [],
  };
}

export class SessionsApi {
  constructor(private apiKey: string) {}

  private async req<T>(path: string, init?: RequestInit): Promise<T> {
    const r = await fetch(`/api/sessions${path}`, {
      ...init,
      headers: {
        ...(init?.headers ?? {}),
        Authorization: `Bearer ${this.apiKey}`,
        "Content-Type": "application/json",
      },
    });
    if (!r.ok) {
      const t = await r.text().catch(() => "");
      throw new Error(`${r.status} ${t.slice(0, 100)}`);
    }
    return r.json() as Promise<T>;
  }

  async list(
    workspaceId?: string | null,
    limit = 50,
    tag?: string | null,
  ): Promise<Session[]> {
    const qs = new URLSearchParams();
    qs.set("limit", String(limit));
    if (workspaceId) qs.set("workspace_id", workspaceId);
    if (tag) qs.set("tag", tag);
    const data = await this.req<ListResp>(`?${qs.toString()}`);
    return data.items.map(toSession);
  }

  async listTags(): Promise<string[]> {
    const data = await this.req<{ tags: string[] }>("/tags");
    return data.tags;
  }

  async setTags(id: string, tags: string[]): Promise<Session> {
    const data = await this.req<RemoteSession>(`/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ tags }),
    });
    return toSession(data);
  }

  async create(
    title = "新会话",
    workspaceId?: string | null,
  ): Promise<Session> {
    const body: Record<string, unknown> = { title };
    if (workspaceId) body.workspace_id = workspaceId;
    const data = await this.req<RemoteSession>("", {
      method: "POST",
      body: JSON.stringify(body),
    });
    return toSession(data);
  }

  async delete(id: string): Promise<void> {
    await this.req(`/${id}`, { method: "DELETE" });
  }

  async rename(id: string, title: string): Promise<Session> {
    const data = await this.req<RemoteSession>(`/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    });
    return toSession(data);
  }

  async refreshOne(id: string): Promise<Session | null> {
    try {
      const data = await this.req<{ session: RemoteSession }>(
        `/${id}?include_messages=false`,
      );
      return toSession(data.session);
    } catch {
      return null;
    }
  }
}
