"use client";

import { useEffect, useRef, useState } from "react";
import type { Session, Settings } from "../lib/types";
import { useAgent } from "../hooks/useAgent";
import { MessageBubble } from "./MessageBubble";

const EXAMPLES = [
  "现在几点？",
  "Calculate sqrt(144) + 23 * 47",
  "用一首五言绝句解释 RAG",
  "北京时间几点然后算 99×88",
];

export function ChatPanel({
  session,
  settings,
  onSessionStats,
  onTitleHint,
}: {
  session: Session | null;
  settings: Settings;
  onSessionStats: (cost: number, newMsgs: number) => void;
  onTitleHint?: (title: string) => void;
}) {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { messages, streaming, send, stop } = useAgent({
    sessionId: session?.id ?? null,
    settings,
    onSessionStats: (r) => onSessionStats(r.totalCostUsd, r.newMessages),
  });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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
    await send(text);
  }

  return (
    <div className="flex-1 flex flex-col bg-neutral-50/50">
      {/* Header */}
      <div className="px-6 py-3 border-b border-neutral-200 bg-white">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-semibold text-sm">
              {session?.title ?? "未选会话"}
            </h2>
            <div className="text-[10px] text-neutral-500 mt-0.5 font-mono">
              {settings.model}
              {session && session.totalCostUsd > 0 && (
                <span className="ml-3">
                  累计 ${session.totalCostUsd.toFixed(4)}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4 max-w-3xl w-full mx-auto">
        {messages.length === 0 && (
          <div className="text-center py-16 text-neutral-400">
            <div className="text-sm mb-3">点击试试 ↓</div>
            <div className="flex flex-wrap gap-2 justify-center max-w-md mx-auto">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => handleSend(ex)}
                  className="text-xs px-3 py-1.5 rounded-full bg-white border border-neutral-200 hover:border-blue-400 hover:text-blue-600 transition"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => (
          <MessageBubble key={m.id} msg={m} />
        ))}

        {streaming &&
          (messages.length === 0 ||
            messages[messages.length - 1]?.role === "user") && (
            <div className="text-xs text-neutral-400 italic px-2">
              Thinking...
            </div>
          )}

        <div ref={messagesEndRef} />
      </div>

      {/* Composer */}
      <div className="border-t border-neutral-200 bg-white p-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend(input);
            setInput("");
          }}
          className="max-w-3xl mx-auto flex gap-2"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="问点什么..."
            disabled={streaming}
            autoFocus
            className="flex-1 px-4 py-2.5 border border-neutral-300 rounded-xl text-sm focus:outline-none focus:border-blue-500 disabled:opacity-50"
          />
          {streaming ? (
            <button
              type="button"
              onClick={stop}
              className="px-5 py-2.5 rounded-xl bg-red-100 text-red-700 text-sm font-semibold hover:bg-red-200"
            >
              停止
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim()}
              className="px-5 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 disabled:bg-neutral-300 disabled:cursor-not-allowed"
            >
              发送
            </button>
          )}
        </form>
      </div>
    </div>
  );
}
