/** /v1/audit client. */

export interface AuditLogEntry {
  id: number;
  actor_id: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  detail: Record<string, unknown>;
  ip: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface AuditList {
  items: AuditLogEntry[];
  next_cursor: number | null;
}

export class AuditApi {
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
    return r.json() as Promise<T>;
  }
  list(opts: {
    actor_id?: string;
    action_prefix?: string;
    resource_type?: string;
    resource_id?: string;
    since?: string;        // ISO datetime
    until?: string;
    limit?: number;
    before_id?: number;
  } = {}): Promise<AuditList> {
    const p = new URLSearchParams();
    if (opts.actor_id) p.set("actor_id", opts.actor_id);
    if (opts.action_prefix) p.set("action_prefix", opts.action_prefix);
    if (opts.resource_type) p.set("resource_type", opts.resource_type);
    if (opts.resource_id) p.set("resource_id", opts.resource_id);
    if (opts.since) p.set("since", opts.since);
    if (opts.until) p.set("until", opts.until);
    if (opts.limit) p.set("limit", String(opts.limit));
    if (opts.before_id) p.set("before_id", String(opts.before_id));
    return this.req(`/api/audit?${p.toString()}`);
  }

  /** 触发浏览器下载 CSV; 用 fetch + blob 而非直接 a.href, 因为要带 Bearer header */
  async downloadCsv(opts: {
    actor_id?: string;
    action_prefix?: string;
    resource_type?: string;
    resource_id?: string;
    since?: string;
    until?: string;
    max_rows?: number;
  } = {}): Promise<void> {
    const p = new URLSearchParams();
    if (opts.actor_id) p.set("actor_id", opts.actor_id);
    if (opts.action_prefix) p.set("action_prefix", opts.action_prefix);
    if (opts.resource_type) p.set("resource_type", opts.resource_type);
    if (opts.resource_id) p.set("resource_id", opts.resource_id);
    if (opts.since) p.set("since", opts.since);
    if (opts.until) p.set("until", opts.until);
    if (opts.max_rows) p.set("max_rows", String(opts.max_rows));
    const r = await fetch(`/api/audit/csv?${p.toString()}`, {
      headers: { Authorization: `Bearer ${this.apiKey}` },
    });
    if (!r.ok) throw new Error(`${r.status}: ${(await r.text()).slice(0, 100)}`);
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const cd = r.headers.get("content-disposition") || "";
    const m = /filename="([^"]+)"/.exec(cd);
    a.download = m?.[1] ?? "audit.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  cleanup(retainDays: number): Promise<{ deleted: number; retain_days: number }> {
    return this.req(`/api/audit/cleanup`, {
      method: "POST",
      body: JSON.stringify({ retain_days: retainDays }),
    });
  }
}
