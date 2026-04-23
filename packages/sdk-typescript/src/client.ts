/**
 * Custom Agent Platform · TypeScript Client
 *
 * 用法:
 *   import { Client } from "@custom-agent/sdk";
 *
 *   const client = new Client({ apiKey: "..." });
 *   for await (const event of client.chat.completions.stream({
 *     messages: [{ role: "user", content: "hi" }],
 *     model: "deepseek/deepseek-chat",
 *   })) {
 *     if (event.type === "token") process.stdout.write(event.text);
 *   }
 */

import {
  AgentError,
  AuthError,
  RateLimitError,
  ServerError,
  StreamError,
  TimeoutError,
} from "./errors.js";
import { parseSSE } from "./sse.js";
import type {
  ChatCreateParams,
  ChatResponse,
  StreamEvent,
} from "./types.js";

const DEFAULT_BASE_URL = "http://localhost:8000";
const DEFAULT_TIMEOUT_MS = 120_000;

export interface ClientOptions {
  /** API Key. 缺省读 env CUSTOM_AGENT_API_KEY (Node) */
  apiKey?: string;
  /** Backend URL. 缺省 http://localhost:8000 或 env CUSTOM_AGENT_BASE_URL */
  baseUrl?: string;
  /** 不传 model 时用此默认值 */
  defaultModel?: string;
  /** 单请求超时 (ms),默认 120s */
  timeoutMs?: number;
  /** 自定义 fetch (测试用) */
  fetch?: typeof fetch;
}

export class Client {
  readonly apiKey: string;
  readonly baseUrl: string;
  readonly defaultModel?: string;
  readonly timeoutMs: number;
  private readonly _fetch: typeof fetch;

  readonly chat: Chat;

  constructor(options: ClientOptions = {}) {
    const apiKey = options.apiKey ?? readEnv("CUSTOM_AGENT_API_KEY");
    if (!apiKey) {
      throw new Error(
        "apiKey required (pass apiKey option or set CUSTOM_AGENT_API_KEY env var)",
      );
    }
    const baseUrl = (
      options.baseUrl ??
      readEnv("CUSTOM_AGENT_BASE_URL") ??
      DEFAULT_BASE_URL
    ).replace(/\/$/, "");

    this.apiKey = apiKey;
    this.baseUrl = baseUrl;
    if (options.defaultModel !== undefined) {
      this.defaultModel = options.defaultModel;
    }
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this._fetch = options.fetch ?? fetch;
    this.chat = new Chat(this);
  }

  /** 一句话便捷接口:吃 prompt,吐完整文本(忽略工具/进度细节)。 */
  async ask(
    prompt: string,
    options: { model?: string; system?: string } = {},
  ): Promise<string> {
    const messages: Array<{ role: "system" | "user"; content: string }> = [];
    if (options.system) messages.push({ role: "system", content: options.system });
    messages.push({ role: "user", content: prompt });

    const parts: string[] = [];
    const params: ChatCreateParams = { messages };
    if (options.model !== undefined) params.model = options.model;
    for await (const ev of this.chat.completions.stream(params)) {
      if (ev.type === "token") parts.push(ev.text);
      else if (ev.type === "error") throw new AgentError(ev.text);
    }
    return parts.join("");
  }

  /** 内部 - 给 Completions 用 */
  async _post(
    path: string,
    body: unknown,
    init: { stream?: boolean; signal?: AbortSignal } = {},
  ): Promise<Response> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    const signal = init.signal ?? controller.signal;

    try {
      const res = await this._fetch(this.baseUrl + path, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.apiKey}`,
          ...(init.stream ? { Accept: "text/event-stream" } : {}),
        },
        body: JSON.stringify(body),
        signal,
      });
      return res;
    } catch (err: unknown) {
      const e = err as { name?: string; message?: string };
      if (e.name === "AbortError") {
        throw new TimeoutError(`Request timed out after ${this.timeoutMs}ms`);
      }
      throw new AgentError(`Network error: ${e.message ?? String(err)}`);
    } finally {
      clearTimeout(timeout);
    }
  }
}

// ============================================================
// Chat namespace
// ============================================================
export class Chat {
  readonly completions: ChatCompletions;
  constructor(client: Client) {
    this.completions = new ChatCompletions(client);
  }
}

export class ChatCompletions {
  constructor(private readonly client: Client) {}

  /** OpenAI 兼容 - 非流式 */
  async create(params: ChatCreateParams): Promise<ChatResponse> {
    const body = this.buildBody(params, false);
    const res = await this.client._post("/v1/chat/completions", body);
    if (!res.ok) await throwForStatus(res);
    return (await res.json()) as ChatResponse;
  }

  /** OpenAI 兼容 - SSE 流式 (返回 typed AsyncIterable) */
  async *stream(params: ChatCreateParams): AsyncGenerator<StreamEvent, void, void> {
    const body = this.buildBody(params, true);
    const res = await this.client._post("/v1/chat/completions", body, { stream: true });
    if (!res.ok) await throwForStatus(res);
    if (!res.body) {
      throw new StreamError("response has no body");
    }
    for await (const sse of parseSSE(res.body)) {
      if (sse.data === "[DONE]") continue;
      let parsed: StreamEvent;
      try {
        parsed = JSON.parse(sse.data) as StreamEvent;
      } catch (e) {
        throw new StreamError(`Invalid JSON in SSE data: ${sse.data.slice(0, 80)}`);
      }
      yield parsed;
    }
  }

  private buildBody(p: ChatCreateParams, stream: boolean): Record<string, unknown> {
    const m = p.model ?? this.client.defaultModel;
    const body: Record<string, unknown> = { messages: p.messages, stream };
    if (m !== undefined) body.model = m;
    if (p.temperature !== undefined) body.temperature = p.temperature;
    if (p.max_tokens !== undefined) body.max_tokens = p.max_tokens;
    if (p.metadata !== undefined) body.metadata = p.metadata;
    return body;
  }
}

// ============================================================
// 内部
// ============================================================
function readEnv(key: string): string | undefined {
  if (typeof process !== "undefined" && process.env) {
    return process.env[key];
  }
  return undefined;
}

async function throwForStatus(res: Response): Promise<never> {
  let body = "";
  try {
    body = await res.text();
  } catch {
    /* ignore */
  }
  const msg = `HTTP ${res.status}: ${body.slice(0, 200)}`;
  if (res.status === 401) throw new AuthError(msg, { status: res.status, body });
  if (res.status === 429) throw new RateLimitError(msg, { status: res.status, body });
  if (res.status >= 500) throw new ServerError(msg, { status: res.status, body });
  throw new AgentError(msg, { status: res.status, body });
}
