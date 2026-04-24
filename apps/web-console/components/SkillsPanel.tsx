"use client";

import { useMemo, useState } from "react";
import { confirmDialog, toast } from "../lib/ui";
import type { Skill } from "../lib/types";
import type { SkillCreatePayload, SkillUpdatePayload } from "../lib/api/skills";

const TOOLS = ["search_kb", "calculator", "get_time", "web_search"];

export function SkillsPanel({
  skills,
  currentWorkspaceId,
  onCreate,
  onUpdate,
  onRemove,
  onInstall,
  onRefresh,
}: {
  skills: Skill[];
  currentWorkspaceId: string | null;
  onCreate: (payload: SkillCreatePayload) => Promise<Skill>;
  onUpdate: (sid: string, payload: SkillUpdatePayload) => Promise<Skill>;
  onRemove: (sid: string) => Promise<void>;
  onInstall: (sourceSkillId: string) => Promise<Skill>;
  onRefresh: () => Promise<void>;
}) {
  const [editing, setEditing] = useState<Skill | "new" | null>(null);
  const [search, setSearch] = useState("");
  const [installing, setInstalling] = useState<string | null>(null);

  const own = useMemo(
    () =>
      skills
        .filter((s) => s.workspace_id === currentWorkspaceId)
        .filter(
          (s) =>
            !search ||
            s.name.toLowerCase().includes(search.toLowerCase()) ||
            s.description.toLowerCase().includes(search.toLowerCase()),
        ),
    [skills, currentWorkspaceId, search],
  );
  const market = useMemo(
    () =>
      skills
        .filter(
          (s) => s.workspace_id !== currentWorkspaceId && s.visibility === "public",
        )
        .filter(
          (s) =>
            !search ||
            s.name.toLowerCase().includes(search.toLowerCase()) ||
            s.description.toLowerCase().includes(search.toLowerCase()),
        ),
    [skills, currentWorkspaceId, search],
  );
  const ownNames = new Set(own.map((s) => s.name));

  const handleInstall = async (skill: Skill) => {
    setInstalling(skill.id);
    try {
      await onInstall(skill.id);
      toast.success("已安装", `「${skill.name}」复制到本工作空间`);
    } catch (e) {
      toast.fromError(e, "安装失败");
    } finally {
      setInstalling(null);
    }
  };

  const handleRemove = async (skill: Skill) => {
    const ok = await confirmDialog({
      title: `删除技能「${skill.name}」?`,
      description: "已绑定此技能的会话不受影响, 但后续将无法选择。",
      confirmText: "删除",
      danger: true,
    });
    if (!ok) return;
    try {
      await onRemove(skill.id);
      toast.success("已删除");
    } catch (e) {
      toast.fromError(e, "删除失败");
    }
  };

  return (
    <div className="flex-1 flex flex-col">
      <div
        className="p-3 border-b space-y-2"
        style={{ borderColor: "var(--border)" }}
      >
        <button
          onClick={() => setEditing("new")}
          disabled={!currentWorkspaceId}
          className="w-full text-sm py-1.5 px-3 rounded-lg font-medium transition flex items-center justify-center gap-1.5 disabled:opacity-40"
          style={{
            background: "linear-gradient(135deg, var(--primary), var(--accent))",
            color: "white",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          <span>＋</span> 新建技能
        </button>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="🔎 搜索技能..."
          className="w-full px-2.5 py-1.5 rounded-md text-xs outline-none"
          style={{
            background: "var(--bg-elev-2)",
            color: "var(--fg)",
            border: "1px solid transparent",
          }}
          onFocus={(e) => (e.currentTarget.style.borderColor = "var(--primary)")}
          onBlur={(e) => (e.currentTarget.style.borderColor = "transparent")}
        />
        {!currentWorkspaceId && (
          <div className="text-[10px]" style={{ color: "var(--fg-subtle)" }}>
            请先选一个 workspace
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto py-2 space-y-3">
        <Section title="本工作空间" icon="🗂️" count={own.length}>
          {own.length === 0 ? (
            <EmptyHint icon="🧩" text='点上方"+ 新建技能"或从市场安装 ↓' />
          ) : (
            own.map((s) => (
              <SkillRow
                key={s.id}
                skill={s}
                showRemove
                showEdit
                onRemove={() => handleRemove(s)}
                onEdit={() => setEditing(s)}
              />
            ))
          )}
        </Section>
        {market.length > 0 && (
          <Section title="🏪 市场 (一键复用)" icon="" count={market.length}>
            {market.map((s) => {
              const alreadyInstalled = ownNames.has(s.name);
              return (
                <SkillRow
                  key={s.id}
                  skill={s}
                  showInstall
                  installed={alreadyInstalled}
                  installing={installing === s.id}
                  onInstall={() => handleInstall(s)}
                />
              );
            })}
          </Section>
        )}
      </div>

      <div
        className="border-t p-2 text-center"
        style={{ borderColor: "var(--border)" }}
      >
        <button
          onClick={async () => {
            try {
              await onRefresh();
              toast.info("已刷新");
            } catch (e) {
              toast.fromError(e, "刷新失败");
            }
          }}
          className="text-[10px]"
          style={{ color: "var(--fg-subtle)" }}
        >
          ⟳ 刷新 ({own.length + market.length})
        </button>
      </div>

      {editing && currentWorkspaceId && (
        <SkillModal
          mode={editing === "new" ? "create" : "edit"}
          initial={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSave={async (payload) => {
            if (editing === "new") {
              // SkillModal 在 create 模式下保证 name 非空, 这里 cast 安全
              await onCreate(payload as SkillCreatePayload);
              toast.success("技能已创建");
            } else {
              await onUpdate(editing.id, payload);
              toast.success("已保存");
            }
            setEditing(null);
          }}
        />
      )}
    </div>
  );
}

function Section({
  title,
  icon,
  count,
  children,
}: {
  title: string;
  icon: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div
        className="px-3 py-1 text-[10px] uppercase tracking-wide flex items-center justify-between"
        style={{ color: "var(--fg-subtle)" }}
      >
        <span>
          {icon} {title}
        </span>
        <span className="font-mono">{count}</span>
      </div>
      {children}
    </div>
  );
}

function EmptyHint({ icon, text }: { icon: string; text: string }) {
  return (
    <div className="px-4 py-3 text-center">
      <div className="text-2xl opacity-40 mb-1">{icon}</div>
      <div className="text-xs" style={{ color: "var(--fg-subtle)" }}>
        {text}
      </div>
    </div>
  );
}

function SkillRow({
  skill,
  showRemove,
  showEdit,
  showInstall,
  installed,
  installing,
  onRemove,
  onEdit,
  onInstall,
}: {
  skill: Skill;
  showRemove?: boolean;
  showEdit?: boolean;
  showInstall?: boolean;
  installed?: boolean;
  installing?: boolean;
  onRemove?: () => void;
  onEdit?: () => void;
  onInstall?: () => void;
}) {
  const visBadge =
    skill.visibility === "public"
      ? { icon: "🌍", label: "public", c: "var(--info-soft-fg)", bg: "var(--info-soft)" }
      : skill.visibility === "private"
        ? { icon: "🔒", label: "private", c: "var(--fg-muted)", bg: "var(--bg-elev-2)" }
        : { icon: "🗂️", label: "workspace", c: "var(--accent-soft-fg)", bg: "var(--accent-soft)" };

  return (
    <div
      className="group mx-2 px-2 py-1.5 rounded-lg transition"
      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-hover)")}
      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
    >
      <div className="flex items-start gap-2">
        <div className="flex-1 min-w-0">
          <div
            className="text-sm font-medium truncate flex items-center gap-1.5 flex-wrap"
            style={{ color: "var(--fg)" }}
          >
            {skill.name}
            <span className="text-[9px]" style={{ color: "var(--fg-subtle)" }}>
              v{skill.version}
            </span>
            <span
              className="text-[9px] px-1 rounded inline-flex items-center gap-0.5"
              style={{ background: visBadge.bg, color: visBadge.c }}
            >
              {visBadge.icon} {visBadge.label}
            </span>
            {skill.tags.includes("official") && (
              <span
                className="text-[9px] px-1 rounded"
                style={{
                  background: "var(--warning-soft)",
                  color: "var(--warning-soft-fg)",
                }}
              >
                官方
              </span>
            )}
          </div>
          {skill.description && (
            <div
              className="text-[10px] truncate mt-0.5"
              style={{ color: "var(--fg-muted)" }}
            >
              {skill.description}
            </div>
          )}
          <div
            className="text-[9px] mt-0.5 font-mono truncate"
            style={{ color: "var(--fg-subtle)" }}
          >
            tools: {skill.allowed_tools.length === 0 ? "全部" : skill.allowed_tools.join(", ")}
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          {showInstall && onInstall && (
            installed ? (
              <span
                className="text-[10px] px-1.5"
                style={{ color: "var(--success-soft-fg)" }}
                title="同名 skill 已安装"
              >
                ✓ 已装
              </span>
            ) : (
              <button
                onClick={onInstall}
                disabled={installing}
                className="text-[10px] px-2 py-0.5 rounded-md transition disabled:opacity-50 font-medium"
                style={{
                  background: "var(--accent-soft)",
                  color: "var(--accent-soft-fg)",
                }}
                title="复制到本工作空间 (独立可改)"
              >
                {installing ? "..." : "📥 安装"}
              </button>
            )
          )}
          <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition">
            {showEdit && onEdit && (
              <button
                onClick={onEdit}
                className="text-xs px-1.5 transition"
                style={{ color: "var(--fg-subtle)" }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "var(--primary)")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "var(--fg-subtle)")}
                title="编辑"
              >
                ✎
              </button>
            )}
            {showRemove && onRemove && (
              <button
                onClick={onRemove}
                className="text-xs px-1.5 transition"
                style={{ color: "var(--fg-subtle)" }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "var(--danger)")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "var(--fg-subtle)")}
                title="删除"
              >
                ✕
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function SkillModal({
  mode,
  initial,
  onClose,
  onSave,
}: {
  mode: "create" | "edit";
  initial: Skill | null;
  onClose: () => void;
  onSave: (p: SkillCreatePayload | SkillUpdatePayload) => Promise<void>;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [systemPrompt, setSystemPrompt] = useState(initial?.system_prompt ?? "");
  const [tools, setTools] = useState<string[]>(initial?.allowed_tools ?? []);
  const [starterText, setStarterText] = useState(
    (initial?.starter_examples ?? []).join("\n"),
  );
  const [visibility, setVisibility] = useState<"private" | "workspace" | "public">(
    initial?.visibility ?? "workspace",
  );
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    if (!name.trim()) {
      setErr("名称不能为空");
      return;
    }
    setSubmitting(true);
    setErr(null);
    try {
      const payload: SkillCreatePayload = {
        name: name.trim(),
        description: description.trim(),
        system_prompt: systemPrompt.trim(),
        allowed_tools: tools,
        starter_examples: starterText
          .split("\n")
          .map((x) => x.trim())
          .filter(Boolean),
        visibility,
      };
      await onSave(payload);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-30 flex items-center justify-center px-4"
      style={{ background: "var(--bg-overlay)" }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-md max-h-[90vh] overflow-y-auto rounded-xl p-5 animate-modal"
        style={{
          background: "var(--bg-elev)",
          color: "var(--fg)",
          boxShadow: "var(--shadow-lg)",
          border: "1px solid var(--border)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="font-semibold text-base mb-3">
          🧩 {mode === "create" ? "新建技能" : `编辑「${initial?.name}」`}
        </h3>

        <div className="space-y-3 text-sm">
          <Field label="名称 *">
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="月报生成 / 合同审查 / ..."
              className="w-full px-2.5 py-1.5 rounded-md text-sm outline-none"
              style={{
                background: "var(--bg-elev-2)",
                color: "var(--fg)",
                border: "1px solid var(--border)",
              }}
            />
          </Field>

          <Field label="描述">
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="一句话说明这个技能干啥"
              className="w-full px-2.5 py-1.5 rounded-md text-sm outline-none"
              style={{
                background: "var(--bg-elev-2)",
                color: "var(--fg)",
                border: "1px solid var(--border)",
              }}
            />
          </Field>

          <Field label="System Prompt (定制系统提示)">
            <textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="例: 你是数据分析助手, 用 search_kb 找数据, 用 calculator 算指标..."
              rows={5}
              className="w-full px-2.5 py-1.5 rounded-md text-xs outline-none font-mono resize-y"
              style={{
                background: "var(--bg-elev-2)",
                color: "var(--fg)",
                border: "1px solid var(--border)",
              }}
            />
          </Field>

          <Field label="启动示例 (一行一条, 显示在欢迎页)">
            <textarea
              value={starterText}
              onChange={(e) => setStarterText(e.target.value)}
              placeholder="例:&#10;帮我生成本周月报&#10;对比上月数据"
              rows={3}
              className="w-full px-2.5 py-1.5 rounded-md text-xs outline-none resize-y"
              style={{
                background: "var(--bg-elev-2)",
                color: "var(--fg)",
                border: "1px solid var(--border)",
              }}
            />
          </Field>

          <Field label="允许的工具 (不勾 = 全部允许)">
            <div className="flex flex-wrap gap-1.5">
              {TOOLS.map((t) => {
                const checked = tools.includes(t);
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
                        setTools((prev) =>
                          e.target.checked
                            ? [...prev, t]
                            : prev.filter((x) => x !== t),
                        );
                      }}
                      className="hidden"
                    />
                    {t}
                  </label>
                );
              })}
            </div>
          </Field>

          <Field label="可见性">
            <select
              value={visibility}
              onChange={(e) => setVisibility(e.target.value as typeof visibility)}
              className="w-full px-2.5 py-1.5 rounded-md text-sm outline-none"
              style={{
                background: "var(--bg-elev-2)",
                color: "var(--fg)",
                border: "1px solid var(--border)",
              }}
            >
              <option value="private">🔒 private (只创建者用)</option>
              <option value="workspace">🗂️ workspace (本工作空间共享)</option>
              <option value="public">🌍 public (跨 workspace 市场可见)</option>
            </select>
          </Field>

          {err && (
            <div
              className="text-xs break-all px-2 py-1.5 rounded"
              style={{ background: "var(--danger-soft)", color: "var(--danger-soft-fg)" }}
            >
              {err}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2 mt-4">
          <button
            onClick={onClose}
            disabled={submitting}
            className="px-3.5 py-1.5 rounded-md text-sm transition"
            style={{
              color: "var(--fg-muted)",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-hover)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            取消
          </button>
          <button
            onClick={submit}
            disabled={submitting || !name.trim()}
            className="px-4 py-1.5 rounded-md text-sm font-semibold text-white disabled:opacity-40"
            style={{ background: "var(--primary)" }}
          >
            {submitting ? "保存中..." : mode === "create" ? "创建" : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div
        className="text-[11px] mb-1 font-semibold"
        style={{ color: "var(--fg-muted)" }}
      >
        {label}
      </div>
      {children}
    </div>
  );
}
