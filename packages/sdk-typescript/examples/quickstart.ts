/**
 * Quickstart example for @custom-agent/sdk
 *
 * Run from workspace root:
 *   cd packages/sdk-typescript
 *   CUSTOM_AGENT_API_KEY=dev-key-change-me npm run example
 */

import { Client, type StreamEvent } from "../src/index.js";

async function main(): Promise<void> {
  const client = new Client(); // 从 CUSTOM_AGENT_API_KEY 读

  console.log(">>> 流式对话:");
  console.log("-".repeat(60));
  for await (const ev of client.chat.completions.stream({
    messages: [{ role: "user", content: "现在北京时间几点然后算 7*8" }],
    model: "deepseek/deepseek-chat",
  })) {
    handleEvent(ev);
  }
  console.log("\n" + "-".repeat(60));

  console.log("\n>>> 高层便捷接口:");
  const text = await client.ask("用一句话介绍 RAG", {
    model: "deepseek/deepseek-chat",
  });
  console.log(text);
}

function handleEvent(ev: StreamEvent): void {
  switch (ev.type) {
    case "start":
      console.log(`[start · model=${ev.data.model}]`);
      break;
    case "token":
      process.stdout.write(ev.text);
      break;
    case "tool_call":
      console.log(`\n[🔧 ${ev.data.name}(${ev.data.arguments})]`);
      break;
    case "tool_result": {
      const preview = (ev.data.result ?? ev.data.error ?? "").slice(0, 80);
      console.log(`[← ${preview}]`);
      break;
    }
    case "done":
      console.log(`\n\n[done · ${ev.data.steps} steps · $${ev.data.cost_usd}]`);
      break;
    case "error":
      console.error(`\n❌ ${ev.text}`);
      break;
  }
}

main().catch((err) => {
  console.error("Error:", err);
  process.exit(1);
});
