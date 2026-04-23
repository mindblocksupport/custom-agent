# gateway · L2 LLM Gateway

唯一的 LLM 出口。MVP = LiteLLM 包装。

## 公开 API

```python
from gateway import llm_complete_stream

async for chunk in llm_complete_stream(
    messages=[...],
    model="deepseek/deepseek-chat",
    tools=[...],
):
    # chunk["type"] in ("text", "tool_call", "usage")
    ...
```

## 后续演进

按 [docs/02-llm-gateway.md](../../docs/02-llm-gateway.md) §2-9:

- ⏳ 模型路由 (Rule + Embedding + Learned)
- ⏳ 三级缓存 (exact + prompt cache + semantic)
- ⏳ 限流配额引擎
- ⏳ Failover 状态机
- ⏳ 计费埋点 → Kafka

## 文档

- [L2 LLM Gateway](../../docs/02-llm-gateway.md)
- [L11 模型战略](../../docs/11-model-strategy.md)
- [L12 LLM API 协议](../../docs/12-llm-api-protocols.md)
