"""Custom Agent SDK · Quickstart 示例

跑法 (workspace 内):
    uv run --package custom-agent-sdk python packages/sdk-python/examples/quickstart.py

或 (外部安装后):
    pip install custom-agent-sdk
    export CUSTOM_AGENT_API_KEY=...
    python quickstart.py
"""

import asyncio

from custom_agent_sdk import Client


async def main() -> None:
    async with Client() as client:  # 从 CUSTOM_AGENT_API_KEY 环境变量读
        print(">>> 流式对话:")
        print("-" * 60)
        async for event in client.chat.completions.stream(
            messages=[{"role": "user", "content": "现在北京时间几点然后算 7*8"}],
            model="deepseek/deepseek-chat",
        ):
            if event.type == "start":
                print(f"[start · model={event.data.model}]")
            elif event.type == "token":
                print(event.text, end="", flush=True)
            elif event.type == "tool_call":
                print(f"\n[🔧 {event.data.name}({event.data.arguments})]")
            elif event.type == "tool_result":
                preview = (event.data.result or event.data.error or "")[:80]
                print(f"[← {preview}]")
            elif event.type == "done":
                print(f"\n\n[done · {event.data.steps} steps · ${event.data.cost_usd}]")
            elif event.type == "error":
                print(f"\n❌ {event.text}")
        print("-" * 60)

        print("\n>>> 高层便捷接口:")
        text = await client.ask("用一句话介绍 RAG", model="deepseek/deepseek-chat")
        print(text)


if __name__ == "__main__":
    asyncio.run(main())
