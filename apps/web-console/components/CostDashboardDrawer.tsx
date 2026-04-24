"use client";

import { useEffect, useMemo, useState } from "react";
import { MeApi, type WorkspaceUsage } from "../lib/api/me";
import { toast } from "../lib/ui";
import type { Session, Workspace } from "../lib/types";

/**
 * Cost dashboard: 真后端 /v1/workspaces/{wid}/usage 聚合数据.
 * Fallback: 后端调用失败时, 用 sidebar 已有 sessions 本地汇总.
 */
export function CostDashboardDrawer({
  open,
  onClose,
  workspace,
  sessions,
  apiKey,
}: {
  open: boolean;
  onClose: () => void;
  workspace: Workspace | null;
  sessions: Session[];
  apiKey: string;
}) {
  const [usage, setUsage] = useState<WorkspaceUsage | null>(null);
  const [days, setDays] = useState<7 | 14 | 30>(7);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !workspace || !apiKey) return;
    setLoading(true);
    const api = new MeApi(apiKey);
    api
      .workspaceUsage(workspace.id, days)
      .then(setUsage)
      .catch((e) => {
        toast.fromError(e, "加载用量失败");
        setUsage(null);
      })
      .finally(() => setLoading(false));
  }, [open, workspace, days, apiKey]);

  // 本地兜底数据 (后端没拿到时)
  const localFallback = useMemo(() => {
    const totalCost = sessions.reduce((s, x) => s + (x.totalCostUsd || 0), 0);
    const totalMsgs = sessions.reduce((s, x) => s + (x.messageCount || 0), 0);
    const top = [...sessions]
      .filter((s) => s.totalCostUsd > 0)
      .sort((a, b) => b.totalCostUsd - a.totalCostUsd)
      .slice(0, 5);
    return { totalCost, totalMsgs, top };
  }, [sessions]);

  const topSessions = useMemo(
    () =>
      [...sessions]
        .filter((s) => s.totalCostUsd > 0)
        .sort((a, b) => b.totalCostUsd - a.totalCostUsd)
        .slice(0, 5),
    [sessions],
  );

  if (!open) return null;

  const total = usage
    ? {
        cost: usage.total_cost_usd,
        messages: usage.total_messages,
        sessions: usage.total_sessions,
      }
    : {
        cost: localFallback.totalCost,
        messages: localFallback.totalMsgs,
        sessions: sessions.length,
      };

  // Daily 数据补齐 (按选择的 days 对齐)
  const dailyChart = useMemo(() => {
    const buckets: { day: string; messages: number; cost: number }[] = [];
    if (usage && usage.daily.length > 0) {
      const map = new Map(
        usage.daily.map((p) => [p.day, { msg: p.messages, cost: p.cost_usd }]),
      );
      const now = new Date();
      for (let i = days - 1; i >= 0; i--) {
        const d = new Date(now);
        d.setUTCDate(d.getUTCDate() - i);
        const key = d.toISOString().slice(0, 10);
        const v = map.get(key) ?? { msg: 0, cost: 0 };
        buckets.push({
          day: `${d.getMonth() + 1}/${d.getDate()}`,
          messages: v.msg,
          cost: v.cost,
        });
      }
    } else {
      // local fallback: 用 sessions.updatedAt 桶
      const now = Date.now();
      for (let i = days - 1; i >= 0; i--) {
        const t = new Date(now - i * 86400000);
        buckets.push({
          day: `${t.getMonth() + 1}/${t.getDate()}`,
          messages: 0,
          cost: 0,
        });
      }
      sessions.forEach((s) => {
        const ago = Math.floor((now - s.updatedAt) / 86400000);
        if (ago >= 0 && ago < days) {
          const idx = days - 1 - ago;
          const b = buckets[idx];
          if (b) {
            b.messages += s.messageCount;
            b.cost += s.totalCostUsd || 0;
          }
        }
      });
    }
    const maxCost = Math.max(0.000001, ...buckets.map((b) => b.cost));
    const maxMsg = Math.max(1, ...buckets.map((b) => b.messages));
    return { buckets, maxCost, maxMsg };
  }, [usage, days, sessions]);

  return (
    <div
      className="fixed inset-0 z-40 flex justify-end"
      style={{ background: "var(--bg-overlay)" }}
      onClick={onClose}
    >
      <div
        className="w-[32rem] max-w-full h-full flex flex-col animate-in"
        style={{
          background: "var(--bg-elev)",
          boxShadow: "var(--shadow-lg)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="px-4 py-3 border-b flex items-center justify-between"
          style={{ borderColor: "var(--border)" }}
        >
          <div>
            <div
              className="text-[10px] uppercase tracking-wide"
              style={{ color: "var(--fg-subtle)" }}
            >
              成本看板
            </div>
            <h2
              className="font-semibold text-base"
              style={{ color: "var(--fg)" }}
            >
              📊 {workspace?.name ?? "(no workspace)"}
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <div
              className="flex gap-0.5 rounded-md p-0.5"
              style={{ background: "var(--bg-elev-2)" }}
            >
              {([7, 14, 30] as const).map((d) => (
                <button
                  key={d}
                  onClick={() => setDays(d)}
                  className="px-2 py-0.5 text-[11px] rounded font-medium transition"
                  style={{
                    background: days === d ? "var(--bg-elev)" : "transparent",
                    color: days === d ? "var(--fg)" : "var(--fg-muted)",
                    boxShadow: days === d ? "var(--shadow-sm)" : "none",
                  }}
                >
                  {d}d
                </button>
              ))}
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
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-5">
          {/* KPI cards */}
          <div className="grid grid-cols-3 gap-2">
            <KpiCard
              label={`${days} 天消费`}
              value={`$${total.cost.toFixed(4)}`}
              icon="💵"
              loading={loading}
            />
            <KpiCard
              label="会话数"
              value={String(total.sessions)}
              icon="💬"
              loading={loading}
            />
            <KpiCard
              label="消息数"
              value={String(total.messages)}
              icon="📝"
              loading={loading}
            />
          </div>

          {/* 实时 (今日 + 当月) */}
          {usage && (
            <div className="grid grid-cols-2 gap-2">
              <KpiCard
                label="今日 (UTC)"
                value={`$${usage.today_cost_usd.toFixed(4)}`}
                icon="📅"
                accent
              />
              <KpiCard
                label="当月"
                value={`$${usage.month_cost_usd.toFixed(4)}`}
                icon="📈"
                accent
              />
            </div>
          )}

          {/* 预算 */}
          {(usage?.budget_daily_usd || usage?.budget_monthly_usd) && (
            <div>
              <SectionTitle>预算 (workspace 配额)</SectionTitle>
              <div className="space-y-2">
                {usage.budget_daily_usd && (
                  <BudgetBar
                    label="日预算"
                    used={usage.today_cost_usd}
                    total={usage.budget_daily_usd}
                  />
                )}
                {usage.budget_monthly_usd && (
                  <BudgetBar
                    label="月预算"
                    used={usage.month_cost_usd}
                    total={usage.budget_monthly_usd}
                  />
                )}
              </div>
            </div>
          )}

          {/* 趋势 */}
          <div>
            <SectionTitle>近 {days} 天活跃 (按消息生成日)</SectionTitle>
            <div
              className="flex items-end gap-0.5 h-28 px-1 py-2 rounded-md"
              style={{ background: "var(--bg-elev-2)" }}
            >
              {dailyChart.buckets.map((b) => {
                const h = (b.cost / dailyChart.maxCost) * 100;
                return (
                  <div
                    key={b.day}
                    className="flex-1 flex flex-col items-center gap-1 min-w-0"
                    title={`${b.day} · ${b.messages} 消息 · $${b.cost.toFixed(4)}`}
                  >
                    <div
                      className="w-full rounded-t transition-all"
                      style={{
                        height: `${h}%`,
                        minHeight: b.cost > 0 ? "3px" : "1px",
                        background:
                          b.cost > 0
                            ? "linear-gradient(to top, var(--primary), var(--accent))"
                            : "var(--surface-pressed)",
                      }}
                    />
                  </div>
                );
              })}
            </div>
            <div
              className="flex justify-between text-[9px] font-mono mt-1 px-1"
              style={{ color: "var(--fg-subtle)" }}
            >
              {dailyChart.buckets
                .filter((_, i, arr) => i === 0 || i === arr.length - 1 || i === Math.floor(arr.length / 2))
                .map((b) => (
                  <span key={b.day}>{b.day}</span>
                ))}
            </div>
          </div>

          {/* 模型成本拆分 */}
          {usage && usage.by_model.length > 0 && (
            <div>
              <SectionTitle>按模型拆分</SectionTitle>
              <div className="space-y-1.5">
                {usage.by_model.map((m) => {
                  const pct = total.cost > 0 ? (m.cost_usd / total.cost) * 100 : 0;
                  return (
                    <div
                      key={m.model}
                      className="rounded-md p-2"
                      style={{ background: "var(--bg-elev-2)" }}
                    >
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="font-mono truncate" style={{ color: "var(--fg)" }}>
                          {m.model.split("/").pop() ?? m.model}
                        </span>
                        <span className="font-mono" style={{ color: "var(--accent-soft-fg)" }}>
                          ${m.cost_usd.toFixed(4)}
                        </span>
                      </div>
                      <div
                        className="h-1 rounded-full overflow-hidden"
                        style={{ background: "var(--surface-pressed)" }}
                      >
                        <div
                          style={{
                            width: `${pct}%`,
                            height: "100%",
                            background: "linear-gradient(to right, var(--primary), var(--accent))",
                            transition: "width 0.3s",
                          }}
                        />
                      </div>
                      <div
                        className="flex justify-between text-[10px] font-mono mt-0.5"
                        style={{ color: "var(--fg-subtle)" }}
                      >
                        <span>{m.messages} 消息 · ↑{m.input_tokens} ↓{m.output_tokens}</span>
                        <span>{pct.toFixed(1)}%</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Top 会话 (本地) */}
          <div>
            <SectionTitle>消费 Top 5 会话 (sidebar 视图)</SectionTitle>
            {topSessions.length === 0 ? (
              <div
                className="text-xs italic px-2"
                style={{ color: "var(--fg-subtle)" }}
              >
                暂无消费数据
              </div>
            ) : (
              <div className="space-y-1.5">
                {topSessions.map((s, i) => (
                  <div
                    key={s.id}
                    className="flex items-center gap-2 px-2.5 py-1.5 rounded-md"
                    style={{ background: "var(--bg-elev-2)" }}
                  >
                    <span
                      className="text-[10px] font-mono w-4"
                      style={{ color: "var(--fg-subtle)" }}
                    >
                      #{i + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs truncate" style={{ color: "var(--fg)" }}>
                        {s.title}
                      </div>
                      <div
                        className="text-[10px] font-mono"
                        style={{ color: "var(--fg-subtle)" }}
                      >
                        {s.messageCount} 条 ·{" "}
                        {new Date(s.updatedAt).toLocaleDateString()}
                      </div>
                    </div>
                    <div
                      className="text-xs font-mono"
                      style={{ color: "var(--accent-soft-fg)" }}
                    >
                      ${s.totalCostUsd.toFixed(4)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div
            className="text-[10px] leading-relaxed pt-3 border-t"
            style={{
              color: "var(--fg-subtle)",
              borderColor: "var(--border)",
            }}
          >
            ℹ {usage
              ? "数据来自 chat_messages 实时聚合 (assistant 消息有成本) · 按 UTC 日切分"
              : "后端聚合不可用, 走本地 sessions 兜底"}
          </div>
        </div>
      </div>
    </div>
  );
}

function KpiCard({
  label,
  value,
  icon,
  accent,
  loading,
}: {
  label: string;
  value: string;
  icon: string;
  accent?: boolean;
  loading?: boolean;
}) {
  return (
    <div
      className="rounded-lg p-2.5 text-center"
      style={{
        background: accent ? "var(--accent-soft)" : "var(--bg-elev-2)",
        border: `1px solid ${accent ? "var(--accent)" : "var(--border)"}`,
      }}
    >
      <div className="text-xl mb-0.5">{icon}</div>
      <div
        className="text-[10px] uppercase tracking-wide"
        style={{ color: accent ? "var(--accent-soft-fg)" : "var(--fg-subtle)" }}
      >
        {label}
      </div>
      <div
        className="text-sm font-semibold font-mono mt-0.5"
        style={{ color: accent ? "var(--accent-soft-fg)" : "var(--fg)" }}
      >
        {loading ? "..." : value}
      </div>
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="text-[11px] font-semibold mb-2"
      style={{ color: "var(--fg-muted)" }}
    >
      {children}
    </div>
  );
}

function BudgetBar({
  label,
  used,
  total,
}: {
  label: string;
  used: number;
  total: number;
}) {
  const pct = Math.min(100, (used / total) * 100);
  const danger = pct > 80;
  return (
    <div>
      <div
        className="flex justify-between text-[10px] font-mono mb-0.5"
        style={{ color: "var(--fg-muted)" }}
      >
        <span>{label}</span>
        <span>
          ${used.toFixed(4)} / ${total.toFixed(2)}{" "}
          <span style={{ color: danger ? "var(--danger)" : "var(--fg-subtle)" }}>
            ({pct.toFixed(1)}%)
          </span>
        </span>
      </div>
      <div
        className="h-1.5 rounded-full overflow-hidden"
        style={{ background: "var(--surface-pressed)" }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: danger
              ? "var(--danger)"
              : "linear-gradient(to right, var(--primary), var(--accent))",
            transition: "width 0.3s",
          }}
        />
      </div>
    </div>
  );
}
