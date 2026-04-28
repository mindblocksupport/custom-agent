"use client";

import { useState } from "react";
import { toast } from "../lib/ui";
import type { UiMessage } from "../lib/types";
import { Markdown } from "./Markdown";
import { ToolCard } from "./ToolCard";

const ROUTE_LABEL: Record<string, string> = {
  default_short: "短问→快模型",
  reasoning_keyword: "推理→强模型",
  long_query: "长上下文→强模型",
  tool_calling: "工具循环→快模型",
  explicit: "指定模型",
  force: "强制模型",
};

export function MessageBubble({
  msg,
  isLast,
  onRegenerate,
  onInspect,
  onFork,
}: {
  msg: UiMessage;
  isLast?: boolean;
  onRegenerate?: () => void;
  onInspect?: () => void;
  onFork?: () => void;
}) {
  if (msg.role === "user") {
    const hasAttachments = !!(msg.attachments && msg.attachments.length > 0);
    return (
      <div className="flex justify-end gap-2 group animate-in">
        <div className="flex flex-col items-end max-w-[80%]">
          {hasAttachments && (
            <div className="flex gap-1.5 mb-1.5 flex-wrap justify-end">
              {msg.attachments!.map((a) => (
                <a
                  key={a.id}
                  href={a.dataUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block rounded-lg overflow-hidden transition"
                  style={{
                    border: "1px solid var(--border)",
                    boxShadow: "var(--shadow-sm)",
                  }}
                  title={`${a.filename} · 点击查看大图`}
                >
                  <img
                    src={a.dataUrl}
                    alt={a.filename}
                    className="block object-cover hover:opacity-90 transition"
                    style={{ maxWidth: 220, maxHeight: 220 }}
                  />
                </a>
              ))}
            </div>
          )}
          {(msg.text || !hasAttachments) && (
            <div
              className="px-3.5 py-2 rounded-2xl text-sm whitespace-pre-wrap break-words leading-relaxed"
              style={{
                background: "var(--primary)",
                color: "var(--fg-on-primary)",
                borderTopRightRadius: "6px",
                boxShadow: "var(--shadow-sm)",
              }}
            >
              {msg.text || (hasAttachments ? "(图片)" : "")}
            </div>
          )}
          <UserActions text={msg.text ?? ""} />
        </div>
        <Avatar role="user" />
      </div>
    );
  }

  return (
    <div className="flex justify-start gap-2 group animate-in">
      <Avatar role="assistant" />
      <div className="max-w-[85%] flex flex-col gap-1.5 min-w-0">
        {msg.blocks.length === 0 && !msg.error && (
          <div
            className="px-3.5 py-2 rounded-2xl text-sm italic"
            style={{
              background: "var(--bg-elev)",
              border: "1px solid var(--border)",
              color: "var(--fg-subtle)",
              borderTopLeftRadius: "6px",
            }}
          >
            <span className="typing-dots">思考中</span>
          </div>
        )}
        {msg.blocks.map((b, i) =>
          b.kind === "text" ? (
            <div
              key={i}
              className="px-3.5 py-2 rounded-2xl text-sm break-words leading-relaxed"
              style={{
                background: "var(--bg-elev)",
                border: "1px solid var(--border)",
                color: "var(--fg)",
                borderTopLeftRadius: "6px",
                boxShadow: "var(--shadow-sm)",
              }}
            >
              <Markdown>{b.text}</Markdown>
            </div>
          ) : (
            <ToolCard key={i} inv={b.invocation} />
          ),
        )}
        {msg.error && (
          <div
            className="px-3 py-2 rounded-md text-xs flex items-start gap-2"
            style={{
              background: "var(--danger-soft)",
              color: "var(--danger-soft-fg)",
              border: "1px solid var(--danger)",
            }}
          >
            <span>❌</span>
            <span className="break-all flex-1">{msg.error}</span>
          </div>
        )}
        <AssistantActions
          msg={msg}
          isLast={isLast}
          onRegenerate={onRegenerate}
          onInspect={onInspect}
          onFork={onFork}
        />
        {msg.done && <MessageMeta msg={msg} />}
      </div>
    </div>
  );
}

function Avatar({ role }: { role: "user" | "assistant" }) {
  if (role === "user") {
    return (
      <div
        className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold shrink-0 mt-0.5"
        style={{
          background: "var(--primary-soft)",
          color: "var(--primary-soft-fg)",
        }}
      >
        我
      </div>
    );
  }
  return (
    <div
      className="w-7 h-7 rounded-full flex items-center justify-center text-xs shrink-0 mt-0.5"
      style={{
        background: "linear-gradient(135deg, var(--primary), var(--accent))",
        color: "white",
      }}
    >
      🤖
    </div>
  );
}

function UserActions({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="opacity-0 group-hover:opacity-100 transition flex gap-1 mt-1">
      <ActionBtn
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(text);
            setCopied(true);
            setTimeout(() => setCopied(false), 1200);
          } catch {
            toast.error("复制失败");
          }
        }}
        title="复制内容"
      >
        {copied ? "✓ 已复制" : "📋"}
      </ActionBtn>
    </div>
  );
}

function AssistantActions({
  msg,
  isLast,
  onRegenerate,
  onInspect,
  onFork,
}: {
  msg: UiMessage;
  isLast?: boolean;
  onRegenerate?: () => void;
  onInspect?: () => void;
  onFork?: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const text = msg.blocks
    .filter((b) => b.kind === "text")
    .map((b) => (b.kind === "text" ? b.text : ""))
    .join("\n\n");

  if (!text && !isLast) return null;
  return (
    <div className="opacity-0 group-hover:opacity-100 transition flex gap-1 mt-0.5">
      {text && (
        <ActionBtn
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(text);
              setCopied(true);
              setTimeout(() => setCopied(false), 1200);
            } catch {
              toast.error("复制失败");
            }
          }}
          title="复制 markdown 原文"
        >
          {copied ? "✓ 已复制" : "📋 复制"}
        </ActionBtn>
      )}
      {onRegenerate && (
        <ActionBtn onClick={onRegenerate} title="用相同问题重新生成 (替换本条)">
          🔄 重新生成
        </ActionBtn>
      )}
      {onInspect && msg.done && (
        <ActionBtn onClick={onInspect} title="查看本响应的工具/检索时间线">
          🔍 查看 trace
        </ActionBtn>
      )}
      {onFork && (
        <ActionBtn
          onClick={onFork}
          title="从这条消息分叉出一个新会话, 截止到此条的历史复制过去"
        >
          🌿 从此分叉
        </ActionBtn>
      )}
    </div>
  );
}

function ActionBtn({
  onClick,
  title,
  children,
}: {
  onClick: () => void;
  title?: string;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="text-[10px] px-1.5 py-0.5 rounded transition"
      style={{
        color: "var(--fg-subtle)",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = "var(--surface-hover)";
        e.currentTarget.style.color = "var(--fg)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "transparent";
        e.currentTarget.style.color = "var(--fg-subtle)";
      }}
    >
      {children}
    </button>
  );
}

function MessageMeta({ msg }: { msg: UiMessage }) {
  const [showTrace, setShowTrace] = useState(false);
  const routeLabel =
    msg.routeReason && (ROUTE_LABEL[msg.routeReason] ?? msg.routeReason);

  return (
    <div
      className="text-[10px] px-2 mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono"
      style={{ color: "var(--fg-subtle)" }}
    >
      <Pill title="agent 多步推理的步数" icon="🔁">
        推理 {msg.done!.steps} 步
      </Pill>
      {msg.done!.input_tokens !== undefined && (
        <Pill title="本次输入消耗 token">↑{msg.done!.input_tokens}</Pill>
      )}
      {msg.done!.output_tokens !== undefined && (
        <Pill title="本次输出生成 token">↓{msg.done!.output_tokens}</Pill>
      )}
      <Pill title="本次调用美元成本" icon="💵">
        ${msg.done!.cost_usd.toFixed(6)}
      </Pill>
      {msg.model && (
        <Pill title={`实际选用的模型: ${msg.model}`} icon="🧠">
          {msg.model.split("/").pop()}
        </Pill>
      )}
      {routeLabel && (
        <Pill
          title={`路由原因 (route_reason): ${msg.routeReason}`}
          icon="🧭"
          accent
        >
          {routeLabel}
        </Pill>
      )}
      {msg.traceId && (
        <button
          className="text-[10px] px-1.5 py-0.5 rounded transition"
          style={{
            color: "var(--fg-muted)",
            background: "var(--bg-elev-2)",
          }}
          onMouseEnter={(e) =>
            (e.currentTarget.style.background = "var(--surface-hover)")
          }
          onMouseLeave={(e) =>
            (e.currentTarget.style.background = "var(--bg-elev-2)")
          }
          onClick={() => {
            navigator.clipboard?.writeText(msg.traceId!);
            setShowTrace(true);
            setTimeout(() => setShowTrace(false), 1200);
          }}
          title="追踪 ID — 点击复制, 用于 Langfuse 排障"
        >
          {showTrace ? "✓ 已复制" : `🔍 ${msg.traceId.slice(0, 8)}`}
        </button>
      )}
    </div>
  );
}

function Pill({
  icon,
  title,
  children,
  accent,
}: {
  icon?: string;
  title: string;
  children: React.ReactNode;
  accent?: boolean;
}) {
  return (
    <span
      title={title}
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded"
      style={{
        background: accent ? "var(--accent-soft)" : "var(--bg-elev-2)",
        color: accent ? "var(--accent-soft-fg)" : "var(--fg-muted)",
      }}
    >
      {icon && <span className="text-[10px]">{icon}</span>}
      <span>{children}</span>
    </span>
  );
}
