/**
 * SDK 单元测试 - 用 mock fetch 避免起 backend
 */

import { describe, it, expect, vi } from "vitest";
import {
  AgentError,
  AuthError,
  Client,
  type StreamEvent,
} from "../src/index.js";

// ============================================================
// Helpers
// ============================================================
function jsonResponse(status: number, data: unknown): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function sseResponse(events: Array<{ event: string; data: unknown }>): Response {
  const lines: string[] = [];
  for (const ev of events) {
    lines.push(`event: ${ev.event}`);
    const payload = typeof ev.data === "string" ? ev.data : JSON.stringify(ev.data);
    lines.push(`data: ${payload}`);
    lines.push("");
  }
  const body = lines.join("\n") + "\n";
  return new Response(body, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

function makeClient(handler: (url: string, init: RequestInit) => Response | Promise<Response>) {
  const fetchFn = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = typeof input === "string" ? input : input.toString();
    return handler(url, init);
  }) as unknown as typeof fetch;

  return new Client({
    apiKey: "test-key",
    baseUrl: "http://test",
    fetch: fetchFn,
  });
}

// ============================================================
// Tests
// ============================================================
describe("Client construction", () => {
  it("requires apiKey", () => {
    delete (process.env as any).CUSTOM_AGENT_API_KEY;
    expect(() => new Client()).toThrow(/apiKey required/);
  });

  it("reads CUSTOM_AGENT_API_KEY env var", () => {
    process.env.CUSTOM_AGENT_API_KEY = "env-key";
    const c = new Client();
    expect(c.apiKey).toBe("env-key");
    delete (process.env as any).CUSTOM_AGENT_API_KEY;
  });

  it("strips trailing slash from baseUrl", () => {
    const c = new Client({ apiKey: "k", baseUrl: "http://foo:8000/" });
    expect(c.baseUrl).toBe("http://foo:8000");
  });
});

describe("chat.completions.create (non-stream)", () => {
  it("posts to /v1/chat/completions and parses response", async () => {
    const c = makeClient((url, init) => {
      expect(url).toBe("http://test/v1/chat/completions");
      const body = JSON.parse(init.body as string);
      expect(body.stream).toBe(false);
      expect(body.messages[0].content).toBe("hi");
      return jsonResponse(200, {
        model: "fake",
        choices: [
          {
            index: 0,
            message: { role: "assistant", content: "hello back" },
            finish_reason: "stop",
          },
        ],
      });
    });
    const resp = await c.chat.completions.create({
      messages: [{ role: "user", content: "hi" }],
      model: "fake",
    });
    expect(resp.choices[0]?.message.content).toBe("hello back");
  });

  it("throws AuthError on 401", async () => {
    const c = makeClient(() => jsonResponse(401, { detail: "Invalid API key" }));
    await expect(
      c.chat.completions.create({
        messages: [{ role: "user", content: "x" }],
        model: "fake",
      }),
    ).rejects.toBeInstanceOf(AuthError);
  });
});

describe("chat.completions.stream", () => {
  it("yields typed events", async () => {
    const c = makeClient(() =>
      sseResponse([
        { event: "start", data: { type: "start", data: { model: "fake", max_steps: 15 } } },
        { event: "token", data: { type: "token", text: "Hello " } },
        { event: "token", data: { type: "token", text: "world" } },
        { event: "done", data: { type: "done", data: { steps: 1, cost_usd: 0.001 } } },
        { event: "done", data: "[DONE]" },
      ]),
    );
    const events: StreamEvent[] = [];
    for await (const e of c.chat.completions.stream({
      messages: [{ role: "user", content: "hi" }],
      model: "fake",
    })) {
      events.push(e);
    }
    expect(events.map((e) => e.type)).toEqual(["start", "token", "token", "done"]);
    expect((events[1] as { text: string }).text).toBe("Hello ");
  });

  it("yields tool_call + tool_result events", async () => {
    const c = makeClient(() =>
      sseResponse([
        { event: "start", data: { type: "start", data: { model: "fake", max_steps: 15 } } },
        {
          event: "tool_call",
          data: {
            type: "tool_call",
            data: { id: "c1", name: "calculator", arguments: '{"x":1}' },
          },
        },
        {
          event: "tool_result",
          data: {
            type: "tool_result",
            data: { id: "c1", name: "calculator", result: "42" },
          },
        },
        { event: "done", data: { type: "done", data: { steps: 2, cost_usd: 0 } } },
      ]),
    );
    const events: StreamEvent[] = [];
    for await (const e of c.chat.completions.stream({
      messages: [{ role: "user", content: "hi" }],
      model: "fake",
    })) {
      events.push(e);
    }
    const tc = events.find((e) => e.type === "tool_call");
    const tr = events.find((e) => e.type === "tool_result");
    expect(tc).toBeDefined();
    expect(tr).toBeDefined();
    if (tc?.type === "tool_call") expect(tc.data.name).toBe("calculator");
    if (tr?.type === "tool_result") expect(tr.data.result).toBe("42");
  });

  it("handles CRLF line endings (regression)", async () => {
    const body = 'event: token\r\ndata: {"type":"token","text":"ok"}\r\n\r\n';
    const c = makeClient(
      () =>
        new Response(body, {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        }),
    );
    const events: StreamEvent[] = [];
    for await (const e of c.chat.completions.stream({
      messages: [{ role: "user", content: "x" }],
      model: "fake",
    })) {
      events.push(e);
    }
    expect(events.length).toBe(1);
    expect(events[0]?.type).toBe("token");
  });
});

describe("ask convenience method", () => {
  it("aggregates token events into a string", async () => {
    const c = makeClient(() =>
      sseResponse([
        { event: "start", data: { type: "start", data: { model: "fake", max_steps: 15 } } },
        { event: "token", data: { type: "token", text: "Paris" } },
        { event: "token", data: { type: "token", text: "." } },
        { event: "done", data: { type: "done", data: { steps: 1, cost_usd: 0 } } },
      ]),
    );
    const text = await c.ask("Capital of France?", { model: "fake" });
    expect(text).toBe("Paris.");
  });

  it("throws AgentError on error event", async () => {
    const c = makeClient(() =>
      sseResponse([
        { event: "start", data: { type: "start", data: { model: "fake", max_steps: 15 } } },
        { event: "error", data: { type: "error", text: "boom" } },
      ]),
    );
    await expect(c.ask("x", { model: "fake" })).rejects.toThrow(/boom/);
  });
});
