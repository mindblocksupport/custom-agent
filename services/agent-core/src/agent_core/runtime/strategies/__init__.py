"""Agent 策略 · 不同推理范式

每个策略实现 AgentStrategy 协议,在 planner / executor / critic 之上编排。

当前:
- ReActStrategy   - 经典 think → act → observe 循环

未来 (按 docs/05 §3):
- PlanExecuteStrategy  - 一次规划 → 并行执行 → 完成
- ReflexionStrategy    - ReAct + critic 反思纠错
- TreeOfThoughtsStrategy - 多路探索 + 剪枝
- CodeActStrategy      - 模型直接生成代码作 action
"""

from agent_core.runtime.strategies.base import AgentStrategy
from agent_core.runtime.strategies.react import ReActStrategy

__all__ = ["AgentStrategy", "ReActStrategy"]
