"use client";

import { useMemo, useRef, useState } from "react";
import { useKb } from "../hooks/useKb";
import { confirmDialog, toast } from "../lib/ui";
import type { KbDoc, KbJob } from "../lib/types";

const STATUS_BADGE: Record<KbJob["status"], { bg: string; fg: string }> = {
  pending: { bg: "var(--bg-elev-2)", fg: "var(--fg-muted)" },
  parsing: { bg: "var(--info-soft)", fg: "var(--info-soft-fg)" },
  chunking: { bg: "var(--info-soft)", fg: "var(--info-soft-fg)" },
  embedding: { bg: "var(--info-soft)", fg: "var(--info-soft-fg)" },
  done: { bg: "var(--success-soft)", fg: "var(--success-soft-fg)" },
  failed: { bg: "var(--danger-soft)", fg: "var(--danger-soft-fg)" },
};

export function KbPanel({
  apiKey,
  workspaceId,
}: {
  apiKey: string;
  workspaceId?: string | null;
}) {
  const [filterCollection, setFilterCollection] = useState<string | null>(null);
  const {
    docs,
    loading,
    error,
    upload,
    remove,
    activeJobs,
    refresh,
    collections,
  } = useKb({
    apiKey,
    workspaceId,
    collection: filterCollection,
  });
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return docs;
    return docs.filter(
      (d) =>
        (d.title ?? "").toLowerCase().includes(q) ||
        d.source_uri.toLowerCase().includes(q),
    );
  }, [docs, search]);

  // 候选 collections: workspace.allowed ∪ used (兜底 default)
  const collectionChoices = useMemo(() => {
    const set = new Set<string>(["default"]);
    collections.allowed.forEach((c) => set.add(c));
    collections.used.forEach((c) => set.add(c));
    return [...set].sort();
  }, [collections]);

  const onSelectFile = async (file: File | undefined) => {
    if (!file) return;
    setUploading(true);
    try {
      const target = filterCollection ?? collections.default;
      const res = await upload(file, target);
      toast.info(
        "已开始解析",
        `${file.name} → ${res.collection}`,
        2500,
      );
    } catch (e) {
      toast.fromError(e, "上传失败");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div className="flex-1 flex flex-col">
      {/* Upload + collection */}
      <div
        className="p-3 border-b space-y-2"
        style={{ borderColor: "var(--border)" }}
      >
        <button
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
          className="w-full text-sm py-1.5 px-3 rounded-lg font-medium transition flex items-center justify-center gap-1.5 disabled:opacity-40"
          style={{
            background: "var(--success)",
            color: "white",
            boxShadow: "var(--shadow-sm)",
          }}
        >
          {uploading ? "上传中..." : <><span>＋</span> 上传文档</>}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.md,.txt,.markdown"
          className="hidden"
          onChange={(e) => onSelectFile(e.target.files?.[0])}
        />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="🔎 搜索文档..."
          className="w-full px-2.5 py-1.5 rounded-md text-xs outline-none"
          style={{
            background: "var(--bg-elev-2)",
            color: "var(--fg)",
            border: "1px solid transparent",
          }}
          onFocus={(e) => (e.currentTarget.style.borderColor = "var(--primary)")}
          onBlur={(e) => (e.currentTarget.style.borderColor = "transparent")}
        />
        <div className="flex items-center gap-1">
          <select
            value={filterCollection ?? ""}
            onChange={(e) =>
              setFilterCollection(e.target.value === "" ? null : e.target.value)
            }
            className="flex-1 text-xs px-2 py-1 rounded-md outline-none"
            style={{
              background: "var(--bg-elev-2)",
              color: "var(--fg)",
              border: "1px solid var(--border)",
            }}
            title="筛选 collection (上传也用此 collection)"
          >
            <option value="">全部 collections</option>
            {collectionChoices.map((c) => (
              <option key={c} value={c}>
                {c}
                {c === collections.default ? " · 默认" : ""}
              </option>
            ))}
          </select>
        </div>
        <div
          className="text-[10px] leading-relaxed"
          style={{ color: "var(--fg-subtle)" }}
        >
          支持: .md / .txt / .pdf (数字版) · 扫描件 OCR 待接入
        </div>
      </div>

      {/* Active jobs */}
      {activeJobs.length > 0 && (
        <div
          className="border-b px-3 py-2 space-y-1.5"
          style={{
            borderColor: "var(--border)",
            background: "var(--info-soft)",
          }}
        >
          <div
            className="text-[10px] uppercase tracking-wide"
            style={{ color: "var(--info-soft-fg)" }}
          >
            处理中 ({activeJobs.length})
          </div>
          {activeJobs.map((j) => (
            <JobRow key={j.id} job={j} />
          ))}
        </div>
      )}

      {/* Docs list */}
      <div className="flex-1 overflow-y-auto py-2">
        {loading && docs.length === 0 && (
          <div className="px-3 space-y-1.5">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 skeleton rounded-md" />
            ))}
          </div>
        )}
        {error && (
          <div
            className="text-xs px-3 py-2 break-all flex items-center gap-2"
            style={{ color: "var(--danger-soft-fg)" }}
          >
            <span>❌</span>
            <span className="flex-1">{error}</span>
            <button
              onClick={refresh}
              className="underline"
              style={{ color: "var(--primary)" }}
            >
              重试
            </button>
          </div>
        )}
        {!loading && filtered.length === 0 && !error && (
          <div className="px-3 py-8 text-center">
            <div className="text-3xl opacity-40 mb-2">📚</div>
            <div className="text-xs" style={{ color: "var(--fg-muted)" }}>
              {search
                ? "无匹配文档"
                : filterCollection
                  ? `「${filterCollection}」无文档`
                  : "知识库为空"}
            </div>
            {!search && (
              <div className="text-[11px] mt-1" style={{ color: "var(--fg-subtle)" }}>
                上传文档后, agent 用 search_kb 检索
              </div>
            )}
          </div>
        )}
        {filtered.map((d) => (
          <DocRow
            key={d.id}
            doc={d}
            onDelete={async () => {
              const ok = await confirmDialog({
                title: `删除「${d.title ?? d.source_uri}」?`,
                description: "文档及其所有 chunks 将不可检索。",
                confirmText: "删除",
                danger: true,
              });
              if (!ok) return;
              try {
                await remove(d.id);
                toast.success("已删除");
              } catch (e) {
                toast.fromError(e, "删除失败");
              }
            }}
          />
        ))}
      </div>

      {/* Footer */}
      <div
        className="border-t p-2 text-center"
        style={{ borderColor: "var(--border)" }}
      >
        <button
          onClick={refresh}
          className="text-[10px]"
          style={{ color: "var(--fg-subtle)" }}
        >
          ⟳ 刷新 ({docs.length})
        </button>
      </div>
    </div>
  );
}

function JobRow({ job }: { job: KbJob }) {
  const badge = STATUS_BADGE[job.status];
  return (
    <div className="text-[10px] font-mono">
      <div className="flex items-center justify-between">
        <span
          className="px-1.5 py-0.5 rounded"
          style={{ background: badge.bg, color: badge.fg }}
        >
          {job.status}
        </span>
        <span style={{ color: "var(--fg-muted)" }}>
          {job.progress}% · {job.stage ?? ""}
        </span>
      </div>
      <div
        className="h-1 mt-1 rounded-full overflow-hidden"
        style={{ background: "var(--surface-pressed)" }}
      >
        <div
          style={{
            width: `${job.progress}%`,
            height: "100%",
            background: "var(--primary)",
            transition: "width 0.3s",
          }}
        />
      </div>
      {job.error && (
        <div
          className="mt-0.5 break-all"
          style={{ color: "var(--danger-soft-fg)" }}
        >
          {job.error}
        </div>
      )}
      {job.status === "done" && job.chunks_created > 0 && (
        <div
          className="mt-0.5"
          style={{ color: "var(--success-soft-fg)" }}
        >
          ✓ +{job.chunks_created} chunks
          {job.chunks_reused > 0 && ` (${job.chunks_reused} reused)`}
        </div>
      )}
    </div>
  );
}

function DocRow({ doc, onDelete }: { doc: KbDoc; onDelete: () => void }) {
  return (
    <div
      className="group mx-2 px-2.5 py-2 rounded-lg transition"
      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-hover)")}
      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
    >
      <div className="flex items-center gap-2">
        <div className="flex-1 min-w-0">
          <div
            className="text-sm truncate"
            style={{ color: "var(--fg)" }}
            title={doc.source_uri}
          >
            {doc.title ?? doc.source_uri.split("/").pop() ?? "untitled"}
          </div>
          <div
            className="text-[10px] mt-0.5 flex gap-2 font-mono"
            style={{ color: "var(--fg-subtle)" }}
          >
            <span>{doc.chunk_count} chunks</span>
            <span>v{doc.current_version}</span>
            <span
              className="px-1 rounded"
              style={{
                background:
                  doc.collection === "default"
                    ? "var(--bg-elev-2)"
                    : "var(--accent-soft)",
                color:
                  doc.collection === "default"
                    ? "var(--fg-muted)"
                    : "var(--accent-soft-fg)",
              }}
            >
              {doc.collection}
            </span>
          </div>
        </div>
        <button
          onClick={onDelete}
          className="opacity-0 group-hover:opacity-100 text-xs px-1 transition"
          style={{ color: "var(--fg-subtle)" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--danger)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--fg-subtle)")}
          title="删除"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
