# agent-core · L5 Agent Runtime

Agent 主循环 + 工具协议 + 防失控护栏。

## 公开 API

```python
from agent_core import run_agent, AgentConfig, ToolRegistry, Tool

# 1. 装填工具
from tools_builtin import build_default_registry
registry = build_default_registry()  # 或自己 ToolRegistry().register(...)

# 2. 跑
async for event in run_agent(
    messages=[{"role": "user", "content": "hi"}],
    model="deepseek/deepseek-chat",
    registry=registry,
    config=AgentConfig(max_steps=15, max_cost_usd=0.5),
):
    print(event.type, event)
```

## 子模块

| 模块 | 职责 |
|---|---|
| `runtime/loop.py` | ReAct 主循环 |
| `runtime/state.py` | AgentState dataclass |
| `runtime/config.py` | AgentConfig (五道闸门参数) |
| `tools/protocol.py` | Tool dataclass |
| `tools/registry.py` | ToolRegistry 类 |
| `guardrails/limits.py` | RuntimeGuard (防失控) |

## 设计原则

1. **依赖注入** —— `run_agent()` 所有外部依赖通过参数传入,无全局变量
2. **类型化事件** —— yield `StreamEvent` (来自 `schemas`),上层负责序列化
3. **不依赖 settings** —— 是纯库,api-server 才管配置
4. **MVP 简版** —— 后续替换为 LangGraph (见 docs/16 §6)

## 文档

- [L5 Agent Core](../../docs/05-agent-core.md)
- [L13 Context Engineering](../../docs/13-context-engineering.md)
- [L10 当前痛点](../../docs/10-current-problems-and-mitigations.md)
