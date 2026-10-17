from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_read_only_db():
    body = TestClient(app).get("/api/health").json()
    assert body["status"] == "ok"
    assert body["database"]["ok"] is True
    assert body["database"]["read_only"] is True
    assert body["database"]["file"] == "fpl.db"
