"""ToolRegistry 单元测试"""

import pytest

from agent_core import Tool, ToolRegistry


async def _echo(text: str) -> str:
    return text


@pytest.fixture
def echo_tool() -> Tool:
    return Tool(
        name="echo",
        description="Echo input",
        parameters={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        execute=_echo,
    )


def test_register_and_list(echo_tool):
    r = ToolRegistry()
    r.register(echo_tool)
    assert "echo" in r.names()


def test_duplicate_register_fails(echo_tool):
    r = ToolRegistry([echo_tool])
    with pytest.raises(ValueError, match="already registered"):
        r.register(echo_tool)


def test_get_schemas(echo_tool):
    r = ToolRegistry([echo_tool])
    schemas = r.get_schemas()
    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "echo"


@pytest.mark.asyncio
async def test_execute_dict_args(echo_tool):
    r = ToolRegistry([echo_tool])
    result = await r.execute("echo", {"text": "hello"})
    assert result == "hello"


@pytest.mark.asyncio
async def test_execute_json_args(echo_tool):
    r = ToolRegistry([echo_tool])
    result = await r.execute("echo", '{"text": "hi"}')
    assert result == "hi"


@pytest.mark.asyncio
async def test_unknown_tool():
    r = ToolRegistry()
    with pytest.raises(KeyError, match="Unknown tool"):
        await r.execute("nope", "{}")
