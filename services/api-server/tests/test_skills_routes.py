"""Skills routes 测试 (mock DB)."""

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from api_server.db.skills import SkillRow
from api_server.main import app

AUTH = {"Authorization": "Bearer dev-key-change-me"}


def _skill(sid: UUID = None, name: str = "月报生成", version: int = 1) -> SkillRow:
    return SkillRow(
        id=sid or uuid4(),
        workspace_id=uuid4(),
        name=name, description="生成月度报告",
        version=version,
        system_prompt="你是一个数据分析助手, 用 search_kb 找数据.",
        allowed_tools=["search_kb"],
        default_collections=["finance"],
        starter_examples=["上月营收", "Q3 违约率"],
        visibility="workspace",
        budget_per_call_usd=0.1, tags=["analyst"],
        created_by="dev",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def test_create_skill():
    sid = uuid4()
    wid = uuid4()
    with patch("api_server.routes.skills.skill_db.create", return_value=sid), \
         patch("api_server.routes.skills.skill_db.get", return_value=_skill(sid)), \
         TestClient(app) as client:
        r = client.post(
            f"/v1/workspaces/{wid}/skills",
            json={"name": "月报生成", "system_prompt": "你是分析助手"},
            headers=AUTH,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["id"] == str(sid)
        assert body["version"] == 1


def test_create_skill_workspace_404():
    with patch("api_server.routes.skills.skill_db.create", return_value=None), \
         TestClient(app) as client:
        r = client.post(
            f"/v1/workspaces/{uuid4()}/skills",
            json={"name": "x"}, headers=AUTH,
        )
        assert r.status_code == 404


def test_list_skills():
    rows = [_skill(name=f"sk{i}") for i in range(2)]
    with patch("api_server.routes.skills.skill_db.list_for_workspace",
               return_value=rows), \
         TestClient(app) as client:
        r = client.get(f"/v1/workspaces/{uuid4()}/skills", headers=AUTH)
        assert r.status_code == 200
        assert len(r.json()) == 2


def test_get_skill():
    sid = uuid4()
    with patch("api_server.routes.skills.skill_db.get", return_value=_skill(sid)), \
         TestClient(app) as client:
        r = client.get(f"/v1/skills/{sid}", headers=AUTH)
        assert r.status_code == 200
        assert r.json()["id"] == str(sid)


def test_get_skill_404():
    with patch("api_server.routes.skills.skill_db.get", return_value=None), \
         TestClient(app) as client:
        r = client.get(f"/v1/skills/{uuid4()}", headers=AUTH)
        assert r.status_code == 404


def test_patch_skill():
    sid = uuid4()
    with patch("api_server.routes.skills.skill_db.update", return_value=True), \
         patch("api_server.routes.skills.skill_db.get",
               return_value=_skill(sid, name="月报 v2")), \
         TestClient(app) as client:
        r = client.patch(f"/v1/skills/{sid}",
                         json={"name": "月报 v2"}, headers=AUTH)
        assert r.status_code == 200
        assert r.json()["name"] == "月报 v2"


def test_delete_skill():
    with patch("api_server.routes.skills.skill_db.delete", return_value=True), \
         TestClient(app) as client:
        r = client.delete(f"/v1/skills/{uuid4()}", headers=AUTH)
        assert r.status_code == 200


def test_new_version_bumps():
    sid = uuid4()
    new_sid = uuid4()
    with patch("api_server.routes.skills.skill_db.new_version", return_value=new_sid), \
         patch("api_server.routes.skills.skill_db.get",
               return_value=_skill(new_sid, version=2)), \
         TestClient(app) as client:
        r = client.post(f"/v1/skills/{sid}/versions",
                        json={"system_prompt": "更新版"}, headers=AUTH)
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == str(new_sid)
        assert body["version"] == 2


def test_visibility_validation():
    with TestClient(app) as client:
        r = client.post(
            f"/v1/workspaces/{uuid4()}/skills",
            json={"name": "x", "visibility": "secret"},
            headers=AUTH,
        )
        assert r.status_code == 422


def test_skills_require_auth():
    with TestClient(app) as client:
        r = client.get(f"/v1/skills/{uuid4()}")
        assert r.status_code in (401, 403)


# ==== v1.5 Skill 市场 ====

def test_list_skills_include_public():
    own = [_skill(name="own1"), _skill(name="own2")]
    market = [_skill(name="market_a"), _skill(name="market_b")]
    with patch("api_server.routes.skills.skill_db.list_for_workspace",
               return_value=own), \
         patch("api_server.routes.skills.skill_db.list_public_in_tenant",
               return_value=market), \
         TestClient(app) as client:
        r = client.get(
            f"/v1/workspaces/{uuid4()}/skills?include_public=true",
            headers=AUTH,
        )
        assert r.status_code == 200
        names = [s["name"] for s in r.json()]
        assert names == ["own1", "own2", "market_a", "market_b"]


def test_list_skills_default_no_public():
    own = [_skill(name="own1")]
    public_called = []
    with patch("api_server.routes.skills.skill_db.list_for_workspace",
               return_value=own), \
         patch(
            "api_server.routes.skills.skill_db.list_public_in_tenant",
            side_effect=lambda **_: public_called.append(1) or [],
        ), \
         TestClient(app) as client:
        r = client.get(f"/v1/workspaces/{uuid4()}/skills", headers=AUTH)
        assert r.status_code == 200
        assert [s["name"] for s in r.json()] == ["own1"]
        assert public_called == []


def test_skills_market_endpoint():
    market = [_skill(name="法务月报"), _skill(name="客服 SOP")]
    with patch("api_server.routes.skills.skill_db.list_public_in_tenant",
               return_value=market), \
         TestClient(app) as client:
        r = client.get("/v1/skills/public", headers=AUTH)
        assert r.status_code == 200
        assert {s["name"] for s in r.json()} == {"法务月报", "客服 SOP"}
