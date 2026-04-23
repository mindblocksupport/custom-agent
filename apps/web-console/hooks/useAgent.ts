"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { parseSseStream } from "../lib/sse";
import { loadMessages, saveMessages } from "../lib/storage";
import type {
  ApiMessage,
  Settings,
  ToolInvocation,
  UiMessage,
} from "../lib/types";

interface SendResult {
  totalCostUsd: number;
  newMessages: number;
}

export function useAgent({
  sessionId,
  settings,
  onSessionStats,
}: {
  sessionId: string | null;
  settings: Settings;
  onSessionStats?: (r: SendResult) => void;
}): {
  messages: UiMessage[];
  streaming: boolean;
  send: (text: string) => Promise<void>;
  stop: () => void;
  reset: () => void;
} {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  // 加载持久化消息
  useEffect(() => {
    if (sessionId) setMessages(loadMessages(sessionId));
  }, [sessionId]);

  const persist = useCallback(
    (msgs: UiMessage[]) => {
      if (sessionId) saveMessages(sessionId, msgs);
    },
    [sessionId],
  );

  const reset = useCallback(() => {
    setMessages([]);
    if (sessionId) saveMessages(sessionId, []);
  }, [sessionId]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const send = useCallback(
    async (text: string) => {
      if (!sessionId || !text.trim() || streaming) return;

      const userMsg: UiMessage = {
        id: crypto.randomUUID(),
        role: "user",
        text: text.trim(),
        blocks: [{ kind: "text", text: text.trim() }],
        createdAt: Date.now(),
      };

      // 构造发往后端的 OpenAI 兼容消息(只取 user/assistant/tool 真正对话内容)
      const apiMessages: ApiMessage[] = messages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m): ApiMessage => {
          if (m.role === "user") {
            return { role: "user", content: m.text ?? "" };
          }
          // assistant: 拼接所有 text block
          const txt = m.blocks
            .filter((b) => b.kind === "text")
            .map((b) => (b.kind === "text" ? b.text : ""))
            .join("");
          return { role: "assistant", content: txt };
        });
      apiMessages.push({ role: "user", content: text.trim() });

      // UI: append user + 空 assistant 占位
      const assistantMsg: UiMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        blocks: [],
        createdAt: Date.now(),
      };
      const initial = [...messages, userMsg, assistantMsg];
      setMessages(initial);
      persist(initial);
      setStreaming(true);

      const ctrl = new AbortController();
      abortRef.current = ctrl;

      try {
        const headers: Record<string, string> = {
          "Content-Type": "application/json",
          Authorization: `Bearer ${settings.apiKey}`,
        };
        // 同源走 /api/chat 代理(Next route),否则直连 settings.baseUrl
        const url = settings.baseUrl
          ? `${settings.baseUrl.replace(/\/$/, "")}/v1/chat/completions`
          : "/api/chat";

        const res = await fetch(url, {
          method: "POST",
          headers,
          body: JSON.stringify({
            messages: apiMessages,
            model: settings.model,
            stream: true,
          }),
          signal: ctrl.signal,
        });

        if (!res.ok || !res.body) {
          const txt = await res.text().catch(() => "");
          throw new Error(`HTTP ${res.status}: ${txt.slice(0, 120)}`);
        }

        // 局部可变状态(引用 assistantMsg.id)
        const tools = new Map<string, ToolInvocation>(); // tool_call_id → invocation
        let activeAssistantId = assistantMsg.id;
        let activeText = "";

        const updateAssistant = (mutator: (m: UiMessage) => UiMessage) => {
          setMessages((prev) => {
            const next = prev.map((m) =>
              m.id === activeAssistantId ? mutator(m) : m,
            );
            persist(next);
            return next;
          });
        };

        const ensureTextBlock = () => {
          updateAssistant((m) => {
            const last = m.blocks[m.blocks.length - 1];
            if (last && last.kind === "text") return m;
            return { ...m, blocks: [...m.blocks, { kind: "text", text: "" }] };
          });
        };

        const appendToken = (t: string) => {
          activeText += t;
          updateAssistant((m) => {
            const blocks = [...m.blocks];
            const last = blocks[blocks.length - 1];
            if (!last || last.kind !== "text") {
              blocks.push({ kind: "text", text: t });
            } else {
              blocks[blocks.length - 1] = { kind: "text", text: last.text + t };
            }
            return { ...m, blocks };
          });
        };

        let totalCostUsd = 0;

        await parseSseStream(res.body, {
          onEvent: (ev) => {
            switch (ev.type) {
              case "start":
                // could emit notice
                break;
              case "token":
                ensureTextBlock();
                appendToken(ev.text);
                break;
              case "tool_call": {
                activeText = "";
                const invId = crypto.randomUUID();
                const inv: ToolInvocation = {
                  id: invId,
                  callId: ev.data.id,
                  name: ev.data.name,
                  argumentsRaw: ev.data.arguments,
                  status: "running",
                };
                if (ev.data.id) tools.set(ev.data.id, inv);
                updateAssistant((m) => ({
                  ...m,
                  blocks: [...m.blocks, { kind: "tool", invocation: inv }],
                }));
                break;
              }
              case "tool_result": {
                const found = ev.data.id ? tools.get(ev.data.id) : null;
                const updated: ToolInvocation = {
                  id: found?.id ?? crypto.randomUUID(),
                  callId: ev.data.id,
                  name: ev.data.name,
                  argumentsRaw: found?.argumentsRaw ?? "",
                  status: ev.data.error ? "error" : "ok",
                  ...(ev.data.result !== null && ev.data.result !== undefined
                    ? { result: ev.data.result }
                    : {}),
                  ...(ev.data.error !== null && ev.data.error !== undefined
                    ? { error: ev.data.error }
                    : {}),
                };
                if (ev.data.id) tools.set(ev.data.id, updated);
                updateAssistant((m) => ({
                  ...m,
                  blocks: m.blocks.map((b) =>
                    b.kind === "tool" && b.invocation.id === updated.id
                      ? { kind: "tool", invocation: updated }
                      : b,
                  ),
                }));
                break;
              }
              case "done":
                totalCostUsd = ev.data.cost_usd;
                updateAssistant((m) => ({ ...m, done: ev.data }));
                break;
              case "error":
                updateAssistant((m) => ({ ...m, error: ev.text }));
                break;
            }
          },
          onError: (msg) => {
            updateAssistant((m) => ({ ...m, error: `Stream error: ${msg}` }));
          },
        });

        onSessionStats?.({ totalCostUsd, newMessages: 2 });
      } catch (e: unknown) {
        if ((e as { name?: string }).name === "AbortError") {
          // stop() called
        } else {
          const msg = e instanceof Error ? e.message : String(e);
          setMessages((prev) => {
            const next = prev.map((m) =>
              m.id === assistantMsg.id ? { ...m, error: msg } : m,
            );
            persist(next);
            return next;
          });
        }
      } finally {
        setStreaming(false);
        abortRef.current = null;
      }
    },
    [messages, persist, sessionId, settings.apiKey, settings.baseUrl, settings.model, streaming, onSessionStats],
  );

  return { messages, streaming, send, stop, reset };
}
