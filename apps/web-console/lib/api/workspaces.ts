/** Workspaces typed client (v1.5). */
import type { Workspace } from "../types";

export interface WorkspacePatch {
  name?: string;
  description?: string;
  default_model?: string;
  allowed_models?: string[];
  allowed_tools?: string[];
  default_collection?: string;
  allowed_collections?: string[];
  budget_daily_usd?: number | null;
  budget_monthly_usd?: number | null;
}

export interface WorkspaceMember {
  actor_id: string;
  role: "owner" | "editor" | "viewer";
  created_at: string;
  budget_daily_usd: number | null;
  budget_monthly_usd: number | null;
}

export class WorkspacesApi {
  constructor(private apiKey: string) {}
  private async req<T>(path: string, init?: RequestInit): Promise<T> {
    const r = await fetch(`/api/workspaces${path}`, {
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
  list(mineOnly = true): Promise<Workspace[]> {
    return this.req(`?mine_only=${mineOnly}`);
  }
  create(name: string): Promise<Workspace> {
    return this.req("", { method: "POST", body: JSON.stringify({ name }) });
  }
  get(id: string): Promise<Workspace> {
    return this.req(`/${id}`);
  }
  patch(id: string, payload: WorkspacePatch): Promise<Workspace> {
    return this.req(`/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }
  delete(id: string): Promise<void> {
    return this.req(`/${id}`, { method: "DELETE" });
  }
  listMembers(id: string): Promise<WorkspaceMember[]> {
    return this.req(`/${id}/members`);
  }
  addMember(
    id: string,
    actorId: string,
    role: "owner" | "editor" | "viewer" = "viewer",
    budgetDailyUsd?: number | null,
    budgetMonthlyUsd?: number | null,
  ): Promise<WorkspaceMember> {
    return this.req(`/${id}/members`, {
      method: "POST",
      body: JSON.stringify({
        actor_id: actorId,
        role,
        ...(budgetDailyUsd !== undefined ? { budget_daily_usd: budgetDailyUsd } : {}),
        ...(budgetMonthlyUsd !== undefined ? { budget_monthly_usd: budgetMonthlyUsd } : {}),
      }),
    });
  }
  removeMember(id: string, actorId: string): Promise<void> {
    return this.req(`/${id}/members/${encodeURIComponent(actorId)}`, {
      method: "DELETE",
    });
  }
  setMemberBudget(
    id: string, actorId: string,
    budgetDailyUsd: number | null,
    budgetMonthlyUsd: number | null,
  ): Promise<WorkspaceMember> {
    return this.req(
      `/${id}/members/${encodeURIComponent(actorId)}/budget`,
      {
        method: "PATCH",
        body: JSON.stringify({
          budget_daily_usd: budgetDailyUsd,
          budget_monthly_usd: budgetMonthlyUsd,
        }),
      },
    );
  }
}
