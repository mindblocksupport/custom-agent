"""KB routes 测试 (mock kb_db, 不需要真 PG)."""

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from api_server.db.kb import DocRow, IngestJobRow
from api_server.main import app

AUTH = {"Authorization": "Bearer dev-key-change-me"}
T = UUID("00000000-0000-0000-0000-000000000001")


def _doc(did: UUID = None, status: str = "published") -> DocRow:
    return DocRow(
        id=did or uuid4(), tenant_id=T, source_uri="/tmp/x.md",
        source_type="file", title="Test", collection="default",
        status=status, current_version=1, chunk_count=10,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _job(jid: UUID = None, status: str = "pending") -> IngestJobRow:
    return IngestJobRow(
        id=jid or uuid4(), tenant_id=T, actor_id="dev",
        doc_id=None, collection="default", source_uri="/tmp/x.md",
        source_type="file", status=status, progress=0, stage=None, error=None,
        chunks_created=0, chunks_reused=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        finished_at=None,
    )


def test_list_docs_empty():
    with patch("api_server.routes.kb.kb_db.list_docs", return_value=([], None)), \
         TestClient(app) as client:
        r = client.get("/v1/kb/docs", headers=AUTH)
        assert r.status_code == 200
        assert r.json() == {"items": [], "next_cursor": None}


def test_list_docs_with_filters():
    rows = [_doc(), _doc()]
    with patch("api_server.routes.kb.kb_db.list_docs", return_value=(rows, None)) as m, \
         TestClient(app) as client:
        r = client.get("/v1/kb/docs?collection=legal&status=published", headers=AUTH)
        assert r.status_code == 200
        assert len(r.json()["items"]) == 2
        # collection / status 透传给 db 层
        kwargs = m.call_args.kwargs
        assert kwargs["collection"] == "legal"
        assert kwargs["status"] == "published"


def test_get_doc():
    did = uuid4()
    with patch("api_server.routes.kb.kb_db.get_doc", return_value=_doc(did)), \
         TestClient(app) as client:
        r = client.get(f"/v1/kb/docs/{did}", headers=AUTH)
        assert r.status_code == 200
        assert r.json()["id"] == str(did)
        assert r.json()["chunk_count"] == 10


def test_get_doc_404():
    with patch("api_server.routes.kb.kb_db.get_doc", return_value=None), \
         TestClient(app) as client:
        r = client.get(f"/v1/kb/docs/{uuid4()}", headers=AUTH)
        assert r.status_code == 404


def test_delete_doc():
    with patch("api_server.routes.kb.kb_db.delete_doc", return_value=True), \
         TestClient(app) as client:
        r = client.delete(f"/v1/kb/docs/{uuid4()}", headers=AUTH)
        assert r.status_code == 200
        assert r.json() == {"deleted": True}


def test_delete_doc_404():
    with patch("api_server.routes.kb.kb_db.delete_doc", return_value=False), \
         TestClient(app) as client:
        r = client.delete(f"/v1/kb/docs/{uuid4()}", headers=AUTH)
        assert r.status_code == 404


def test_get_job_status():
    jid = uuid4()
    with patch("api_server.routes.kb.kb_db.get_job", return_value=_job(jid, "parsing")), \
         TestClient(app) as client:
        r = client.get(f"/v1/kb/jobs/{jid}", headers=AUTH)
        assert r.status_code == 200
        assert r.json()["status"] == "parsing"


def test_upload_creates_job():
    jid = uuid4()
    with patch("api_server.routes.kb.kb_db.create_ingest_job", return_value=jid), \
         patch("api_server.routes.kb.run_ingest_job"), \
         TestClient(app) as client:
        r = client.post(
            "/v1/kb/upload",
            files={"file": ("test.md", b"# Hello\nworld", "text/markdown")},
            data={"collection": "legal"},
            headers=AUTH,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["job_id"] == str(jid)
        assert body["collection"] == "legal"


def test_upload_rejects_empty():
    with TestClient(app) as client:
        r = client.post(
            "/v1/kb/upload",
            files={"file": ("empty.md", b"", "text/markdown")},
            headers=AUTH,
        )
        assert r.status_code == 400


def test_kb_requires_auth():
    with TestClient(app) as client:
        for path in ["/v1/kb/docs", f"/v1/kb/docs/{uuid4()}",
                     f"/v1/kb/jobs/{uuid4()}"]:
            r = client.get(path)
            assert r.status_code in (401, 403), f"{path}: {r.status_code}"
