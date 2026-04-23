"""Agent 运行时配置 · 解耦全局 settings"""

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """单次 agent 运行的配置 (五道闸门 - 详见 L5 §5)。"""

    max_steps: int = Field(15, ge=1, le=200, description="主循环最大步数")
    max_cost_usd: float = Field(0.5, gt=0, description="单次会话美元预算")
    max_consecutive_tool_errors: int = Field(3, ge=1, description="连续工具失败上限")
    max_loop_repeats: int = Field(3, ge=2, description="同 action 重复 N 次判定为死循环")
    max_total_tokens: int | None = Field(None, description="单次会话总 token 上限 (None = 不限)")
