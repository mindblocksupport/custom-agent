/** Skills typed client (v1.5). */
import type { Skill } from "../types";

export interface SkillCreatePayload {
  name: string;
  description?: string;
  system_prompt?: string;
  allowed_tools?: string[];
  default_collections?: string[];
  starter_examples?: string[];
  visibility?: "private" | "workspace" | "public";
  tags?: string[];
}

export type SkillUpdatePayload = Partial<SkillCreatePayload>;

export class SkillsApi {
  constructor(private apiKey: string) {}
  private async req<T>(path: string, init?: RequestInit): Promise<T> {
    const r = await fetch(path, {
      ...init,
      headers: {
        ...(init?.headers ?? {}),
        Authorization: `Bearer ${this.apiKey}`,
        "Content-Type": "application/json",
      },
    });
    if (!r.ok) throw new Error(`${r.status}: ${(await r.text()).slice(0, 100)}`);
    if (r.status === 204) return undefined as T;
    return r.json() as Promise<T>;
  }
  listForWorkspace(wid: string, includePublic = false): Promise<Skill[]> {
    return this.req(
      `/api/workspaces/${wid}/skills?include_public=${includePublic}`,
    );
  }
  listPublic(): Promise<Skill[]> {
    return this.req("/api/skills/public");
  }
  get(sid: string): Promise<Skill> {
    return this.req(`/api/skills/${sid}`);
  }
  create(wid: string, payload: SkillCreatePayload): Promise<Skill> {
    return this.req(`/api/workspaces/${wid}/skills`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }
  patch(sid: string, payload: SkillUpdatePayload): Promise<Skill> {
    return this.req(`/api/skills/${sid}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }
  delete(sid: string): Promise<void> {
    return this.req(`/api/skills/${sid}`, { method: "DELETE" });
  }
  install(sid: string, targetWorkspaceId: string): Promise<Skill> {
    return this.req(`/api/skills/${sid}/install`, {
      method: "POST",
      body: JSON.stringify({ workspace_id: targetWorkspaceId }),
    });
  }
  listVersions(sid: string): Promise<Skill[]> {
    return this.req(`/api/skills/${sid}/versions`);
  }
  rollback(sid: string, targetVersion: number): Promise<Skill> {
    return this.req(`/api/skills/${sid}/rollback`, {
      method: "POST",
      body: JSON.stringify({ target_version: targetVersion }),
    });
  }
}
