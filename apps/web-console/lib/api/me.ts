/** /v1/me + usage + collections + chunks + sessions:search clients. */

export interface MeProfile {
  actor_id: string;
  tenant_id: string;
  principals: string[];
  workspace_count: number;
  skill_count_visible: number;
  api_version: string;
}

export interface UsageDayPoint {
  day: string;
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

export interface UsageBySkillPoint {
  skill_id: string | null;
  skill_name: string;
  sessions: number;
  messages: number;
  cost_usd: number;
}

export interface UsageDailyBySkillPoint {
  day: string;        // ISO date
  skill_id: string | null;
  skill_name: string;
  cost_usd: number;
  messages: number;
}

export interface UsageDailyByModelPoint {
  day: string;
  model: string;
  cost_usd: number;
  messages: number;
}

export interface UsageByActorPoint {
  actor_id: string;
  sessions: number;
  messages: number;
  cost_usd: number;
}

export interface UsageDailyByActorPoint {
  day: string;
  actor_id: string;
  cost_usd: number;
  messages: number;
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
  by_skill: UsageBySkillPoint[];
  daily_by_skill: UsageDailyBySkillPoint[];
  daily_by_model: UsageDailyByModelPoint[];
  by_actor: UsageByActorPoint[];
  daily_by_actor: UsageDailyByActorPoint[];
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

export interface MyBudget {
  workspace_id: string;
  today_cost_usd: number;
  month_cost_usd: number;
  budget_daily_usd: number | null;
  budget_monthly_usd: number | null;
  has_limit: boolean;
}

export interface KbChunk {
  id: string;
  chunk_seq: number;
  doc_version: number;
  content: string;
  page: number | null;
  char_offset_start: number | null;
  char_offset_end: number | null;
  parent_id: string | null;
}

export interface KbChunkList {
  doc_id: string;
  items: KbChunk[];
  truncated: boolean;
}

export interface SessionSearchHit {
  session: {
    id: string;
    title: string;
    message_count: number;
    total_cost_usd: number;
    created_at: string;
    updated_at: string;
    workspace_id?: string | null;
    skill_id?: string | null;
  };
  snippet: string | null;
}

export interface SessionSearchResp {
  items: SessionSearchHit[];
  query: string;
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
  myBudget(wid: string): Promise<MyBudget | null> {
    return this.req<MyBudget>(`/api/workspaces/${wid}/me/budget`).catch(
      () => null,  // 404 (not member) → null, 不当 error
    );
  }
  kbCollections(workspaceId?: string | null): Promise<KbCollections> {
    const qs = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : "";
    return this.req(`/api/kb/collections${qs}`);
  }
  kbDocChunks(docId: string, limit = 100): Promise<KbChunkList> {
    return this.req(`/api/kb/docs/${docId}/chunks?limit=${limit}`);
  }
  searchSessions(
    q: string, opts: { workspaceId?: string | null; limit?: number } = {},
  ): Promise<SessionSearchResp> {
    const params = new URLSearchParams();
    params.set("q", q);
    if (opts.workspaceId) params.set("workspace_id", opts.workspaceId);
    if (opts.limit) params.set("limit", String(opts.limit));
    return this.req(`/api/sessions/search?${params.toString()}`);
  }
}
