/** API keys 管理 client. */

export type KeyRole = "admin" | "editor" | "viewer";

export interface ApiKey {
  key_hash: string;
  label: string | null;
  actor_id: string;
  principals: string[];
  role: KeyRole;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
  is_current: boolean;
}

export interface ApiKeyWithRaw extends ApiKey {
  raw_key: string;
}

export class KeysApi {
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
  list(includeRevoked = false): Promise<ApiKey[]> {
    return this.req(`/api/keys?include_revoked=${includeRevoked}`);
  }
  create(
    label: string,
    opts: { actorId?: string; principals?: string[]; role?: KeyRole } = {},
  ): Promise<ApiKeyWithRaw> {
    const body: Record<string, unknown> = { label };
    if (opts.actorId) body.actor_id = opts.actorId;
    if (opts.principals) body.principals = opts.principals;
    if (opts.role) body.role = opts.role;
    return this.req("/api/keys", {
      method: "POST",
      body: JSON.stringify(body),
    });
  }
  revoke(keyHash: string): Promise<{ revoked: boolean }> {
    return this.req(`/api/keys/${keyHash}`, { method: "DELETE" });
  }
  rename(keyHash: string, label: string): Promise<ApiKey> {
    return this.req(`/api/keys/${keyHash}`, {
      method: "PATCH",
      body: JSON.stringify({ label }),
    });
  }
  setRole(keyHash: string, role: KeyRole): Promise<ApiKey> {
    return this.req(`/api/keys/${keyHash}`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    });
  }
}
