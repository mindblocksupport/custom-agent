"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { downloadText, messagesToJson, messagesToMarkdown } from "../lib/export";
import { toast } from "../lib/ui";
import type {
  Session, Settings, Skill, UiMessage, UserAttachment,
} from "../lib/types";
import { useAgent } from "../hooks/useAgent";
import { useSkillVars } from "../hooks/useSkillVars";
import { MessageBubble } from "./MessageBubble";
import { SkillSelector } from "./SkillSelector";
import { SkillVarsModal } from "./SkillVarsModal";
import { StatusBar } from "./StatusBar";
import { TraceInspector } from "./TraceInspector";
import { Welcome } from "./Welcome";

const MAX_IMAGE_BYTES = 5 * 1024 * 1024; // 5 MB / image
const MAX_ATTACHMENTS = 4;

// 与后端 services/gateway/src/gateway/router.py _VISION_PATTERNS 保持一致
const VISION_PATTERNS = [
  "claude-3", "claude-sonnet-4", "claude-opus-4",
  "gpt-4o", "gpt-4-turbo", "gpt-4-vision", "gpt-5",
  "gemini-1.5", "gemini-2", "gemini-pro-vision",
  "qwen-vl", "qwen2-vl", "qwen2.5-vl",
  "internvl", "minicpm-v", "llava",
];

function isVisionCapable(model: string | null | undefined): boolean {
  if (!model || model === "auto") return false;
  const m = model.toLowerCase();
  return VISION_PATTERNS.some((p) => m.includes(p));
}

/** OpenAI 'high' detail: 512x512 tile ≈ 170 tokens, 85 base.
 * 我们没有图像 dimension (没解析); 用 base64 size 反推.
 * 经验: 1MB ≈ ~1500-2000 tokens (high detail).
 */
function estimateImageTokens(bytes: number): number {
  // base64 → 实际字节 / 1.33
  const realBytes = bytes / 1.33;
  // 估 ≈ 1500 tok / MB (保守)
  return Math.max(85, Math.round((realBytes / 1024 / 1024) * 1500 + 85));
}

type ModelGroup = "通用" | "👁 Vision";
const MODELS: Array<{
  id: string; label: string; icon: string; group: ModelGroup;
}> = [
  { id: "auto", label: "Auto · 智能路由", icon: "🧭", group: "通用" },
  { id: "deepseek/deepseek-chat", label: "DeepSeek (便宜)", icon: "💰", group: "通用" },
  { id: "anthropic/claude-sonnet-4-6", label: "Sonnet 4.6 (聪明+vision)", icon: "🧠", group: "👁 Vision" },
  { id: "gpt-4o-mini", label: "GPT-4o mini (vision)", icon: "👁", group: "👁 Vision" },
  { id: "gemini/gemini-2.0-flash-exp", label: "Gemini 2.0 Flash (vision)", icon: "✨", group: "👁 Vision" },
];

export function ChatPanel({
  session,
  settings,
  workspaceId,
  skills,
  activeSkillId,
  onSelectSkill,
  onSessionStats,
  onTitleHint,
  onModelChange,
  onOpenSidebar,
  onForkFromMessage,
  onOpenWorkspaceSettings,
}: {
  session: Session | null;
  settings: Settings;
  workspaceId: string | null;
  skills: Skill[];
  activeSkillId: string | null;
  onSelectSkill: (id: string | null) => void;
  onSessionStats: (cost: number, newMsgs: number) => void;
  onTitleHint?: (title: string) => void;
  onModelChange?: (model: string) => void;
  onOpenSidebar?: () => void;
  onForkFromMessage?: (
    sourceTitle: string,
    truncatedMessages: UiMessage[],
  ) => void;
  onOpenWorkspaceSettings?: () => void;
}) {
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<UserAttachment[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [inspectMsg, setInspectMsg] = useState<UiMessage | null>(null);
  const [varsModalOpen, setVarsModalOpen] = useState(false);

  const activeSkill = skills.find((s) => s.id === activeSkillId) ?? null;

  const skillVarsHook = useSkillVars({
    sessionId: session?.id ?? null,
    skillId: activeSkillId,
    systemPrompt: activeSkill?.system_prompt ?? null,
  });

  const { messages, streaming, send, stop, regenerate } = useAgent({
    sessionId: session?.id ?? null,
    settings,
    workspaceId,
    skillId: activeSkillId,
    skillVars: skillVarsHook.values,
    onSessionStats: (r) => onSessionStats(r.totalCostUsd, r.newMessages),
    onSendError: (info) => {
      if (info.code === "budget_exceeded" && onOpenWorkspaceSettings) {
        toast.warn(
          "预算已超 — 已拦截本次调用",
          info.message,
          12000,
        );
        setTimeout(() => {
          import("../lib/ui").then(({ confirmDialog }) => {
            confirmDialog({
              title: "调高预算?",
              description:
                info.message +
                "\n\n点确定打开工作空间设置, 修改预算字段并保存。",
              confirmText: "打开设置",
              cancelText: "稍后",
            }).then((ok) => {
              if (ok) onOpenWorkspaceSettings();
            });
          });
        }, 200);
      } else if (info.code === "model_not_allowed") {
        toast.warn("模型未授权", info.message, 8000);
      }
    },
    onBudgetWarn: (warning) => {
      // X-Budget-Warning: "daily=85%($0.85/$1.00); monthly=82%($82.00/$100.00)"
      toast.warn(
        "💸 预算告急",
        `已用 ${warning} — 仍可继续, 但建议看「成本看板」并考虑调高 budget`,
        7000,
      );
    },
  });

  // 自动滚动 (仅在用户在底部时)
  useLayoutEffect(() => {
    if (!autoScroll) return;
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, autoScroll]);

  // 监听用户主动滚动 → 离开底部时关闭自动滚动
  useEffect(() => {
    const el = scrollAreaRef.current;
    if (!el) return;
    const onScroll = () => {
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
      setAutoScroll(distance < 80);
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  // textarea 自动高度
  useEffect(() => {
    const t = textareaRef.current;
    if (!t) return;
    t.style.height = "auto";
    t.style.height = Math.min(t.scrollHeight, 220) + "px";
  }, [input]);

  async function handleSend(text: string, atts: UserAttachment[] = attachments) {
    const trimmed = text.trim();
    const hasAtt = atts.length > 0;
    if (!trimmed && !hasAtt) return;
    if (streaming) return;
    if (
      onTitleHint &&
      session &&
      session.title === "新会话" &&
      messages.length === 0 &&
      trimmed
    ) {
      onTitleHint(trimmed.slice(0, 24));
    }
    setAutoScroll(true);
    await send(trimmed, hasAtt ? atts : undefined);
    setAttachments([]);
  }

  // ---------- attachments ----------
  const ingestFiles = async (files: FileList | File[]) => {
    const arr = Array.from(files).filter((f) => f.type.startsWith("image/"));
    if (arr.length === 0) {
      toast.warn("仅支持图片附件");
      return;
    }
    const remaining = MAX_ATTACHMENTS - attachments.length;
    if (remaining <= 0) {
      toast.warn(`最多 ${MAX_ATTACHMENTS} 张图片`);
      return;
    }
    const accepted: UserAttachment[] = [];
    for (const f of arr.slice(0, remaining)) {
      if (f.size > MAX_IMAGE_BYTES) {
        toast.error(`${f.name} 超过 5MB 限制`);
        continue;
      }
      try {
        const dataUrl = await readFileAsDataUrl(f);
        accepted.push({
          id: crypto.randomUUID(),
          dataUrl,
          filename: f.name || "image",
          size: f.size,
          mime: f.type,
        });
      } catch (e) {
        toast.fromError(e, "读取失败");
      }
    }
    if (accepted.length > 0) {
      setAttachments((prev) => [...prev, ...accepted]);
    }
  };

  const removeAttachment = (id: string) =>
    setAttachments((prev) => prev.filter((a) => a.id !== id));

  // 全局粘贴: 当 composer 聚焦时, 监听 paste 事件
  useEffect(() => {
    const onPaste = async (e: ClipboardEvent) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      const files: File[] = [];
      for (let i = 0; i < items.length; i++) {
        const it = items[i];
        if (it && it.kind === "file") {
          const f = it.getAsFile();
          if (f && f.type.startsWith("image/")) files.push(f);
        }
      }
      if (files.length > 0) {
        e.preventDefault();
        await ingestFiles(files);
      }
    };
    const ta = textareaRef.current;
    ta?.addEventListener("paste", onPaste);
    return () => ta?.removeEventListener("paste", onPaste);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attachments.length]);

  const onComposerKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      const txt = input;
      setInput("");
      handleSend(txt);
    }
  };

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  // 最近一次调用的 cost (从 lastAssistant.done 拿; streaming 中没有)
  const lastCallCost = lastAssistant?.done?.cost_usd ?? null;

  return (
    <div
      className="flex-1 flex flex-col"
      style={{ background: "var(--bg)" }}
    >
      {/* Header */}
      <div
        className="px-5 py-2 border-b"
        style={{
          background: "var(--bg-elev)",
          borderColor: "var(--border)",
        }}
      >
        <div className="flex items-center justify-between gap-3 flex-wrap">
          {onOpenSidebar && (
            <button
              onClick={onOpenSidebar}
              className="md:hidden p-1.5 rounded transition shrink-0"
              style={{ color: "var(--fg-muted)" }}
              aria-label="打开侧栏"
              title="打开会话列表"
            >
              ☰
            </button>
          )}
          <div className="min-w-0 flex-1">
            <h2
              className="font-semibold text-sm truncate"
              style={{ color: "var(--fg)" }}
            >
              {session?.title ?? "未选会话"}
            </h2>
            <div
              className="text-[10px] mt-0.5 font-mono flex items-center gap-2"
              style={{ color: "var(--fg-subtle)" }}
            >
              {session && (
                <>
                  <span>{session.messageCount} 条消息</span>
                  {session.totalCostUsd > 0 && (
                    <span title="本会话累计成本">
                      · 累计 ${session.totalCostUsd.toFixed(4)}
                    </span>
                  )}
                  {lastCallCost !== null && lastCallCost > 0 && !streaming && (
                    <span
                      title="最近一次调用 cost"
                      className="px-1 rounded"
                      style={{
                        background: "var(--accent-soft)",
                        color: "var(--accent-soft-fg)",
                      }}
                    >
                      本次 ${lastCallCost.toFixed(6)}
                    </span>
                  )}
                </>
              )}
              {streaming && (
                <span
                  className="inline-flex items-center gap-1 ml-1"
                  style={{ color: "var(--primary)" }}
                >
                  <span
                    className="w-1.5 h-1.5 rounded-full animate-pulse-soft"
                    style={{ background: "var(--primary)" }}
                  />
                  生成中
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {session && messages.length > 0 && (
              <ExportMenu session={session} messages={messages} />
            )}
            <SkillSelector
              skills={skills}
              activeId={activeSkillId}
              currentWorkspaceId={workspaceId}
              onSelect={onSelectSkill}
            />

            {onModelChange && (
              <ModelPicker
                value={settings.model || "auto"}
                onChange={onModelChange}
              />
            )}

            <StatusBar apiKey={settings.apiKey} />
          </div>
        </div>
      </div>

      {/* Messages */}
      <div
        ref={scrollAreaRef}
        className="flex-1 overflow-y-auto"
        style={{ background: "var(--bg)" }}
      >
        <div className="max-w-3xl mx-auto p-5 space-y-4">
          {messages.length === 0 && (
            <Welcome
              onPick={handleSend}
              starterExamples={activeSkill?.starter_examples}
              skillName={activeSkill?.name}
            />
          )}

          {messages.map((m) => (
            <MessageBubble
              key={m.id}
              msg={m}
              isLast={m.id === lastAssistant?.id && !streaming}
              onRegenerate={
                m.id === lastAssistant?.id && !streaming
                  ? () => regenerate()
                  : undefined
              }
              onInspect={
                m.role === "assistant" ? () => setInspectMsg(m) : undefined
              }
              onFork={
                onForkFromMessage && m.role === "assistant" && session && !streaming
                  ? () => {
                      // 截至本条消息 (含) 的全部 history
                      const idx = messages.findIndex((x) => x.id === m.id);
                      if (idx < 0) return;
                      const truncated = messages.slice(0, idx + 1);
                      onForkFromMessage(session.title, truncated);
                    }
                  : undefined
              }
            />
          ))}

          {streaming &&
            (messages.length === 0 ||
              messages[messages.length - 1]?.role === "user") && (
              <div className="flex items-center gap-2 px-2">
                <div
                  className="w-7 h-7 rounded-full flex items-center justify-center text-xs"
                  style={{
                    background: "var(--accent-soft)",
                    color: "var(--accent-soft-fg)",
                  }}
                >
                  🤖
                </div>
                <div
                  className="text-xs italic typing-dots"
                  style={{ color: "var(--fg-subtle)" }}
                >
                  Thinking
                </div>
              </div>
            )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Scroll-to-bottom button */}
      {!autoScroll && messages.length > 0 && (
        <button
          onClick={() => {
            setAutoScroll(true);
            messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
          }}
          className="absolute bottom-28 right-8 z-20 px-3 py-1.5 rounded-full text-xs font-medium transition animate-in"
          style={{
            background: "var(--bg-elev)",
            color: "var(--fg)",
            border: "1px solid var(--border)",
            boxShadow: "var(--shadow-md)",
          }}
        >
          ↓ 回到底部
        </button>
      )}

      {/* Skill 变量 banner: skill.system_prompt 含 {{ var }} 但未填全 */}
      {activeSkill && skillVarsHook.required.length > 0 && (
        <div
          className="px-4 py-1.5 border-t flex items-center gap-2"
          style={{
            background: skillVarsHook.hasUnfilled
              ? "var(--warning-soft)"
              : "var(--success-soft)",
            color: skillVarsHook.hasUnfilled
              ? "var(--warning-soft-fg)"
              : "var(--success-soft-fg)",
            borderColor: "var(--border)",
          }}
        >
          <span>🪄</span>
          <span className="text-[11px] flex-1 truncate">
            Skill「{activeSkill.name}」用了{" "}
            <b>{skillVarsHook.required.length}</b> 个模板变量
            {skillVarsHook.hasUnfilled
              ? ` · 还有 ${skillVarsHook.missing.length} 个待填: ${skillVarsHook.missing.join(", ")}`
              : " · 已全部填好"}
          </span>
          <button
            onClick={() => setVarsModalOpen(true)}
            className="text-[11px] px-2 py-0.5 rounded font-medium"
            style={{
              background: "var(--bg-elev)",
              color: skillVarsHook.hasUnfilled
                ? "var(--warning-soft-fg)"
                : "var(--success-soft-fg)",
              border: `1px solid ${
                skillVarsHook.hasUnfilled
                  ? "var(--warning)"
                  : "var(--success)"
              }`,
            }}
          >
            {skillVarsHook.hasUnfilled ? "填变量" : "改变量"}
          </button>
        </div>
      )}

      {/* Composer */}
      <div
        className="border-t p-3 relative"
        style={{
          background: "var(--bg-elev)",
          borderColor: "var(--border)",
        }}
        onDragEnter={(e) => {
          if (e.dataTransfer.types.includes("Files")) {
            e.preventDefault();
            setIsDragging(true);
          }
        }}
        onDragOver={(e) => {
          if (e.dataTransfer.types.includes("Files")) {
            e.preventDefault();
          }
        }}
        onDragLeave={(e) => {
          if (e.currentTarget.contains(e.relatedTarget as Node)) return;
          setIsDragging(false);
        }}
        onDrop={async (e) => {
          e.preventDefault();
          setIsDragging(false);
          if (e.dataTransfer.files.length > 0) {
            await ingestFiles(e.dataTransfer.files);
          }
        }}
      >
        {isDragging && (
          <div
            className="absolute inset-0 z-10 flex items-center justify-center rounded-md pointer-events-none"
            style={{
              background: "var(--primary-soft)",
              border: "2px dashed var(--primary)",
              color: "var(--primary-soft-fg)",
            }}
          >
            <div className="text-sm font-semibold">📎 释放上传图片 (最多 4 张)</div>
          </div>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const txt = input;
            setInput("");
            handleSend(txt);
          }}
          className="max-w-3xl mx-auto"
        >
          {/* Vision 警告: 附件存在但选了非 vision 模型 (auto 不警告 — 后端会自动 promote) */}
          {attachments.length > 0 &&
            settings.model &&
            settings.model !== "auto" &&
            !isVisionCapable(settings.model) && (
              <div
                className="text-[11px] mb-2 px-2.5 py-1.5 rounded-md flex items-center gap-2"
                style={{
                  background: "var(--warning-soft)",
                  color: "var(--warning-soft-fg)",
                  border: "1px solid var(--warning)",
                }}
              >
                <span>⚠️</span>
                <span className="flex-1">
                  当前模型「<code className="font-mono">{settings.model.split("/").pop()}</code>」
                  不支持图片输入. 切到 vision-capable 模型 (claude-sonnet-4 / gpt-4o / gemini / qwen-vl)
                  或选 auto 让路由自动升级。
                </span>
                {onModelChange && (
                  <button
                    type="button"
                    onClick={() => onModelChange("auto")}
                    className="text-[10px] px-2 py-0.5 rounded font-medium shrink-0"
                    style={{
                      background: "var(--bg-elev)",
                      color: "var(--warning-soft-fg)",
                      border: "1px solid var(--warning)",
                    }}
                  >
                    用 auto
                  </button>
                )}
              </div>
            )}

          {/* 附件预览 */}
          {attachments.length > 0 && (
            <div className="flex gap-2 mb-2 flex-wrap">
              {attachments.map((a) => (
                <div
                  key={a.id}
                  className="relative rounded-md overflow-hidden group"
                  style={{
                    border: "1px solid var(--border)",
                    background: "var(--bg-elev-2)",
                  }}
                >
                  <img
                    src={a.dataUrl}
                    alt={a.filename}
                    className="block object-cover"
                    style={{ width: 72, height: 72 }}
                  />
                  <button
                    type="button"
                    onClick={() => removeAttachment(a.id)}
                    className="absolute top-0.5 right-0.5 w-5 h-5 rounded-full text-xs flex items-center justify-center transition opacity-0 group-hover:opacity-100"
                    style={{
                      background: "rgba(0,0,0,0.65)",
                      color: "white",
                    }}
                    title="移除"
                  >
                    ✕
                  </button>
                  <div
                    className="absolute bottom-0 left-0 right-0 text-[8px] font-mono truncate px-1 py-0.5"
                    style={{
                      background: "rgba(0,0,0,0.55)",
                      color: "white",
                    }}
                    title={`${a.filename} · ${(a.size / 1024).toFixed(1)} KB · 估 ~${estimateImageTokens(a.size)} tok`}
                  >
                    {(a.size / 1024).toFixed(0)}KB · ~{estimateImageTokens(a.size)}t
                  </div>
                </div>
              ))}
            </div>
          )}

          <div
            className="flex items-end gap-2 rounded-2xl p-2 transition"
            style={{
              background: "var(--bg-elev-2)",
              border: "1px solid var(--border)",
            }}
          >
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={streaming || attachments.length >= MAX_ATTACHMENTS}
              className="px-2 py-1.5 rounded-md text-base transition shrink-0 self-end disabled:opacity-30"
              style={{ color: "var(--fg-muted)" }}
              onMouseEnter={(e) => {
                if (!e.currentTarget.disabled)
                  e.currentTarget.style.background = "var(--surface-hover)";
              }}
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "transparent")
              }
              title="附加图片 (或拖拽 / 粘贴)"
            >
              📎
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={async (e) => {
                if (e.target.files && e.target.files.length > 0) {
                  await ingestFiles(e.target.files);
                  e.target.value = "";
                }
              }}
            />
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onComposerKey}
              placeholder={
                streaming
                  ? "正在生成中... 可点击「停止」中断"
                  : attachments.length > 0
                    ? "对图片说点什么..."
                    : "问点什么... (Enter 发送, Shift+Enter 换行, 拖/粘贴图片)"
              }
              disabled={streaming}
              autoFocus
              rows={1}
              className="flex-1 px-2 py-1.5 text-sm bg-transparent outline-none resize-none disabled:opacity-50 leading-relaxed"
              style={{ color: "var(--fg)", maxHeight: 220 }}
            />
            {streaming ? (
              <button
                type="button"
                onClick={stop}
                className="px-4 py-2 rounded-xl text-xs font-semibold transition shrink-0 self-end"
                style={{
                  background: "var(--danger-soft)",
                  color: "var(--danger-soft-fg)",
                  border: "1px solid var(--danger)",
                }}
              >
                ⏹ 停止
              </button>
            ) : (
              <button
                type="submit"
                disabled={!input.trim() && attachments.length === 0}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-white transition shrink-0 self-end disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1"
                style={{
                  background: "var(--primary)",
                  boxShadow: input.trim() || attachments.length > 0
                    ? "var(--shadow-sm)" : "none",
                }}
                onMouseEnter={(e) => {
                  if (input.trim() || attachments.length > 0)
                    e.currentTarget.style.background = "var(--primary-hover)";
                }}
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = "var(--primary)")
                }
              >
                发送 <span className="opacity-70">↵</span>
              </button>
            )}
          </div>
          <div
            className="text-[10px] mt-1.5 text-center font-mono"
            style={{ color: "var(--fg-subtle)" }}
          >
            {input.length > 0 && <span>{input.length} 字符 · </span>}
            {attachments.length > 0 && (
              <span>
                {attachments.length} 张图 (~
                {attachments.reduce((s, a) => s + estimateImageTokens(a.size), 0)} tok) ·{" "}
              </span>
            )}
            {streaming
              ? "可点 ⏹ 停止"
              : "Enter 发送 / Shift+Enter 换行 · ⌘K 命令面板 · 📎 / 拖 / 粘贴上图"}
          </div>
        </form>
      </div>

      <TraceInspector msg={inspectMsg} onClose={() => setInspectMsg(null)} />

      {activeSkill && (
        <SkillVarsModal
          open={varsModalOpen}
          onClose={() => setVarsModalOpen(false)}
          skillName={activeSkill.name}
          systemPromptTemplate={activeSkill.system_prompt}
          required={skillVarsHook.required}
          values={skillVarsHook.values}
          onSave={(next) => {
            skillVarsHook.update(next);
            setVarsModalOpen(false);
          }}
        />
      )}
    </div>
  );
}

function readFileAsDataUrl(f: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(r.result as string);
    r.onerror = () => reject(new Error("FileReader failed"));
    r.readAsDataURL(f);
  });
}

function ExportMenu({
  session,
  messages,
}: {
  session: Session;
  messages: UiMessage[];
}) {
  const [open, setOpen] = useState(false);
  const safeName = (session.title || "session").replace(
    /[^a-z0-9\u4e00-\u9fa5_-]+/gi, "_",
  );

  const exportMd = () => {
    try {
      downloadText(`${safeName}.md`, messagesToMarkdown(session, messages));
      toast.success("已导出 Markdown");
      setOpen(false);
    } catch (e) {
      toast.fromError(e, "导出失败");
    }
  };
  const exportJson = () => {
    try {
      downloadText(
        `${safeName}.json`,
        messagesToJson(session, messages),
        "application/json",
      );
      toast.success("已导出 JSON");
      setOpen(false);
    } catch (e) {
      toast.fromError(e, "导出失败");
    }
  };
  const copyMd = async () => {
    try {
      await navigator.clipboard.writeText(messagesToMarkdown(session, messages));
      toast.success("Markdown 已复制到剪贴板");
      setOpen(false);
    } catch (e) {
      toast.fromError(e, "复制失败");
    }
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="text-xs px-2 py-1.5 rounded-md transition flex items-center gap-1"
        style={{
          background: "var(--bg-elev-2)",
          color: "var(--fg-muted)",
          border: "1px solid var(--border)",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--primary)")}
        onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--border)")}
        title="导出本会话"
      >
        📥 导出 <span style={{ color: "var(--fg-subtle)" }}>▾</span>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div
            className="absolute z-20 mt-1 right-0 w-48 rounded-lg overflow-hidden animate-in"
            style={{
              background: "var(--bg-elev)",
              border: "1px solid var(--border)",
              boxShadow: "var(--shadow-lg)",
            }}
          >
            <ExportItem icon="📝" label="下载 Markdown (.md)" onClick={exportMd} />
            <ExportItem icon="🧾" label="下载 JSON (.json)" onClick={exportJson} />
            <ExportItem
              icon="📋"
              label="复制 Markdown 到剪贴板"
              onClick={copyMd}
            />
          </div>
        </>
      )}
    </div>
  );
}

function ExportItem({
  icon,
  label,
  onClick,
}: {
  icon: string;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left px-3 py-2 text-xs flex items-center gap-2 transition"
      style={{ color: "var(--fg)" }}
      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-hover)")}
      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
    >
      <span>{icon}</span>
      <span>{label}</span>
    </button>
  );
}

function ModelPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (m: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const cur = MODELS.find((m) => m.id === value);
  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="text-xs px-2.5 py-1.5 rounded-md font-mono transition flex items-center gap-1.5"
        style={{
          background: "var(--bg-elev-2)",
          color: "var(--fg)",
          border: "1px solid var(--border)",
        }}
        onMouseEnter={(e) =>
          (e.currentTarget.style.borderColor = "var(--primary)")
        }
        onMouseLeave={(e) =>
          (e.currentTarget.style.borderColor = "var(--border)")
        }
        title="选择 LLM 模型"
      >
        <span>{cur?.icon ?? "🧭"}</span>
        <span>{cur?.label.split(" ")[0] ?? value}</span>
        <span style={{ color: "var(--fg-subtle)" }}>▾</span>
      </button>
      {open && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setOpen(false)}
          />
          <div
            className="absolute z-20 mt-1 right-0 w-64 rounded-lg overflow-hidden animate-in"
            style={{
              background: "var(--bg-elev)",
              border: "1px solid var(--border)",
              boxShadow: "var(--shadow-lg)",
            }}
          >
            {(["通用", "👁 Vision"] as const).map((g) => (
              <div key={g}>
                <div
                  className="px-3 py-1 text-[9px] uppercase tracking-wide"
                  style={{
                    color: "var(--fg-subtle)",
                    background: "var(--bg-elev-2)",
                  }}
                >
                  {g}
                </div>
                {MODELS.filter((m) => m.group === g).map((m) => {
                  const isActive = m.id === value;
                  return (
                    <button
                      key={m.id}
                      onClick={() => {
                        onChange(m.id);
                        setOpen(false);
                      }}
                      className="w-full text-left px-3 py-2 text-xs transition flex items-center gap-2"
                      style={{
                        background: isActive ? "var(--primary-soft)" : "transparent",
                        color: isActive ? "var(--primary-soft-fg)" : "var(--fg)",
                      }}
                      onMouseEnter={(e) => {
                        if (!isActive)
                          e.currentTarget.style.background = "var(--surface-hover)";
                      }}
                      onMouseLeave={(e) => {
                        if (!isActive)
                          e.currentTarget.style.background = "transparent";
                      }}
                    >
                      <span>{m.icon}</span>
                      <span>{m.label}</span>
                      {isActive && <span className="ml-auto">✓</span>}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
