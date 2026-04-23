"""ModelRouter 启发式规则测试."""

from gateway.router import ModelRouter


def _msg(role: str, content: str) -> dict:
    return {"role": role, "content": content}


def test_explicit_model_wins():
    r = ModelRouter()
    d = r.route(messages=[_msg("user", "x")], explicit_model="anthropic/claude-opus-4-7")
    assert d.model == "anthropic/claude-opus-4-7" and d.reason == "explicit"


def test_short_faq_goes_cheap():
    r = ModelRouter()
    d = r.route(messages=[_msg("user", "今天几号")])
    assert d.model.startswith("deepseek")
    assert d.reason in {"default_short", "tool_calling"}


def test_reasoning_keyword_triggers_reasoning_model():
    r = ModelRouter()
    d = r.route(messages=[_msg("user", "请分析这个数据库设计的权衡")])
    assert "claude" in d.model.lower() or d.model.endswith("sonnet-4-6")
    assert d.reason == "reasoning_keyword"


def test_long_query_goes_reasoning():
    long_text = "x" * 250
    r = ModelRouter()
    d = r.route(messages=[_msg("user", long_text)])
    assert d.reason == "long_query"


def test_force_model_overrides_heuristic():
    r = ModelRouter(force_model="custom/model-v1")
    d = r.route(messages=[_msg("user", "请分析 X 的原因")])
    assert d.model == "custom/model-v1" and d.reason == "force"


def test_tool_calling_picks_cheap():
    r = ModelRouter()
    d = r.route(
        messages=[_msg("user", "查询天气")],
        tools=[{"name": "get_weather"}],
    )
    assert d.model.startswith("deepseek") and d.reason == "tool_calling"


def test_uses_last_user_message_not_assistant():
    r = ModelRouter()
    d = r.route(messages=[
        _msg("user", "请分析这个"),     # 早期 user 含推理词
        _msg("assistant", "好的"),
        _msg("user", "好"),               # 最后一条短 user
    ])
    # 用最后一条 user → 短 → cheap
    assert d.model.startswith("deepseek")
