# custom-agent-sdk · Python SDK

官方 Python SDK,3 行接入 Custom Agent Platform。

## 安装

```bash
pip install custom-agent-sdk
```

## 快速上手

### 流式对话(推荐)

```python
import asyncio
from custom_agent_sdk import Client

async def main():
    async with Client(api_key="dev-key-change-me") as client:
        async for event in client.chat.completions.stream(
            messages=[{"role": "user", "content": "现在几点然后算 99×88"}],
            model="deepseek/deepseek-chat",
        ):
            if event.type == "token":
                print(event.text, end="", flush=True)
            elif event.type == "tool_call":
                print(f"\n[🔧 {event.data.name}]", end="")
            elif event.type == "tool_result":
                pass  # 已通过 token 渲染
            elif event.type == "done":
                print(f"\n\n[done · {event.data.steps} steps · ${event.data.cost_usd}]")
            elif event.type == "error":
                print(f"\n❌ {event.text}")

asyncio.run(main())
```

### 非流式 (OpenAI 兼容)

```python
async with Client(api_key="...") as client:
    resp = await client.chat.completions.create(
        messages=[{"role": "user", "content": "Hello"}],
        model="deepseek/deepseek-chat",
    )
    print(resp.choices[0].message.content)
```

### 高层便捷接口

```python
async with Client(api_key="...") as client:
    text = await client.ask("用一句话介绍 RAG")
    print(text)
```

## 配置

| 参数 | 默认 | 说明 |
|---|---|---|
| `api_key` | (必填) | 平台签发的 API Key |
| `base_url` | `http://localhost:8000` | 你的 Custom Agent 服务地址 |
| `default_model` | `None` | 不传时由服务端默认值决定 |
| `timeout` | `120` | 单次请求超时秒数 |

环境变量自动读取:
- `CUSTOM_AGENT_API_KEY`
- `CUSTOM_AGENT_BASE_URL`

## 类型化事件

| `event.type` | 字段 | 说明 |
|---|---|---|
| `start` | `data.model`, `data.max_steps` | Agent 启动 |
| `token` | `text` | 流式文本 |
| `tool_call` | `data.name`, `data.arguments`, `data.id` | 调用工具 |
| `tool_result` | `data.name`, `data.result` 或 `data.error` | 工具返回 |
| `done` | `data.steps`, `data.cost_usd` | 任务完成 |
| `error` | `text` | 失败 |

## 错误处理

```python
from custom_agent_sdk import Client, AgentError, AuthError, RateLimitError

try:
    resp = await client.chat.completions.create(...)
except AuthError:
    ...  # 401 - API Key 错误
except RateLimitError:
    ...  # 429 - 限流
except AgentError as e:
    ...  # 其他 - e.status, e.body
```

## OpenAI 兼容

我们的 `/v1/chat/completions` 完全 OpenAI 兼容,你也可以**直接用 openai 包**:

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key="dev-key-change-me", base_url="http://localhost:8000/v1")
resp = await client.chat.completions.create(messages=[...], model="...")
```

但用我们 SDK 的好处:
- ✅ 类型化的扩展事件 (tool_call / tool_result / done.cost_usd)
- ✅ 高层便捷方法 (`client.ask(...)`)
- ✅ 自动从环境变量读配置
- ✅ 不需要把模型名映射到 OpenAI 命名空间
