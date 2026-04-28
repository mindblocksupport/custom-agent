"""Multimodal chat schema + skill_vars 渲染测试."""

from unittest.mock import patch
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from api_server.db.skills import SkillRow
from api_server.db.workspaces import WorkspaceRow
from api_server.main import app
from api_server.routes.chat import (
    _content_to_text,
    _count_image_parts,
    _render_skill_prompt,
    _apply_skill_to_messages,
)

AUTH = {"Authorization": "Bearer dev-key-change-me"}
TENANT = UUID("00000000-0000-0000-0000-000000000001")


# ---------------- _content_to_text + _count_image_parts ----------------

def test_content_to_text_passes_string_through():
    assert _content_to_text("hello") == "hello"


def test_content_to_text_flattens_multimodal_array():
    content = [
        {"type": "text", "text": "what is this?"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,xxxx"}},
    ]
    out = _content_to_text(content)
    assert "what is this?" in out
    assert "[image:base64]" in out


def test_content_to_text_handles_url_image():
    content = [
        {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}},
    ]
    out = _content_to_text(content)
    assert "[image:" in out and "example.com" in out


def test_content_to_text_handles_none():
    assert _content_to_text(None) == ""


def test_count_image_parts():
    assert _count_image_parts(None) == 0
    assert _count_image_parts("just text") == 0
    assert _count_image_parts([{"type": "text", "text": "x"}]) == 0
    assert _count_image_parts(
        [
            {"type": "text", "text": "x"},
            {"type": "image_url", "image_url": {"url": "data:..."}},
            {"type": "image_url", "image_url": {"url": "https://..."}},
        ]
    ) == 2


# ---------------- _render_skill_prompt ----------------

def test_render_skill_prompt_substitutes():
    assert (
        _render_skill_prompt("Hi {{ name }}, today is {{ day }}", {"name": "Alex", "day": "Mon"})
        == "Hi Alex, today is Mon"
    )


def test_render_skill_prompt_keeps_unfilled():
    out = _render_skill_prompt("Hi {{ name }} from {{ city }}", {"name": "A"})
    assert out == "Hi A from {{ city }}"


def test_render_skill_prompt_empty_vars():
    assert _render_skill_prompt("no vars", {}) == "no vars"


def test_render_skill_prompt_repeats():
    assert _render_skill_prompt("{{ x }}-{{ x }}", {"x": "7"}) == "7-7"


# ---------------- _apply_skill_to_messages w/ vars ----------------

def _mk_skill(prompt: str = "你是 {{ role }} 助手") -> SkillRow:
    return SkillRow(
        id=uuid4(), workspace_id=uuid4(),
        name="测试", description="",
        version=1, system_prompt=prompt,
        allowed_tools=[], default_collections=[],
        starter_examples=[], visibility="workspace",
        budget_per_call_usd=None, tags=[],
        created_by="dev",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_apply_skill_renders_with_vars():
    skill = _mk_skill("你是 {{ role }} 助手, 用 {{ tool }} 找数据")
    out = _apply_skill_to_messages(
        [{"role": "user", "content": "hi"}],
        skill,
        {"role": "数据分析", "tool": "search_kb"},
    )
    assert out[0]["role"] == "system"
    assert out[0]["content"] == "你是 数据分析 助手, 用 search_kb 找数据"
    assert out[1]["role"] == "user"


def test_apply_skill_no_vars_no_change():
    skill = _mk_skill("plain prompt")
    out = _apply_skill_to_messages(
        [{"role": "user", "content": "hi"}], skill, {},
    )
    assert out[0]["content"] == "plain prompt"


def test_apply_skill_none_skips():
    msgs = [{"role": "user", "content": "hi"}]
    assert _apply_skill_to_messages(msgs, None, {}) == msgs


# ---------------- ChatRequest schema parses multimodal ----------------

def test_chat_request_accepts_multimodal_content():
    """直接经 FastAPI 走 schema 验证 (不真发 LLM)."""
    # 用 422 检查 schema 接受; 真到 LLM 之前会失败 (没 mock), 但 422 vs 500 可以区分.
    body = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "what's this?"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/png;base64,iVBORw0KGgo=",
                        },
                    },
                ],
            }
        ],
        "stream": False,
    }
    with TestClient(app) as client:
        r = client.post("/v1/chat/completions", json=body, headers=AUTH)
        # 接受 schema = 200/500 (LLM 没 key 或 mock 会 500), 拒 = 422
        assert r.status_code != 422, f"schema rejected multimodal: {r.text}"


def test_chat_request_accepts_skill_vars_field():
    body = {
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
        "skill_vars": {"name": "Alex"},
    }
    with TestClient(app) as client:
        r = client.post("/v1/chat/completions", json=body, headers=AUTH)
        assert r.status_code != 422, f"skill_vars rejected: {r.text}"
