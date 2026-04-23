/**
 * 极简 SSE parser - 支持 \r\n / \n / \r 三种 line ending。
 * 不依赖任何外部包,跑在 Node 20+ 与现代浏览器。
 */

export interface SSEEvent {
  event: string; // 默认 "message"
  data: string; // 多行 data: 用 \n 拼接
  id?: string;
}

export async function* parseSSE(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<SSEEvent, void, void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // SSE spec 允许 \r\n / \n / \r
      buffer = buffer.replace(/\r\n/g, "\n").replace(/\r/g, "\n");

      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";

      for (const block of blocks) {
        const ev = parseBlock(block);
        if (ev) yield ev;
      }
    }
    // flush 残留
    if (buffer.trim()) {
      const ev = parseBlock(buffer);
      if (ev) yield ev;
    }
  } finally {
    reader.releaseLock();
  }
}

function parseBlock(block: string): SSEEvent | null {
  if (!block.trim()) return null;
  let event = "message";
  let id: string | undefined;
  const dataLines: string[] = [];

  for (const line of block.split("\n")) {
    if (!line || line.startsWith(":")) continue; // 注释
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    const valueRaw = colon === -1 ? "" : line.slice(colon + 1);
    const value = valueRaw.startsWith(" ") ? valueRaw.slice(1) : valueRaw;

    switch (field) {
      case "event":
        event = value;
        break;
      case "data":
        dataLines.push(value);
        break;
      case "id":
        id = value;
        break;
      // retry 字段忽略 (我们不做自动重连)
    }
  }

  if (dataLines.length === 0) return null;
  const result: SSEEvent = { event, data: dataLines.join("\n") };
  if (id !== undefined) result.id = id;
  return result;
}
