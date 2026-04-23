/** 极简 SSE 解析,支持 \r\n / \n / \r 三种 line ending。 */

import type { StreamEvent } from "./types";

export interface ParseHandlers {
  onEvent: (ev: StreamEvent) => void;
  onError?: (msg: string) => void;
}

export async function parseSseStream(
  body: ReadableStream<Uint8Array>,
  handlers: ParseHandlers,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      buffer = buffer.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        const ev = parseBlock(block);
        if (ev) handlers.onEvent(ev);
      }
    }
    if (buffer.trim()) {
      const ev = parseBlock(buffer);
      if (ev) handlers.onEvent(ev);
    }
  } catch (e) {
    handlers.onError?.(e instanceof Error ? e.message : String(e));
  } finally {
    reader.releaseLock();
  }
}

function parseBlock(block: string): StreamEvent | null {
  if (!block.trim()) return null;
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("data:")) {
      const v = line.slice(5);
      dataLines.push(v.startsWith(" ") ? v.slice(1) : v);
    }
  }
  if (dataLines.length === 0) return null;
  const payload = dataLines.join("\n");
  if (payload === "[DONE]") return null;
  try {
    return JSON.parse(payload) as StreamEvent;
  } catch {
    return null;
  }
}
