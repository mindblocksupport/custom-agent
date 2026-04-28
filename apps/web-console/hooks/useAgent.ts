"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { parseSseStream } from "../lib/sse";
import { loadMessages, saveMessages } from "../lib/storage";
import type {
  ApiMessage,
  ContentPart,
  Settings,
  ToolInvocation,
  UiMessage,
  UserAttachment,
} from "../lib/types";

interface SendResult {
  totalCostUsd: number;
  newMessages: number;
}

export interface SendErrorInfo {
  message: string;
  code?: string;
  detail?: unknown;
}

export function useAgent({
  sessionId,
  settings,
  workspaceId,
  skillId,
  skillVars,
  onSessionStats,
  onSendError,
  onBudgetWarn,
}: {
  sessionId: string | null;
  settings: Settings;
  workspaceId?: string | null;
  skillId?: string | null;
  /** {{ var }} → 替换值; 后端在注入 skill.system_prompt 前应用 */
  skillVars?: Record<string, string>;
  onSessionStats?: (r: SendResult) => void;
  /** 发送失败 (含业务 code, e.g. budget_exceeded) 时回调, 让上层弹 CTA */
  onSendError?: (info: SendErrorInfo) => void;
  /** 软警告: 后端 X-Budget-Warning header 存在时触发, 让上层 toast 友情提醒 */
  onBudgetWarn?: (warning: string) => void;
}): {
  messages: UiMessage[];
  streaming: boolean;
  send: (text: string, attachments?: UserAttachment[]) => Promise<void>;
  stop: () => void;
  reset: () => void;
  regenerate: () => Promise<void>;
} {
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

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
    async (
      text: string,
      attachments?: UserAttachment[],
      historyOverride?: UiMessage[],
    ) => {
      const trimmed = text.trim();
      const hasAttachments = !!(attachments && attachments.length > 0);
      if (!sessionId || streaming) return;
      if (!trimmed && !hasAttachments) return;

      const baseHistory = historyOverride ?? messages;

      const userMsg: UiMessage = {
        id: crypto.randomUUID(),
        role: "user",
        text: trimmed,
        blocks: [{ kind: "text", text: trimmed }],
        attachments: hasAttachments ? attachments : undefined,
        createdAt: Date.now(),
      };

      const apiMessages: ApiMessage[] = baseHistory
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m): ApiMessage => {
          if (m.role === "user") {
            // 历史消息: 如果有附件, 也按 multimodal 还原
            if (m.attachments && m.attachments.length > 0) {
              const parts: ContentPart[] = [];
              if (m.text) parts.push({ type: "text", text: m.text });
              for (const a of m.attachments) {
                parts.push({ type: "image_url", image_url: { url: a.dataUrl } });
              }
              return { role: "user", content: parts };
            }
            return { role: "user", content: m.text ?? "" };
          }
          const txt = m.blocks
            .filter((b) => b.kind === "text")
            .map((b) => (b.kind === "text" ? b.text : ""))
            .join("");
          return { role: "assistant", content: txt };
        });

      // 当前轮 user 消息
      if (hasAttachments) {
        const parts: ContentPart[] = [];
        if (trimmed) parts.push({ type: "text", text: trimmed });
        for (const a of attachments!) {
          parts.push({ type: "image_url", image_url: { url: a.dataUrl } });
        }
        apiMessages.push({ role: "user", content: parts });
      } else {
        apiMessages.push({ role: "user", content: trimmed });
      }

      const assistantMsg: UiMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        blocks: [],
        createdAt: Date.now(),
      };
      const initial = [...baseHistory, userMsg, assistantMsg];
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
            // v1.5: 让后端按 workspace + skill 路由 (system_prompt + 默认模型)
            ...(workspaceId ? { workspace_id: workspaceId } : {}),
            ...(skillId ? { skill_id: skillId } : {}),
            ...(skillVars && Object.keys(skillVars).length > 0
              ? { skill_vars: skillVars }
              : {}),
          }),
          signal: ctrl.signal,
        });

        if (!res.ok || !res.body) {
          const txt = await res.text().catch(() => "");
          // 后端用 detail dict 形式 → 优先抽 message
          let nice = txt.slice(0, 200);
          try {
            const j = JSON.parse(txt);
            if (j && typeof j === "object") {
              if (j.detail && typeof j.detail === "object" && j.detail.message) {
                nice = j.detail.message;
                // 把 detail.code 也透传出去, 让上层 UI 能区分 (e.g. budget_exceeded)
                const e: Error & { code?: string; detail?: unknown } = new Error(
                  `HTTP ${res.status}: ${nice}`,
                );
                e.code = j.detail.code;
                e.detail = j.detail;
                throw e;
              }
              if (typeof j.detail === "string") nice = j.detail;
            }
          } catch (parseErr) {
            // 如果是我们刚刚 throw 的扩展 Error, 重抛
            if (parseErr instanceof Error && (parseErr as { code?: string }).code) {
              throw parseErr;
            }
            // 否则忽略 JSON parse 错误, 用文本兜底
          }
          throw new Error(`HTTP ${res.status}: ${nice}`);
        }

        // Day 8: 从响应头吃 chat 元信息
        const traceId = res.headers.get("x-trace-id") || undefined;
        const routeReason = res.headers.get("x-route-reason") || undefined;
        const model = res.headers.get("x-model") || undefined;
        const sessionIdResp = res.headers.get("x-session-id") || undefined;
        const budgetWarn = res.headers.get("x-budget-warning") || undefined;
        if (budgetWarn && onBudgetWarn) {
          onBudgetWarn(budgetWarn);
        }

        const tools = new Map<string, ToolInvocation>();
        const activeAssistantId = assistantMsg.id;

        const updateAssistant = (mutator: (m: UiMessage) => UiMessage) => {
          setMessages((prev) => {
            const next = prev.map((m) =>
              m.id === activeAssistantId ? mutator(m) : m,
            );
            persist(next);
            return next;
          });
        };

        // 把 header 元信息塞 assistant msg
        updateAssistant((m) => ({
          ...m,
          traceId,
          routeReason,
          model,
          sessionId: sessionIdResp,
        }));

        const ensureTextBlock = () => {
          updateAssistant((m) => {
            const last = m.blocks[m.blocks.length - 1];
            if (last && last.kind === "text") return m;
            return { ...m, blocks: [...m.blocks, { kind: "text", text: "" }] };
          });
        };

        const appendToken = (t: string) => {
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

        // Day 8: 把 retrieval 富化字段 patch 到对应 invocation
        const updateInvocation = (
          callId: string | null | undefined,
          patch: Partial<ToolInvocation>,
        ) => {
          if (!callId) return;
          const inv = tools.get(callId);
          if (!inv) return;
          const merged = { ...inv, ...patch };
          tools.set(callId, merged);
          updateAssistant((m) => ({
            ...m,
            blocks: m.blocks.map((b) =>
              b.kind === "tool" && b.invocation.id === inv.id
                ? { kind: "tool", invocation: merged }
                : b,
            ),
          }));
        };

        let totalCostUsd = 0;

        await parseSseStream(res.body, {
          onEvent: (ev) => {
            switch (ev.type) {
              case "start":
                break;
              case "token":
                ensureTextBlock();
                appendToken(ev.text);
                break;
              case "tool_call": {
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
                  // 保留 retrieval 富化字段 (retrieval.done 已先到)
                  retrievalQuery: found?.retrievalQuery,
                  citations: found?.citations,
                  refused: found?.refused,
                  refusalReason: found?.refusalReason,
                  elapsedMs: found?.elapsedMs,
                  nDense: found?.nDense,
                  nBm25: found?.nBm25,
                  nRerankIn: found?.nRerankIn,
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
              case "retrieval.start":
                updateInvocation(ev.data.tool_call_id, {
                  retrievalQuery: ev.data.query,
                });
                break;
              case "retrieval.done":
                updateInvocation(ev.data.tool_call_id, {
                  citations: ev.data.citations,
                  refused: ev.data.refused,
                  refusalReason: ev.data.refusal_reason ?? null,
                  elapsedMs: ev.data.elapsed_ms ?? null,
                  nDense: ev.data.n_dense,
                  nBm25: ev.data.n_bm25,
                  nRerankIn: ev.data.n_rerank_in,
                });
                break;
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
          const errObj = e as { code?: string; detail?: unknown; message?: string };
          const msg = e instanceof Error ? e.message : String(e);
          setMessages((prev) => {
            const next = prev.map((m) =>
              m.id === assistantMsg.id ? { ...m, error: msg } : m,
            );
            persist(next);
            return next;
          });
          if (onSendError) {
            onSendError({
              message: msg,
              code: errObj.code,
              detail: errObj.detail,
            });
          }
        }
      } finally {
        setStreaming(false);
        abortRef.current = null;
      }
    },
    [
      messages,
      persist,
      sessionId,
      settings.apiKey,
      settings.baseUrl,
      settings.model,
      workspaceId,
      skillId,
      skillVars,
      streaming,
      onSessionStats,
      onSendError,
      onBudgetWarn,
    ],
  );

  /**
   * regenerate: 把最后一条 assistant 删掉, 用倒数第二条 user 重新发送一次.
   * 适合"答案不满意"场景.
   */
  const regenerate = useCallback(async () => {
    if (streaming) return;
    let lastUserIdx = -1;
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m && m.role === "user") {
        lastUserIdx = i;
        break;
      }
    }
    if (lastUserIdx === -1) return;
    const lastUserMsg = messages[lastUserIdx];
    if (!lastUserMsg) return;
    const lastUserText = lastUserMsg.text ?? "";
    if (!lastUserText.trim() && !lastUserMsg.attachments?.length) return;
    // 截断: 把 lastUser 及之后全部移除 (send 会把 user 重新加上)
    const truncated = messages.slice(0, lastUserIdx);
    setMessages(truncated);
    persist(truncated);
    await send(lastUserText, lastUserMsg.attachments, truncated);
  }, [messages, persist, send, streaming]);

  return { messages, streaming, send, stop, reset, regenerate };
}
