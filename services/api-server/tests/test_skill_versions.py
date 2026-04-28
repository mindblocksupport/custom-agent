"""Skill version 历史 + rollback routes 测试 (mock DB)."""

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from api_server.db.skills import SkillRow
from api_server.main import app

AUTH = {"Authorization": "Bearer dev-key-change-me"}


def _skill(version: int = 1, sid: UUID | None = None) -> SkillRow:
    return SkillRow(
        id=sid or uuid4(),
        workspace_id=uuid4(),
        name="月报", description="",
        version=version,
        system_prompt=f"prompt v{version}",
        allowed_tools=[], default_collections=[],
        starter_examples=[], visibility="workspace",
        budget_per_call_usd=None, tags=[],
        created_by="dev",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_list_versions_returns_descending():
    sid = uuid4()
    versions = [_skill(version=3), _skill(version=2), _skill(version=1)]
    with patch(
        "api_server.routes.skills.skill_db.list_versions",
        return_value=versions,
    ), TestClient(app) as client:
        r = client.get(f"/v1/skills/{sid}/versions", headers=AUTH)
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body) == 3
        assert [v["version"] for v in body] == [3, 2, 1]


def test_list_versions_404_when_skill_not_found():
    sid = uuid4()
    with patch(
        "api_server.routes.skills.skill_db.list_versions",
        return_value=[],
    ), TestClient(app) as client:
        r = client.get(f"/v1/skills/{sid}/versions", headers=AUTH)
        assert r.status_code == 404


def test_rollback_creates_new_latest():
    sid = uuid4()
    new_id = uuid4()
    new_row = _skill(version=4, sid=new_id)  # rollback after v3 → v4 is the new latest
    with patch(
        "api_server.routes.skills.skill_db.rollback_to",
        return_value=new_id,
    ), patch(
        "api_server.routes.skills.skill_db.get",
        return_value=new_row,
    ), TestClient(app) as client:
        r = client.post(
            f"/v1/skills/{sid}/rollback",
            json={"target_version": 1},
            headers=AUTH,
        )
        assert r.status_code == 200, r.text
        assert r.json()["id"] == str(new_id)
        assert r.json()["version"] == 4


def test_rollback_404_when_target_version_missing():
    sid = uuid4()
    with patch(
        "api_server.routes.skills.skill_db.rollback_to",
        return_value=None,
    ), TestClient(app) as client:
        r = client.post(
            f"/v1/skills/{sid}/rollback",
            json={"target_version": 999},
            headers=AUTH,
        )
        assert r.status_code == 404


def test_rollback_validates_target_version_min():
    sid = uuid4()
    with TestClient(app) as client:
        r = client.post(
            f"/v1/skills/{sid}/rollback",
            json={"target_version": 0},
            headers=AUTH,
        )
        assert r.status_code == 422
