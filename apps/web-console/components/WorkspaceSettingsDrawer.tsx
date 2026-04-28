"use client";

import { useEffect, useState } from "react";
import { WorkspacesApi, type WorkspaceMember, type WorkspacePatch } from "../lib/api/workspaces";
import { confirmDialog, toast } from "../lib/ui";
import type { Workspace } from "../lib/types";

const ALL_TOOLS = ["search_kb", "calculator", "get_time", "web_search"];

export function WorkspaceSettingsDrawer({
  open,
  workspace,
  apiKey,
  onClose,
  onUpdated,
}: {
  open: boolean;
  workspace: Workspace | null;
  apiKey: string;
  onClose: () => void;
  onUpdated: (w: Workspace) => void;
}) {
  const [tab, setTab] = useState<"general" | "members" | "danger">("general");
  const [draft, setDraft] = useState<WorkspacePatch>({});
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [loadingMembers, setLoadingMembers] = useState(false);
  const [saving, setSaving] = useState(false);
  const [newMemberId, setNewMemberId] = useState("");
  const [newMemberRole, setNewMemberRole] = useState<"owner" | "editor" | "viewer">("viewer");

  const api = apiKey ? new WorkspacesApi(apiKey) : null;

  useEffect(() => {
    if (open && workspace) {
      setDraft({
        name: workspace.name,
        description: workspace.description,
        default_model: workspace.default_model,
        allowed_models: workspace.allowed_models ?? [],
        allowed_tools: workspace.allowed_tools,
        default_collection: workspace.default_collection,
        allowed_collections: workspace.allowed_collections,
        budget_daily_usd: workspace.budget_daily_usd,
        budget_monthly_usd: workspace.budget_monthly_usd,
      });
      setTab("general");
    }
  }, [open, workspace]);

  useEffect(() => {
    if (!open || !workspace || !api || tab !== "members") return;
    setLoadingMembers(true);
    api
      .listMembers(workspace.id)
      .then(setMembers)
      .catch((e) => toast.fromError(e, "加载成员失败"))
      .finally(() => setLoadingMembers(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, workspace, tab]);

  if (!open || !workspace) return null;

  const save = async () => {
    if (!api) return;
    setSaving(true);
    try {
      const updated = await api.patch(workspace.id, draft);
      onUpdated(updated);
      toast.success("已保存");
      onClose();
    } catch (e) {
      toast.fromError(e, "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const addMember = async () => {
    if (!api || !newMemberId.trim()) return;
    try {
      const m = await api.addMember(workspace.id, newMemberId.trim(), newMemberRole);
      setMembers((prev) => [...prev, m]);
      setNewMemberId("");
      toast.success("成员已添加");
    } catch (e) {
      toast.fromError(e, "添加失败");
    }
  };

  const removeMember = async (actorId: string) => {
    if (!api) return;
    const ok = await confirmDialog({
      title: `移除成员「${actorId}」?`,
      description: "该成员将无法再访问此工作空间下的会话和数据。",
      confirmText: "移除",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.removeMember(workspace.id, actorId);
      setMembers((prev) => prev.filter((m) => m.actor_id !== actorId));
      toast.success("已移除");
    } catch (e) {
      toast.fromError(e, "移除失败");
    }
  };

  return (
    <div
      className="fixed inset-0 z-40 flex justify-end"
      style={{ background: "var(--bg-overlay)" }}
      onClick={onClose}
    >
      <div
        className="w-[28rem] max-w-full h-full flex flex-col animate-in"
        style={{
          background: "var(--bg-elev)",
          boxShadow: "var(--shadow-lg)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="px-4 py-3 border-b"
          style={{ borderColor: "var(--border)" }}
        >
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0">
              <div className="text-[10px] uppercase tracking-wide" style={{ color: "var(--fg-subtle)" }}>
                工作空间设置
              </div>
              <h2 className="font-semibold text-base truncate" style={{ color: "var(--fg)" }}>
                🗂️ {workspace.name}
              </h2>
            </div>
            <button
              onClick={onClose}
              className="text-xl leading-none"
              style={{ color: "var(--fg-subtle)" }}
              aria-label="关闭"
            >
              ✕
            </button>
          </div>

          <div className="flex gap-1 mt-3">
            <TabPill active={tab === "general"} onClick={() => setTab("general")}>
              通用
            </TabPill>
            <TabPill active={tab === "members"} onClick={() => setTab("members")}>
              成员 ({members.length || "·"})
            </TabPill>
            <TabPill active={tab === "danger"} onClick={() => setTab("danger")}>
              危险区
            </TabPill>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {tab === "general" && (
            <>
              <Field label="名称">
                <input
                  value={draft.name ?? ""}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                  className="w-full px-2.5 py-1.5 rounded-md text-sm outline-none"
                  style={{
                    background: "var(--bg-elev-2)",
                    color: "var(--fg)",
                    border: "1px solid var(--border)",
                  }}
                />
              </Field>
              <Field label="描述">
                <textarea
                  value={draft.description ?? ""}
                  onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                  rows={2}
                  className="w-full px-2.5 py-1.5 rounded-md text-sm outline-none resize-y"
                  style={{
                    background: "var(--bg-elev-2)",
                    color: "var(--fg)",
                    border: "1px solid var(--border)",
                  }}
                />
              </Field>
              <Field
                label="默认模型"
                hint="本工作空间的会话默认用此模型 (auto = 智能路由)"
              >
                <input
                  value={draft.default_model ?? ""}
                  onChange={(e) => setDraft({ ...draft, default_model: e.target.value })}
                  list="ws-model-list"
                  className="w-full px-2.5 py-1.5 rounded-md text-sm outline-none font-mono"
                  style={{
                    background: "var(--bg-elev-2)",
                    color: "var(--fg)",
                    border: "1px solid var(--border)",
                  }}
                />
                <datalist id="ws-model-list">
                  <option value="auto" />
                  <option value="deepseek/deepseek-chat" />
                  <option value="anthropic/claude-sonnet-4-6" />
                </datalist>
              </Field>

              <Field
                label="允许的模型 (空 = 不限)"
                hint="白名单 enforce: 不在列表的 model 调用 → 403. 留空 = 不限制 (默认)"
              >
                <ModelChipEditor
                  values={draft.allowed_models ?? []}
                  onChange={(next) =>
                    setDraft({ ...draft, allowed_models: next })
                  }
                />
              </Field>
              <Field
                label="允许的工具 (空 = 全部允许)"
                hint="工作空间级白名单, skill 还可在此基础上再过滤"
              >
                <div className="flex flex-wrap gap-1.5">
                  {ALL_TOOLS.map((t) => {
                    const checked = (draft.allowed_tools ?? []).includes(t);
                    return (
                      <label
                        key={t}
                        className="text-xs px-2 py-1 rounded border cursor-pointer transition"
                        style={{
                          background: checked ? "var(--primary-soft)" : "var(--bg-elev-2)",
                          color: checked ? "var(--primary-soft-fg)" : "var(--fg-muted)",
                          borderColor: checked ? "var(--primary)" : "var(--border)",
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) => {
                            const arr = draft.allowed_tools ?? [];
                            setDraft({
                              ...draft,
                              allowed_tools: e.target.checked
                                ? [...arr, t]
                                : arr.filter((x) => x !== t),
                            });
                          }}
                          className="hidden"
                        />
                        {t}
                      </label>
                    );
                  })}
                </div>
              </Field>
              <Field
                label="允许的 collections (KB 命名空间, 第一项 = 默认)"
                hint="search_kb 只能查这些 collection; 上传新文档默认放第一项"
              >
                <CollectionChipEditor
                  values={draft.allowed_collections ?? []}
                  defaultValue={draft.default_collection ?? "default"}
                  onChange={(allowed, def) =>
                    setDraft({
                      ...draft,
                      allowed_collections: allowed,
                      default_collection: def,
                    })
                  }
                />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="日预算 ($)">
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={draft.budget_daily_usd ?? ""}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        budget_daily_usd: e.target.value ? Number(e.target.value) : null,
                      })
                    }
                    placeholder="不限"
                    className="w-full px-2.5 py-1.5 rounded-md text-sm outline-none font-mono"
                    style={{
                      background: "var(--bg-elev-2)",
                      color: "var(--fg)",
                      border: "1px solid var(--border)",
                    }}
                  />
                </Field>
                <Field label="月预算 ($)">
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={draft.budget_monthly_usd ?? ""}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        budget_monthly_usd: e.target.value ? Number(e.target.value) : null,
                      })
                    }
                    placeholder="不限"
                    className="w-full px-2.5 py-1.5 rounded-md text-sm outline-none font-mono"
                    style={{
                      background: "var(--bg-elev-2)",
                      color: "var(--fg)",
                      border: "1px solid var(--border)",
                    }}
                  />
                </Field>
              </div>
            </>
          )}

          {tab === "members" && (
            <>
              <div className="space-y-2">
                <div className="text-[11px] font-medium" style={{ color: "var(--fg-muted)" }}>
                  当前成员
                </div>
                {loadingMembers && (
                  <div className="space-y-1.5">
                    {[1, 2].map((i) => (
                      <div key={i} className="h-9 skeleton rounded-md" />
                    ))}
                  </div>
                )}
                {!loadingMembers && members.length === 0 && (
                  <div className="text-xs italic" style={{ color: "var(--fg-subtle)" }}>
                    暂无显式成员 (创建者默认 owner)
                  </div>
                )}
                {members.map((m) => (
                  <MemberRow
                    key={m.actor_id}
                    member={m}
                    onRemove={() => removeMember(m.actor_id)}
                    onSaveBudget={async (daily, monthly) => {
                      if (!api) return;
                      try {
                        const updated = await api.setMemberBudget(
                          workspace.id, m.actor_id, daily, monthly,
                        );
                        setMembers((prev) =>
                          prev.map((x) => (x.actor_id === m.actor_id ? updated : x)),
                        );
                        toast.success("成员预算已更新");
                      } catch (e) {
                        toast.fromError(e, "保存失败");
                      }
                    }}
                  />
                ))}
              </div>

              <div
                className="border-t pt-3 space-y-2"
                style={{ borderColor: "var(--border)" }}
              >
                <div className="text-[11px] font-medium" style={{ color: "var(--fg-muted)" }}>
                  添加成员
                </div>
                <div className="flex gap-2">
                  <input
                    value={newMemberId}
                    onChange={(e) => setNewMemberId(e.target.value)}
                    placeholder="actor_id (邮箱 / userid)"
                    className="flex-1 px-2.5 py-1.5 rounded-md text-sm outline-none"
                    style={{
                      background: "var(--bg-elev-2)",
                      color: "var(--fg)",
                      border: "1px solid var(--border)",
                    }}
                  />
                  <select
                    value={newMemberRole}
                    onChange={(e) => setNewMemberRole(e.target.value as typeof newMemberRole)}
                    className="px-2 py-1.5 rounded-md text-sm outline-none"
                    style={{
                      background: "var(--bg-elev-2)",
                      color: "var(--fg)",
                      border: "1px solid var(--border)",
                    }}
                  >
                    <option value="viewer">viewer</option>
                    <option value="editor">editor</option>
                    <option value="owner">owner</option>
                  </select>
                  <button
                    onClick={addMember}
                    disabled={!newMemberId.trim()}
                    className="px-3 py-1.5 rounded-md text-sm font-medium text-white disabled:opacity-40"
                    style={{ background: "var(--primary)" }}
                  >
                    添加
                  </button>
                </div>
                <div className="text-[10px]" style={{ color: "var(--fg-subtle)" }}>
                  · viewer = 只读, editor = 创建会话/上传 KB, owner = 全权限
                </div>
              </div>
            </>
          )}

          {tab === "danger" && (
            <div className="space-y-3">
              <div
                className="rounded-md p-3 text-xs leading-relaxed"
                style={{
                  background: "var(--danger-soft)",
                  color: "var(--danger-soft-fg)",
                  border: "1px solid var(--danger)",
                }}
              >
                <div className="font-semibold mb-1">⚠️ 删除工作空间</div>
                此操作将软删除该 workspace。其下所有 session / KB / skill
                将不可访问。需要恢复请联系管理员。
              </div>
              <button
                onClick={async () => {
                  const ok = await confirmDialog({
                    title: `永久删除「${workspace.name}」?`,
                    description:
                      "工作空间下所有数据将不可见, 此操作不可在 UI 撤销。",
                    confirmText: "我已知晓, 删除",
                    danger: true,
                  });
                  if (!ok || !api) return;
                  try {
                    await api.delete(workspace.id);
                    toast.success("已删除");
                    onClose();
                    // 父组件需要 refresh, 这里通过 onUpdated 信号 (传 -1 标记?)
                    // 简化: 直接刷新页面
                    window.location.reload();
                  } catch (e) {
                    toast.fromError(e, "删除失败");
                  }
                }}
                className="w-full py-2 rounded-md text-sm font-semibold text-white"
                style={{ background: "var(--danger)" }}
              >
                删除此工作空间
              </button>
            </div>
          )}
        </div>

        {tab === "general" && (
          <div
            className="border-t p-3 flex gap-2"
            style={{ borderColor: "var(--border)" }}
          >
            <button
              onClick={onClose}
              disabled={saving}
              className="flex-1 py-2 rounded-md text-sm transition"
              style={{
                color: "var(--fg-muted)",
                border: "1px solid var(--border)",
              }}
            >
              取消
            </button>
            <button
              onClick={save}
              disabled={saving}
              className="flex-1 py-2 rounded-md text-sm font-semibold text-white"
              style={{ background: "var(--primary)" }}
            >
              {saving ? "保存中..." : "保存"}
            </button>
          </div>
        )}
      </div>
    </div>
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

function MemberRow({
  member,
  onRemove,
  onSaveBudget,
}: {
  member: WorkspaceMember;
  onRemove: () => void;
  onSaveBudget: (daily: number | null, monthly: number | null) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [daily, setDaily] = useState<string>(
    member.budget_daily_usd != null ? String(member.budget_daily_usd) : "",
  );
  const [monthly, setMonthly] = useState<string>(
    member.budget_monthly_usd != null ? String(member.budget_monthly_usd) : "",
  );
  const [saving, setSaving] = useState(false);

  return (
    <div
      className="px-2.5 py-2 rounded-md"
      style={{ background: "var(--bg-elev-2)" }}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="text-xs font-medium truncate" style={{ color: "var(--fg)" }}>
            {member.actor_id}
          </div>
          <div
            className="text-[10px] flex flex-wrap gap-1.5"
            style={{ color: "var(--fg-subtle)" }}
          >
            <span>{member.role}</span>
            <span>·</span>
            <span>加入 {new Date(member.created_at).toLocaleDateString()}</span>
            {(member.budget_daily_usd != null || member.budget_monthly_usd != null) && (
              <>
                <span>·</span>
                <span style={{ color: "var(--accent-soft-fg)" }} className="font-mono">
                  💵
                  {member.budget_daily_usd != null && ` ${member.budget_daily_usd}/日`}
                  {member.budget_monthly_usd != null && ` ${member.budget_monthly_usd}/月`}
                </span>
              </>
            )}
          </div>
        </div>
        <button
          onClick={() => setEditing((v) => !v)}
          className="text-xs px-2 py-0.5 rounded transition"
          style={{
            color: editing ? "var(--primary-soft-fg)" : "var(--fg-muted)",
            background: editing ? "var(--primary-soft)" : "transparent",
          }}
          title="改此成员的预算"
        >
          {editing ? "▾" : "💵"}
        </button>
        <button
          onClick={onRemove}
          className="text-xs px-2 py-0.5 rounded transition"
          style={{ color: "var(--danger-soft-fg)" }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "var(--danger-soft)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
        >
          移除
        </button>
      </div>

      {editing && (
        <div className="grid grid-cols-2 gap-2 mt-2">
          <div>
            <label className="text-[10px] block mb-0.5" style={{ color: "var(--fg-subtle)" }}>
              日预算 ($, 留空 = 不限)
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={daily}
              onChange={(e) => setDaily(e.target.value)}
              placeholder="不限"
              className="w-full px-2 py-1 rounded text-xs outline-none font-mono"
              style={{
                background: "var(--bg-elev)",
                color: "var(--fg)",
                border: "1px solid var(--border)",
              }}
            />
          </div>
          <div>
            <label className="text-[10px] block mb-0.5" style={{ color: "var(--fg-subtle)" }}>
              月预算 ($, 留空 = 不限)
            </label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={monthly}
              onChange={(e) => setMonthly(e.target.value)}
              placeholder="不限"
              className="w-full px-2 py-1 rounded text-xs outline-none font-mono"
              style={{
                background: "var(--bg-elev)",
                color: "var(--fg)",
                border: "1px solid var(--border)",
              }}
            />
          </div>
          <div className="col-span-2 flex justify-end gap-1">
            <button
              onClick={() => {
                setDaily(member.budget_daily_usd != null ? String(member.budget_daily_usd) : "");
                setMonthly(member.budget_monthly_usd != null ? String(member.budget_monthly_usd) : "");
                setEditing(false);
              }}
              className="text-[11px] px-2 py-0.5"
              style={{ color: "var(--fg-muted)" }}
              disabled={saving}
            >
              取消
            </button>
            <button
              onClick={async () => {
                setSaving(true);
                try {
                  const d = daily.trim() ? Number(daily) : null;
                  const m = monthly.trim() ? Number(monthly) : null;
                  await onSaveBudget(d, m);
                  setEditing(false);
                } finally {
                  setSaving(false);
                }
              }}
              disabled={saving}
              className="text-[11px] px-2.5 py-0.5 rounded text-white font-medium disabled:opacity-50"
              style={{ background: "var(--primary)" }}
            >
              {saving ? "..." : "保存"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/** 通用 chip 编辑器, 复用给 allowed_models. 跟 CollectionChipEditor 区别:
 * 没有 "default" 概念, chip 字符串保持原样 (model id 含 / 不能 lower).
 */
function ModelChipEditor({
  values,
  onChange,
}: {
  values: string[];
  onChange: (next: string[]) => void;
}) {
  const [draft, setDraft] = useState("");
  const SUGGESTIONS = [
    "auto",
    "deepseek/deepseek-chat",
    "deepseek/deepseek-reasoner",
    "anthropic/claude-sonnet-4-6",
    "openai/gpt-4o-mini",
    "gemini/gemini-2.0-flash-exp",
    "qwen/qwen-vl-max",
  ];

  const remove = (v: string) => onChange(values.filter((x) => x !== v));
  const add = () => {
    const v = draft.trim();
    if (!v || values.includes(v)) {
      setDraft("");
      return;
    }
    onChange([...values, v]);
    setDraft("");
  };

  return (
    <div className="space-y-2">
      {values.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {values.map((v) => (
            <span
              key={v}
              className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-mono"
              style={{
                background: "var(--bg-elev-2)",
                color: "var(--fg)",
                border: "1px solid var(--border)",
              }}
            >
              <span>{v}</span>
              <button
                type="button"
                onClick={() => remove(v)}
                className="opacity-60 hover:opacity-100"
                style={{ color: "var(--fg-subtle)" }}
                title="移除"
              >
                ✕
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="flex gap-1">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          list="ws-allowed-models-list"
          placeholder="加 model id (Enter 添加)"
          className="flex-1 px-2 py-1 rounded-md text-xs outline-none font-mono"
          style={{
            background: "var(--bg-elev-2)",
            color: "var(--fg)",
            border: "1px solid var(--border)",
          }}
        />
        <datalist id="ws-allowed-models-list">
          {SUGGESTIONS.filter((s) => !values.includes(s)).map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>
        <button
          type="button"
          onClick={add}
          disabled={!draft.trim()}
          className="px-2 rounded-md text-xs disabled:opacity-40"
          style={{ background: "var(--primary)", color: "white" }}
        >
          ＋
        </button>
      </div>
    </div>
  );
}

function CollectionChipEditor({
  values,
  defaultValue,
  onChange,
}: {
  values: string[];
  defaultValue: string;
  onChange: (allowed: string[], def: string) => void;
}) {
  const [draft, setDraft] = useState("");

  const list = values.length > 0 ? values : ["default"];

  const remove = (v: string) => {
    if (list.length <= 1) return; // 至少保留一个
    const next = list.filter((x) => x !== v);
    const nextDef = next.includes(defaultValue) ? defaultValue : next[0]!;
    onChange(next, nextDef);
  };

  const add = () => {
    const v = draft.trim().toLowerCase().replace(/\s+/g, "_");
    if (!v) return;
    if (list.includes(v)) {
      setDraft("");
      return;
    }
    onChange([...list, v], defaultValue || v);
    setDraft("");
  };

  const setAsDefault = (v: string) => {
    onChange(list, v);
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {list.map((v) => {
          const isDefault = v === defaultValue;
          return (
            <span
              key={v}
              className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-mono"
              style={{
                background: isDefault ? "var(--primary-soft)" : "var(--bg-elev-2)",
                color: isDefault ? "var(--primary-soft-fg)" : "var(--fg)",
                border: `1px solid ${isDefault ? "var(--primary)" : "var(--border)"}`,
              }}
            >
              <span>{v}</span>
              {isDefault && <span className="text-[9px]">★ 默认</span>}
              {!isDefault && (
                <button
                  type="button"
                  onClick={() => setAsDefault(v)}
                  className="text-[9px] opacity-60 hover:opacity-100"
                  title="设为默认"
                >
                  ★
                </button>
              )}
              {list.length > 1 && (
                <button
                  type="button"
                  onClick={() => remove(v)}
                  className="text-xs opacity-60 hover:opacity-100"
                  style={{ color: isDefault ? "var(--primary-soft-fg)" : "var(--fg-subtle)" }}
                  title={isDefault ? "默认 collection 不能删, 先设别的为默认" : "移除"}
                  disabled={isDefault && list.length <= 1}
                >
                  ✕
                </button>
              )}
            </span>
          );
        })}
      </div>
      <div className="flex gap-1">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          placeholder="新 collection (Enter 添加)"
          className="flex-1 px-2 py-1 rounded-md text-xs outline-none font-mono"
          style={{
            background: "var(--bg-elev-2)",
            color: "var(--fg)",
            border: "1px solid var(--border)",
          }}
        />
        <button
          type="button"
          onClick={add}
          disabled={!draft.trim()}
          className="px-2 rounded-md text-xs disabled:opacity-40"
          style={{
            background: "var(--primary)",
            color: "white",
          }}
        >
          ＋
        </button>
      </div>
    </div>
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
        className="text-[11px] font-semibold block mb-1"
        style={{ color: "var(--fg-muted)" }}
      >
        {label}
      </label>
      {children}
      {hint && (
        <div className="text-[10px] mt-1 leading-snug" style={{ color: "var(--fg-subtle)" }}>
          {hint}
        </div>
      )}
    </div>
  );
}
