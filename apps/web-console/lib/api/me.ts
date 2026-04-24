/** /v1/me + /v1/workspaces/{wid}/usage typed clients. */

export interface MeProfile {
  actor_id: string;
  tenant_id: string;
  principals: string[];
  workspace_count: number;
  skill_count_visible: number;
  api_version: string;
}

export interface UsageDayPoint {
  day: string;        // ISO date
  sessions: number;
  messages: number;
  cost_usd: number;
}

export interface UsageByModelPoint {
  model: string;
  messages: number;
  cost_usd: number;
  input_tokens: number;
  output_tokens: number;
}

export interface WorkspaceUsage {
  workspace_id: string;
  workspace_name: string;
  days: number;
  total_sessions: number;
  total_messages: number;
  total_cost_usd: number;
  total_input_tokens: number;
  total_output_tokens: number;
  daily: UsageDayPoint[];
  by_model: UsageByModelPoint[];
  budget_daily_usd: number | null;
  budget_monthly_usd: number | null;
  today_cost_usd: number;
  month_cost_usd: number;
}

export interface KbCollections {
  used: string[];
  allowed: string[];
  default: string;
}

export class MeApi {
  constructor(private apiKey: string) {}
  private async req<T>(path: string): Promise<T> {
    const r = await fetch(path, {
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        "Content-Type": "application/json",
      },
    });
    if (!r.ok) throw new Error(`${r.status}: ${(await r.text()).slice(0, 100)}`);
    return r.json() as Promise<T>;
  }
  me(): Promise<MeProfile> {
    return this.req("/api/me");
  }
  workspaceUsage(wid: string, days = 7): Promise<WorkspaceUsage> {
    return this.req(`/api/workspaces/${wid}/usage?days=${days}`);
  }
  kbCollections(workspaceId?: string | null): Promise<KbCollections> {
    const qs = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : "";
    return this.req(`/api/kb/collections${qs}`);
  }
}
