"use client";

import type { UiMessage } from "../lib/types";
import { ToolCard } from "./ToolCard";

export function MessageBubble({ msg }: { msg: UiMessage }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] px-4 py-2.5 rounded-2xl bg-blue-600 text-white text-sm whitespace-pre-wrap break-words">
          {msg.text}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] flex flex-col gap-1">
        {msg.blocks.length === 0 && !msg.error && (
          <div className="px-4 py-2.5 rounded-2xl bg-white border border-neutral-200 text-sm text-neutral-400 italic">
            ...
          </div>
        )}
        {msg.blocks.map((b, i) =>
          b.kind === "text" ? (
            <div
              key={i}
              className="px-4 py-2.5 rounded-2xl bg-white border border-neutral-200 text-sm whitespace-pre-wrap break-words leading-relaxed"
            >
              {b.text}
            </div>
          ) : (
            <ToolCard key={i} inv={b.invocation} />
          ),
        )}
        {msg.error && (
          <div className="px-3 py-2 rounded-md bg-red-50 border border-red-200 text-xs text-red-700">
            ❌ {msg.error}
          </div>
        )}
        {msg.done && (
          <div className="text-[10px] text-neutral-400 px-2 mt-1 flex gap-3 font-mono">
            <span>{msg.done.steps} steps</span>
            {msg.done.input_tokens !== undefined && (
              <span>↑ {msg.done.input_tokens}</span>
            )}
            {msg.done.output_tokens !== undefined && (
              <span>↓ {msg.done.output_tokens}</span>
            )}
            <span>${msg.done.cost_usd.toFixed(6)}</span>
          </div>
        )}
      </div>
    </div>
  );
}
