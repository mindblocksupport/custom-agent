# schemas · 共享 Pydantic Schema

跨服务的数据契约。**不依赖任何业务逻辑**,只描述结构。

## 包含

| 文件 | 内容 |
|---|---|
| `chat.py` | `ChatMessage` / `ChatRequest` (OpenAI 兼容) |
| `events.py` | `StreamEvent` 类型化 discriminated union |

## 用法

```python
from schemas import ChatRequest, StreamEvent, TokenEvent, ToolCallEvent
```

## 演进

- 后续加 `MemoryEntry` / `Skill` / `WorkflowStep` 等
- 同一 schema 自动生成 OpenAPI / TypeScript SDK
