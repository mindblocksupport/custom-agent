"use client";

import { useEffect, useState } from "react";
import { AuditApi, type AuditLogEntry } from "../lib/api/audit";
import { KeysApi, type ApiKey, type ApiKeyWithRaw, type KeyRole } from "../lib/api/keys";
import { confirmDialog, toast } from "../lib/ui";
import type { Settings } from "../lib/types";

const COMMON_MODELS = [
  "deepseek/deepseek-chat",
  "deepseek/deepseek-reasoner",
  "claude-sonnet-4-5-20250929",
  "claude-opus-4-7",
  "gpt-4o-mini",
  "gpt-5-mini",
  "qwen/qwen-max-latest",
  "gemini/gemini-2.0-flash-exp",
];

type Tab = "general" | "keys" | "audit";

export function SettingsDrawer({
  open,
  settings,
  onClose,
  onSave,
}: {
  open: boolean;
  settings: Settings;
  onClose: () => void;
  onSave: (s: Settings) => void;
}) {
  const [tab, setTab] = useState<Tab>("general");
  const [draft, setDraft] = useState<Settings>(settings);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    setDraft(settings);
    if (open) setTab("general");
  }, [settings, open]);

  if (!open) return null;

  const testConnection = async () => {
    setTesting(true);
    try {
      const url = draft.baseUrl
        ? `${draft.baseUrl.replace(/\/$/, "")}/health/`
        : "/api/health";
      const r = await fetch(url, {
        headers: { Authorization: `Bearer ${draft.apiKey}` },
      });
      if (r.ok) {
        toast.success("连接成功", url);
      } else {
        toast.error(`HTTP ${r.status}`, url);
      }
    } catch (e) {
      toast.fromError(e, "连接失败");
    } finally {
      setTesting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      style={{ background: "var(--bg-overlay)" }}
      onClick={onClose}
    >
      <div
        className="responsive-drawer w-96 max-w-full h-full flex flex-col animate-in"
        style={{
          background: "var(--bg-elev)",
          boxShadow: "var(--shadow-lg)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="px-4 py-3 border-b"
          style={{ borderColor: "var(--border)" }}
        >
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold" style={{ color: "var(--fg)" }}>
              ⚙ 设置
            </h2>
            <button
              onClick={onClose}
              className="text-xl leading-none"
              style={{ color: "var(--fg-subtle)" }}
            >
              ✕
            </button>
          </div>
          <div className="flex gap-1">
            <TabPill active={tab === "general"} onClick={() => setTab("general")}>
              通用
            </TabPill>
            <TabPill active={tab === "keys"} onClick={() => setTab("keys")}>
              API Keys
            </TabPill>
            <TabPill active={tab === "audit"} onClick={() => setTab("audit")}>
              审计
            </TabPill>
          </div>
        </div>

        {tab === "general" && (
          <>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              <Field label="API Key (本地)" hint="后端鉴权 token; 默认 dev-key-change-me">
                <input
                  type="password"
                  value={draft.apiKey}
                  onChange={(e) => setDraft({ ...draft, apiKey: e.target.value })}
                  className="w-full px-2.5 py-1.5 rounded-md text-sm outline-none font-mono"
                  style={{
                    background: "var(--bg-elev-2)",
                    color: "var(--fg)",
                    border: "1px solid var(--border)",
                  }}
                />
              </Field>

              <Field
                label="Backend URL"
                hint="留空 = 走当前域 /api/chat 代理 (推荐); 否则填 http://host:8000"
              >
                <input
                  type="text"
                  value={draft.baseUrl}
                  onChange={(e) => setDraft({ ...draft, baseUrl: e.target.value })}
                  placeholder="http://localhost:8000 (可空)"
                  className="w-full px-2.5 py-1.5 rounded-md text-sm outline-none font-mono"
                  style={{
                    background: "var(--bg-elev-2)",
                    color: "var(--fg)",
                    border: "1px solid var(--border)",
                  }}
                />
              </Field>

              <Field label="默认模型" hint="LiteLLM 兼容 ID; auto = 智能路由">
                <input
                  type="text"
                  value={draft.model}
                  onChange={(e) => setDraft({ ...draft, model: e.target.value })}
                  list="model-list"
                  className="w-full px-2.5 py-1.5 rounded-md text-sm outline-none font-mono"
                  style={{
                    background: "var(--bg-elev-2)",
                    color: "var(--fg)",
                    border: "1px solid var(--border)",
                  }}
                />
                <datalist id="model-list">
                  <option value="auto" />
                  {COMMON_MODELS.map((m) => (
                    <option key={m} value={m} />
                  ))}
                </datalist>
              </Field>

              <button
                onClick={testConnection}
                disabled={testing}
                className="w-full py-1.5 rounded-md text-xs font-medium transition"
                style={{
                  background: "var(--bg-elev-2)",
                  color: "var(--fg)",
                  border: "1px solid var(--border)",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--primary)")}
                onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--border)")}
              >
                {testing ? "测试中..." : "🧪 测试连接"}
              </button>

              <div
                className="text-[11px] leading-relaxed pt-3 border-t"
                style={{ color: "var(--fg-subtle)", borderColor: "var(--border)" }}
              >
                🔒 本地设置仅存于浏览器 localStorage, 不会上传; API Key 标签页可创建/吊销
                后端持久化的密钥。
              </div>
            </div>

            <div
              className="p-4 border-t flex gap-2"
              style={{ borderColor: "var(--border)" }}
            >
              <button
                onClick={onClose}
                className="flex-1 py-2 text-sm rounded-md transition"
                style={{
                  color: "var(--fg-muted)",
                  border: "1px solid var(--border)",
                }}
              >
                取消
              </button>
              <button
                onClick={() => {
                  onSave(draft);
                  toast.success("设置已保存");
                  onClose();
                }}
                className="flex-1 py-2 text-sm rounded-md font-semibold text-white"
                style={{ background: "var(--primary)" }}
              >
                保存
              </button>
            </div>
          </>
        )}

        {tab === "keys" && (
          <KeysPanel apiKey={settings.apiKey} currentRawKey={settings.apiKey} />
        )}

        {tab === "audit" && <AuditPanel apiKey={settings.apiKey} />}
      </div>
    </div>
  );
}

function AuditPanel({ apiKey }: { apiKey: string }) {
  const [items, setItems] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionFilter, setActionFilter] = useState<string>("");
  const [actorFilter, setActorFilter] = useState<string>("");
  const [sinceFilter, setSinceFilter] = useState<string>("");
  const [untilFilter, setUntilFilter] = useState<string>("");
  const [resourceTypeFilter, setResourceTypeFilter] = useState<string>("");
  const [resourceIdFilter, setResourceIdFilter] = useState<string>("");
  const [nextCursor, setNextCursor] = useState<number | null>(null);
  const [exporting, setExporting] = useState(false);

  // Date input value (YYYY-MM-DD) → ISO datetime (start of day UTC)
  const toIso = (d: string, endOfDay = false): string | undefined => {
    if (!d) return undefined;
    const t = endOfDay ? "23:59:59" : "00:00:00";
    return new Date(`${d}T${t}Z`).toISOString();
  };

  const filterParams = () => ({
    action_prefix: actionFilter || undefined,
    actor_id: actorFilter || undefined,
    resource_type: resourceTypeFilter || undefined,
    resource_id: resourceIdFilter || undefined,
    since: toIso(sinceFilter, false),
    until: toIso(untilFilter, true),
  });

  const refresh = async () => {
    if (!apiKey) return;
    setLoading(true);
    try {
      const r = await new AuditApi(apiKey).list({
        ...filterParams(),
        limit: 50,
      });
      setItems(r.items);
      setNextCursor(r.next_cursor);
    } catch (e) {
      toast.fromError(e, "加载审计失败");
    } finally {
      setLoading(false);
    }
  };

  const loadMore = async () => {
    if (!apiKey || !nextCursor) return;
    setLoading(true);
    try {
      const r = await new AuditApi(apiKey).list({
        ...filterParams(),
        limit: 50,
        before_id: nextCursor,
      });
      setItems((prev) => [...prev, ...r.items]);
      setNextCursor(r.next_cursor);
    } catch (e) {
      toast.fromError(e, "加载更多失败");
    } finally {
      setLoading(false);
    }
  };

  const exportCsv = async () => {
    if (!apiKey) return;
    setExporting(true);
    try {
      await new AuditApi(apiKey).downloadCsv({
        ...filterParams(),
        max_rows: 5000,
      });
      toast.success("CSV 已下载 (UTF-8 BOM, Excel 直开)");
    } catch (e) {
      toast.fromError(e, "导出失败");
    } finally {
      setExporting(false);
    }
  };

  const cleanup = async () => {
    const ok = await confirmDialog({
      title: "清理 90 天前的审计日志?",
      description:
        "默认保留近 90 天。删除后不可恢复; 如需更严格 retention 请改 retain_days.",
      confirmText: "清理 90 天前",
      danger: true,
    });
    if (!ok) return;
    try {
      const r = await new AuditApi(apiKey).cleanup(90);
      toast.success(`已清理 ${r.deleted} 条 (保留近 ${r.retain_days} 天)`);
      await refresh();
    } catch (e) {
      toast.fromError(e, "清理失败");
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiKey, actionFilter, actorFilter, sinceFilter, untilFilter,
      resourceTypeFilter, resourceIdFilter]);

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-3">
      <div
        className="rounded-lg p-3 space-y-2"
        style={{
          background: "var(--bg-elev-2)",
          border: "1px solid var(--border)",
        }}
      >
        <div className="flex items-center justify-between">
          <div className="text-[11px] font-semibold" style={{ color: "var(--fg-muted)" }}>
            筛选
          </div>
          <div className="flex gap-1">
            <button
              onClick={exportCsv}
              disabled={exporting}
              className="text-[10px] px-2 py-0.5 rounded font-medium disabled:opacity-50"
              style={{
                background: "var(--bg-elev)",
                color: "var(--accent-soft-fg)",
                border: "1px solid var(--accent)",
              }}
              title="导出当前筛选下最多 5000 行 CSV (Excel 可直开)"
            >
              {exporting ? "..." : "📥 CSV"}
            </button>
            <button
              onClick={cleanup}
              className="text-[10px] px-2 py-0.5 rounded font-medium"
              style={{
                background: "var(--bg-elev)",
                color: "var(--danger-soft-fg)",
                border: "1px solid var(--danger)",
              }}
              title="清理 90 天前的审计日志"
            >
              🗑 清旧
            </button>
          </div>
        </div>
        <select
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          className="w-full px-2 py-1 rounded text-xs outline-none"
          style={{
            background: "var(--bg-elev)",
            color: "var(--fg)",
            border: "1px solid var(--border)",
          }}
        >
          <option value="">全部 action</option>
          <option value="key.">key.* (创建/吊销/改 role)</option>
          <option value="workspace.">workspace.* (创建/改/成员)</option>
          <option value="skill.">skill.* (创建/改/删/装/回滚)</option>
          <option value="kb_doc.">kb_doc.* (KB 删)</option>
          <option value="session.">session.* (会话删)</option>
          <option value="audit.">audit.* (清旧自审)</option>
        </select>
        <input
          value={actorFilter}
          onChange={(e) => setActorFilter(e.target.value)}
          placeholder="按 actor_id 过滤 (留空 = 全部)"
          className="w-full px-2 py-1 rounded text-xs outline-none"
          style={{
            background: "var(--bg-elev)",
            color: "var(--fg)",
            border: "1px solid var(--border)",
          }}
        />
        {(resourceTypeFilter || resourceIdFilter) && (
          <div
            className="flex items-center justify-between gap-2 text-[10px] px-2 py-1 rounded"
            style={{
              background: "var(--accent-soft)",
              color: "var(--accent-soft-fg)",
              border: "1px solid var(--accent)",
            }}
          >
            <span className="truncate">
              🎯 聚焦:{" "}
              <span className="font-mono">
                {resourceTypeFilter}
                {resourceIdFilter ? `: ${resourceIdFilter}` : ""}
              </span>
            </span>
            <button
              onClick={() => {
                setResourceTypeFilter("");
                setResourceIdFilter("");
              }}
              className="opacity-70 hover:opacity-100 shrink-0"
              title="清掉资源 filter"
            >
              ✕
            </button>
          </div>
        )}
        <div className="grid grid-cols-2 gap-1.5">
          <div>
            <label
              className="text-[10px] block mb-0.5"
              style={{ color: "var(--fg-subtle)" }}
            >
              起 (since)
            </label>
            <input
              type="date"
              value={sinceFilter}
              onChange={(e) => setSinceFilter(e.target.value)}
              className="w-full px-2 py-1 rounded text-xs outline-none"
              style={{
                background: "var(--bg-elev)",
                color: "var(--fg)",
                border: "1px solid var(--border)",
              }}
            />
          </div>
          <div>
            <label
              className="text-[10px] block mb-0.5"
              style={{ color: "var(--fg-subtle)" }}
            >
              止 (until)
            </label>
            <input
              type="date"
              value={untilFilter}
              onChange={(e) => setUntilFilter(e.target.value)}
              className="w-full px-2 py-1 rounded text-xs outline-none"
              style={{
                background: "var(--bg-elev)",
                color: "var(--fg)",
                border: "1px solid var(--border)",
              }}
            />
          </div>
        </div>
      </div>

      <div className="space-y-1.5">
        {loading && items.length === 0 && (
          <div className="space-y-1.5">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 skeleton rounded-md" />
            ))}
          </div>
        )}
        {!loading && items.length === 0 && (
          <div
            className="text-xs py-4 text-center"
            style={{ color: "var(--fg-subtle)" }}
          >
            暂无审计记录
          </div>
        )}
        {items.map((it) => (
          <div
            key={it.id}
            className="rounded-md p-2.5 text-xs"
            style={{
              background: "var(--bg-elev-2)",
              border: "1px solid var(--border)",
            }}
          >
            <div className="flex items-center justify-between gap-2">
              <span
                className="font-mono px-1.5 py-0.5 rounded text-[10px]"
                style={{
                  background: actionPalette(it.action).bg,
                  color: actionPalette(it.action).fg,
                }}
              >
                {it.action}
              </span>
              <span className="text-[10px]" style={{ color: "var(--fg-subtle)" }}>
                {new Date(it.created_at).toLocaleString()}
              </span>
            </div>
            <div className="mt-1 flex flex-wrap gap-x-2 gap-y-0.5 text-[10px]" style={{ color: "var(--fg-muted)" }}>
              <button
                onClick={() => setActorFilter(it.actor_id)}
                className="hover:underline"
                title="只看此 actor"
              >
                actor: <b>{it.actor_id}</b>
              </button>
              {it.resource_type && it.resource_id && (
                <button
                  onClick={() => {
                    setResourceTypeFilter(it.resource_type!);
                    setResourceIdFilter(it.resource_id!);
                  }}
                  className="hover:underline"
                  title="只看此资源的全部历史"
                >
                  {it.resource_type}: <code className="font-mono">{it.resource_id}</code>
                </button>
              )}
              {it.ip && <span>ip: <code className="font-mono">{it.ip}</code></span>}
            </div>
            {Object.keys(it.detail).length > 0 && (
              <pre
                className="mt-1 text-[10px] font-mono whitespace-pre-wrap break-words p-1 rounded"
                style={{ background: "var(--bg-elev)", color: "var(--fg-subtle)" }}
              >
                {JSON.stringify(it.detail, null, 0)}
              </pre>
            )}
          </div>
        ))}
        {nextCursor && (
          <button
            onClick={loadMore}
            disabled={loading}
            className="w-full text-[11px] py-1.5 rounded transition disabled:opacity-50"
            style={{
              background: "var(--bg-elev-2)",
              color: "var(--fg-muted)",
              border: "1px solid var(--border)",
            }}
          >
            {loading ? "加载中..." : "加载更多"}
          </button>
        )}
      </div>

      <div
        className="text-[10px] leading-relaxed pt-2 border-t"
        style={{ color: "var(--fg-subtle)", borderColor: "var(--border)" }}
      >
        ℹ️ 记录变更类型操作 (key 创建/吊销/改 role · workspace 改/删/成员 · skill 创建/改/删/装).
        读类操作不记录。包含 actor / IP / UA / 详细 patch.
      </div>
    </div>
  );
}

function actionPalette(action: string): { bg: string; fg: string } {
  if (action.startsWith("key.create")) return { bg: "var(--success-soft)", fg: "var(--success-soft-fg)" };
  if (action.startsWith("key.revoke")) return { bg: "var(--danger-soft)", fg: "var(--danger-soft-fg)" };
  if (action.includes(".delete")) return { bg: "var(--danger-soft)", fg: "var(--danger-soft-fg)" };
  if (action.includes(".create")) return { bg: "var(--success-soft)", fg: "var(--success-soft-fg)" };
  if (action.includes(".patch") || action.includes(".update")) {
    return { bg: "var(--info-soft)", fg: "var(--info-soft-fg)" };
  }
  if (action.includes(".install")) return { bg: "var(--accent-soft)", fg: "var(--accent-soft-fg)" };
  if (action.includes("member.add")) return { bg: "var(--success-soft)", fg: "var(--success-soft-fg)" };
  if (action.includes("member.remove")) return { bg: "var(--warning-soft)", fg: "var(--warning-soft-fg)" };
  return { bg: "var(--bg-elev-2)", fg: "var(--fg-muted)" };
}

function KeysPanel({
  apiKey,
  currentRawKey,
}: {
  apiKey: string;
  currentRawKey: string;
}) {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [newActorId, setNewActorId] = useState("");
  const [newPrincipals, setNewPrincipals] = useState("");
  const [newRole, setNewRole] = useState<KeyRole>("admin");
  const [includeRevoked, setIncludeRevoked] = useState(false);
  const [justCreated, setJustCreated] = useState<ApiKeyWithRaw | null>(null);

  const refresh = async () => {
    if (!apiKey) return;
    setLoading(true);
    try {
      const list = await new KeysApi(apiKey).list(includeRevoked);
      setKeys(list);
    } catch (e) {
      toast.fromError(e, "加载 keys 失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiKey, includeRevoked]);

  const create = async () => {
    if (!newLabel.trim()) return;
    setCreating(true);
    try {
      const principalsList = newPrincipals
        .split(/[,;\n]/)
        .map((s) => s.trim())
        .filter(Boolean);
      const k = await new KeysApi(apiKey).create(newLabel.trim(), {
        actorId: showAdvanced && newActorId.trim()
          ? newActorId.trim()
          : undefined,
        principals: showAdvanced && principalsList.length > 0
          ? principalsList
          : undefined,
        role: showAdvanced ? newRole : undefined,
      });
      setJustCreated(k);
      setNewLabel("");
      setNewActorId("");
      setNewPrincipals("");
      setNewRole("admin");
      setShowAdvanced(false);
      await refresh();
    } catch (e) {
      toast.fromError(e, "创建失败");
    } finally {
      setCreating(false);
    }
  };

  const revoke = async (k: ApiKey) => {
    const ok = await confirmDialog({
      title: `吊销 key「${k.label ?? k.key_hash.slice(0, 12)}」?`,
      description:
        "吊销后所有使用此 key 的请求会立刻 401。如果当前 console 用的就是这把, 你会被踢出。",
      confirmText: "吊销",
      danger: true,
    });
    if (!ok) return;
    try {
      await new KeysApi(apiKey).revoke(k.key_hash);
      toast.success("已吊销");
      await refresh();
    } catch (e) {
      toast.fromError(e, "吊销失败");
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {/* 创建 */}
      <div
        className="rounded-lg p-3 space-y-2"
        style={{
          background: "var(--bg-elev-2)",
          border: "1px solid var(--border)",
        }}
      >
        <div className="text-[11px] font-semibold" style={{ color: "var(--fg-muted)" }}>
          创建新 Key
        </div>
        <div className="flex gap-2">
          <input
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !showAdvanced && newLabel.trim()) create();
            }}
            placeholder="标签 (eg: ci-bot, mobile-app)"
            className="flex-1 px-2.5 py-1.5 rounded-md text-sm outline-none"
            style={{
              background: "var(--bg-elev)",
              color: "var(--fg)",
              border: "1px solid var(--border)",
            }}
          />
          <button
            onClick={create}
            disabled={creating || !newLabel.trim()}
            className="px-3 py-1.5 rounded-md text-sm font-semibold text-white disabled:opacity-40"
            style={{ background: "var(--primary)" }}
          >
            {creating ? "..." : "生成"}
          </button>
        </div>
        <div className="flex items-center justify-between">
          <button
            onClick={() => setShowAdvanced((v) => !v)}
            className="text-[10px] underline"
            style={{ color: "var(--fg-subtle)" }}
          >
            {showAdvanced ? "▾" : "▸"} 高级 (改 actor / principals)
          </button>
          <span className="text-[10px]" style={{ color: "var(--fg-subtle)" }}>
            {showAdvanced ? "覆盖默认权限" : "继承当前调用者权限"}
          </span>
        </div>
        {showAdvanced && (
          <div
            className="space-y-2 p-2 rounded-md"
            style={{ background: "var(--bg-elev)", border: "1px dashed var(--border)" }}
          >
            <div>
              <label
                className="text-[10px] font-medium block mb-1"
                style={{ color: "var(--fg-muted)" }}
              >
                role
              </label>
              <select
                value={newRole}
                onChange={(e) => setNewRole(e.target.value as KeyRole)}
                className="w-full px-2 py-1 rounded text-xs outline-none"
                style={{
                  background: "var(--bg-elev-2)",
                  color: "var(--fg)",
                  border: "1px solid var(--border)",
                }}
              >
                <option value="admin">admin · 全权 (默认)</option>
                <option value="editor">editor · 读写 (不能管 key/workspace)</option>
                <option value="viewer">viewer · 只读 (不能改任何东西)</option>
              </select>
            </div>
            <div>
              <label
                className="text-[10px] font-medium block mb-1"
                style={{ color: "var(--fg-muted)" }}
              >
                actor_id (留空 = 当前 actor)
              </label>
              <input
                value={newActorId}
                onChange={(e) => setNewActorId(e.target.value)}
                placeholder="ci-bot / serviceaccount-foo"
                className="w-full px-2 py-1 rounded text-xs outline-none font-mono"
                style={{
                  background: "var(--bg-elev-2)",
                  color: "var(--fg)",
                  border: "1px solid var(--border)",
                }}
              />
            </div>
            <div>
              <label
                className="text-[10px] font-medium block mb-1"
                style={{ color: "var(--fg-muted)" }}
              >
                principals (逗号 / 换行分割; 留空 = 继承)
              </label>
              <textarea
                value={newPrincipals}
                onChange={(e) => setNewPrincipals(e.target.value)}
                rows={2}
                placeholder="user:bot, group:read-only"
                className="w-full px-2 py-1 rounded text-xs outline-none font-mono resize-y"
                style={{
                  background: "var(--bg-elev-2)",
                  color: "var(--fg)",
                  border: "1px solid var(--border)",
                }}
              />
              <div className="text-[10px] mt-1" style={{ color: "var(--fg-subtle)" }}>
                ⚠️ 子集化只在 v2 RBAC 后真正强制; v1 仅用于审计 / KB ACL
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 刚创建: 一次性显示 raw_key */}
      {justCreated && (
        <div
          className="rounded-lg p-3"
          style={{
            background: "var(--success-soft)",
            color: "var(--success-soft-fg)",
            border: "1px solid var(--success)",
          }}
        >
          <div className="font-semibold text-sm flex items-center gap-1">
            ✓ 已生成「{justCreated.label}」 — 仅本次显示
          </div>
          <div
            className="mt-2 font-mono text-xs break-all p-2 rounded"
            style={{ background: "var(--bg-elev)", color: "var(--fg)" }}
          >
            {justCreated.raw_key}
          </div>
          <div className="flex gap-2 mt-2">
            <button
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(justCreated.raw_key);
                  toast.success("已复制到剪贴板");
                } catch {
                  toast.error("复制失败");
                }
              }}
              className="text-xs px-2 py-1 rounded-md font-medium"
              style={{
                background: "var(--bg-elev)",
                color: "var(--success-soft-fg)",
                border: "1px solid var(--success)",
              }}
            >
              📋 复制
            </button>
            <button
              onClick={() => setJustCreated(null)}
              className="text-xs px-2 py-1 rounded-md"
              style={{ color: "var(--success-soft-fg)" }}
            >
              我已存好, 关闭
            </button>
          </div>
          <div className="text-[10px] mt-2 opacity-80">
            ⚠️ 关闭后, 后端只保留 sha256 哈希, 无法再恢复明文 key。
          </div>
        </div>
      )}

      {/* 列表 */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <div className="text-[11px] font-semibold" style={{ color: "var(--fg-muted)" }}>
            当前 tenant 的 keys ({keys.length})
          </div>
          <label
            className="text-[10px] flex items-center gap-1 cursor-pointer"
            style={{ color: "var(--fg-subtle)" }}
          >
            <input
              type="checkbox"
              checked={includeRevoked}
              onChange={(e) => setIncludeRevoked(e.target.checked)}
            />
            含已吊销
          </label>
        </div>
        {loading && (
          <div className="space-y-2">
            {[1, 2].map((i) => (
              <div key={i} className="h-14 skeleton rounded-md" />
            ))}
          </div>
        )}
        {!loading && keys.length === 0 && (
          <div
            className="text-xs py-4 text-center"
            style={{ color: "var(--fg-subtle)" }}
          >
            暂无 key
          </div>
        )}
        <div className="space-y-1.5">
          {keys.map((k) => {
            const isLocal = currentRawKey
              ? hashLooksLike(currentRawKey, k.key_hash)
              : false;
            const revoked = !!k.revoked_at;
            return (
              <div
                key={k.key_hash}
                className="rounded-md p-2.5"
                style={{
                  background: "var(--bg-elev-2)",
                  border: `1px solid ${isLocal ? "var(--primary)" : "var(--border)"}`,
                  opacity: revoked ? 0.55 : 1,
                }}
              >
                <div className="flex items-center justify-between gap-2 mb-1">
                  <div className="flex items-center gap-1.5 min-w-0">
                    <span className="text-sm font-medium truncate" style={{ color: "var(--fg)" }}>
                      {k.label ?? "(no label)"}
                    </span>
                    {isLocal && (
                      <span
                        className="text-[9px] px-1 rounded"
                        style={{
                          background: "var(--primary-soft)",
                          color: "var(--primary-soft-fg)",
                        }}
                      >
                        当前
                      </span>
                    )}
                    {revoked && (
                      <span
                        className="text-[9px] px-1 rounded"
                        style={{
                          background: "var(--danger-soft)",
                          color: "var(--danger-soft-fg)",
                        }}
                      >
                        已吊销
                      </span>
                    )}
                    <RoleBadge
                      role={k.role}
                      onChange={async (next) => {
                        if (next === k.role || revoked) return;
                        try {
                          await new KeysApi(apiKey).setRole(k.key_hash, next);
                          toast.success(`role 已改为 ${next}`);
                          await refresh();
                        } catch (e) {
                          toast.fromError(e, "改 role 失败");
                        }
                      }}
                      disabled={revoked}
                    />
                  </div>
                  {!revoked && (
                    <button
                      onClick={() => revoke(k)}
                      className="text-[10px] px-1.5 py-0.5 rounded"
                      style={{
                        color: "var(--danger-soft-fg)",
                        background: "transparent",
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--danger-soft)")}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                    >
                      吊销
                    </button>
                  )}
                </div>
                <div
                  className="text-[10px] font-mono truncate mb-0.5"
                  style={{ color: "var(--fg-subtle)" }}
                  title={k.key_hash}
                >
                  hash: {k.key_hash.slice(0, 12)}...{k.key_hash.slice(-4)}
                </div>
                <div
                  className="text-[10px] flex gap-2 flex-wrap"
                  style={{ color: "var(--fg-subtle)" }}
                >
                  <span>actor: {k.actor_id}</span>
                  <span>·</span>
                  <span title={k.created_at}>
                    创建 {new Date(k.created_at).toLocaleDateString()}
                  </span>
                  {k.last_used_at && (
                    <>
                      <span>·</span>
                      <span title={k.last_used_at}>
                        最后用 {new Date(k.last_used_at).toLocaleDateString()}
                      </span>
                    </>
                  )}
                </div>
                {k.principals.length > 0 && (
                  <div
                    className="text-[9px] font-mono mt-1 truncate"
                    style={{ color: "var(--fg-subtle)" }}
                    title={k.principals.join(", ")}
                  >
                    {k.principals.join(", ")}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div
        className="text-[10px] leading-relaxed pt-3 border-t"
        style={{ color: "var(--fg-subtle)", borderColor: "var(--border)" }}
      >
        ℹ️ Key 的 raw 明文只在创建时返回一次。后端只存 sha256 哈希。 吊销立即生效, 不可恢复。
      </div>
    </div>
  );
}

/** 浏览器侧没法跑 sha256? 实际上 SubtleCrypto 可以, 但同步不行.
 * 这里简化: 检查 hash 前 12 字符与本地 raw key 的 sha256 前 12 字符是否一致.
 * 同步 fallback (异步 hashCurrent 在 mount 时算一次).
 */
const hashCache: { raw: string; hash: string }[] = [];

function hashLooksLike(raw: string, fullHash: string): boolean {
  const c = hashCache.find((x) => x.raw === raw);
  if (c) return c.hash === fullHash;
  // 触发异步 hash, 下次 render 命中 cache
  computeHash(raw).then((h) => {
    if (!hashCache.some((x) => x.raw === raw)) {
      hashCache.push({ raw, hash: h });
    }
  });
  return false;
}

async function computeHash(raw: string): Promise<string> {
  if (typeof crypto?.subtle?.digest !== "function") return "";
  const buf = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(raw),
  );
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function RoleBadge({
  role, onChange, disabled,
}: {
  role: KeyRole;
  onChange: (next: KeyRole) => void;
  disabled?: boolean;
}) {
  const ROLE_STYLE: Record<KeyRole, { bg: string; fg: string; label: string }> = {
    admin: { bg: "var(--accent-soft)", fg: "var(--accent-soft-fg)", label: "admin" },
    editor: { bg: "var(--info-soft)", fg: "var(--info-soft-fg)", label: "editor" },
    viewer: { bg: "var(--bg-elev-2)", fg: "var(--fg-muted)", label: "viewer" },
  };
  const s = ROLE_STYLE[role];
  return (
    <select
      value={role}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value as KeyRole)}
      className="text-[9px] px-1 rounded outline-none disabled:opacity-60 cursor-pointer"
      style={{
        background: s.bg,
        color: s.fg,
        border: "none",
        appearance: "none",
        WebkitAppearance: "none",
        paddingRight: "0.4em",
      }}
      title="点击改 role (admin/editor/viewer)"
    >
      <option value="admin">admin</option>
      <option value="editor">editor</option>
      <option value="viewer">viewer</option>
    </select>
  );
}

function TabPill({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className="px-2.5 py-1 rounded-md text-xs font-medium transition"
      style={{
        background: active ? "var(--primary-soft)" : "transparent",
        color: active ? "var(--primary-soft-fg)" : "var(--fg-muted)",
      }}
    >
      {children}
    </button>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label
        className="text-xs font-semibold block mb-1"
        style={{ color: "var(--fg-muted)" }}
      >
        {label}
      </label>
      {children}
      {hint && (
        <div
          className="text-[11px] mt-1 leading-snug"
          style={{ color: "var(--fg-subtle)" }}
        >
          {hint}
        </div>
      )}
    </div>
  );
}
