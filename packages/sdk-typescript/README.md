# @custom-agent/sdk · TypeScript SDK

官方 TypeScript SDK,跑在 Node 20+ 与现代浏览器,3 行接入 Custom Agent Platform。

## 安装

```bash
npm install @custom-agent/sdk
# or
pnpm add @custom-agent/sdk
# or
yarn add @custom-agent/sdk
```

## 快速上手

### 流式对话(推荐)

```typescript
import { Client } from "@custom-agent/sdk";

const client = new Client({
  apiKey: process.env.CUSTOM_AGENT_API_KEY!,
  baseUrl: "http://localhost:8000",
});

for await (const event of client.chat.completions.stream({
  messages: [{ role: "user", content: "现在几点然后算 99×88" }],
  model: "deepseek/deepseek-chat",
})) {
  switch (event.type) {
    case "token":
      process.stdout.write(event.text);
      break;
    case "tool_call":
      console.log(`\n[🔧 ${event.data.name}]`);
      break;
    case "done":
      console.log(`\n[done · ${event.data.steps} steps · $${event.data.cost_usd}]`);
      break;
    case "error":
      console.error(event.text);
      break;
  }
}
```

### 非流式 (OpenAI 兼容)

```typescript
const resp = await client.chat.completions.create({
  messages: [{ role: "user", content: "Hello" }],
  model: "deepseek/deepseek-chat",
});
console.log(resp.choices[0].message.content);
```

### 高层便捷接口

```typescript
const text = await client.ask("用一句话介绍 RAG");
console.log(text);
```

## 配置

```typescript
new Client({
  apiKey: "...",                       // 必填(或 CUSTOM_AGENT_API_KEY env)
  baseUrl: "http://localhost:8000",    // 默认; 或 CUSTOM_AGENT_BASE_URL env
  defaultModel: "deepseek/deepseek-chat", // 不传 model 时用
  timeoutMs: 120_000,                   // 单请求超时
  fetch: customFetch,                   // 自定义 fetch (测试 / 代理用)
});
```

## 类型化事件

`StreamEvent` 是 discriminated union,按 `type` 字段分支,**TS 自动收窄类型**:

| `event.type` | 字段 |
|---|---|
| `start` | `data.model`, `data.max_steps` |
| `token` | `text` |
| `tool_call` | `data.name`, `data.arguments`, `data.id?` |
| `tool_result` | `data.name`, `data.result?` 或 `data.error?` |
| `done` | `data.steps`, `data.cost_usd` |
| `error` | `text` |

## 错误处理

```typescript
import {
  AgentError, AuthError, RateLimitError, ServerError, StreamError, TimeoutError,
} from "@custom-agent/sdk";

try {
  await client.chat.completions.create({...});
} catch (err) {
  if (err instanceof AuthError) { /* 401 - API key 错 */ }
  else if (err instanceof RateLimitError) { /* 429 */ }
  else if (err instanceof TimeoutError) { /* 超时 */ }
  else if (err instanceof AgentError) { /* 其他 - err.status, err.body */ }
}
```

## 浏览器中使用

直接 import 即可,内置 SSE parser 用 `ReadableStream` (现代浏览器原生)。

⚠️ 注意 CORS: 后端要允许你前端的域 (默认 dev mode 全放开)。

## 与 Vercel AI SDK 配合

```typescript
import { Client } from "@custom-agent/sdk";

// 在 Next.js route handler 里:
export async function POST(req: Request) {
  const { messages } = await req.json();
  const client = new Client({ apiKey: process.env.CUSTOM_AGENT_API_KEY! });

  // 把我们的 StreamEvent 转成 Vercel AI SDK 期待的格式
  const stream = new ReadableStream({
    async start(controller) {
      for await (const ev of client.chat.completions.stream({ messages })) {
        if (ev.type === "token") {
          controller.enqueue(new TextEncoder().encode(ev.text));
        }
      }
      controller.close();
    },
  });
  return new Response(stream, { headers: { "Content-Type": "text/plain" } });
}
```

## 跑测试

```bash
npm test           # 所有 vitest 用例
npm run test:watch # watch 模式
npm run lint       # tsc 类型检查
npm run build      # 编译到 dist/
```
