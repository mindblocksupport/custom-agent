"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { downloadText, messagesToMarkdown } from "../lib/export";
import { toast } from "../lib/ui";
import type { Session, Settings, Skill, UiMessage } from "../lib/types";
import { useAgent } from "../hooks/useAgent";
import { MessageBubble } from "./MessageBubble";
import { SkillSelector } from "./SkillSelector";
import { StatusBar } from "./StatusBar";
import { TraceInspector } from "./TraceInspector";
import { Welcome } from "./Welcome";

const MODELS = [
  { id: "auto", label: "Auto · 智能路由", icon: "🧭" },
  { id: "deepseek/deepseek-chat", label: "DeepSeek (便宜)", icon: "💰" },
  { id: "anthropic/claude-sonnet-4-6", label: "Sonnet 4.6 (聪明)", icon: "🧠" },
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
}) {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [inspectMsg, setInspectMsg] = useState<UiMessage | null>(null);

  const activeSkill = skills.find((s) => s.id === activeSkillId) ?? null;

  const { messages, streaming, send, stop, regenerate } = useAgent({
    sessionId: session?.id ?? null,
    settings,
    workspaceId,
    skillId: activeSkillId,
    onSessionStats: (r) => onSessionStats(r.totalCostUsd, r.newMessages),
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

  async function handleSend(text: string) {
    if (!text.trim() || streaming) return;
    if (
      onTitleHint &&
      session &&
      session.title === "新会话" &&
      messages.length === 0
    ) {
      onTitleHint(text.trim().slice(0, 24));
    }
    setAutoScroll(true);
    await send(text);
  }

  const onComposerKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter 发送, Shift+Enter 换行 (主流 chat 应用约定)
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      const txt = input;
      setInput("");
      handleSend(txt);
    }
  };

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");

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
              <button
                onClick={() => {
                  try {
                    const md = messagesToMarkdown(session, messages);
                    const safe = (session.title || "session").replace(/[^a-z0-9\u4e00-\u9fa5_-]+/gi, "_");
                    downloadText(`${safe}.md`, md);
                    toast.success("已导出 Markdown");
                  } catch (e) {
                    toast.fromError(e, "导出失败");
                  }
                }}
                className="text-xs px-2 py-1.5 rounded-md transition flex items-center gap-1"
                style={{
                  background: "var(--bg-elev-2)",
                  color: "var(--fg-muted)",
                  border: "1px solid var(--border)",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--primary)")}
                onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--border)")}
                title="导出本会话所有消息为 Markdown 文件"
              >
                📥 导出
              </button>
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

      {/* Composer */}
      <div
        className="border-t p-3"
        style={{
          background: "var(--bg-elev)",
          borderColor: "var(--border)",
        }}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const txt = input;
            setInput("");
            handleSend(txt);
          }}
          className="max-w-3xl mx-auto"
        >
          <div
            className="flex items-end gap-2 rounded-2xl p-2 transition"
            style={{
              background: "var(--bg-elev-2)",
              border: "1px solid var(--border)",
            }}
          >
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onComposerKey}
              placeholder={
                streaming
                  ? "正在生成中... 可点击「停止」中断"
                  : "问点什么... (Enter 发送, Shift+Enter 换行, 支持 Markdown)"
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
                disabled={!input.trim()}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-white transition shrink-0 self-end disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1"
                style={{
                  background: "var(--primary)",
                  boxShadow: input.trim() ? "var(--shadow-sm)" : "none",
                }}
                onMouseEnter={(e) => {
                  if (input.trim())
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
            {input.length > 0 && (
              <span>{input.length} 字符 · </span>
            )}
            {streaming
              ? "可点 ⏹ 停止"
              : "Enter 发送 / Shift+Enter 换行 · ⌘K 命令面板"}
          </div>
        </form>
      </div>

      <TraceInspector msg={inspectMsg} onClose={() => setInspectMsg(null)} />
    </div>
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
            className="absolute z-20 mt-1 right-0 w-56 rounded-lg overflow-hidden animate-in"
            style={{
              background: "var(--bg-elev)",
              border: "1px solid var(--border)",
              boxShadow: "var(--shadow-lg)",
            }}
          >
            {MODELS.map((m) => {
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
        </>
      )}
    </div>
  );
}
