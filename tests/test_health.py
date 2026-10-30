"""Tests for GET /health."""

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.main import app


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_returns_503_when_database_fails(client: TestClient) -> None:
    class BrokenSession:
        def execute(self, *args: object, **kwargs: object) -> None:
            raise OperationalError("SELECT 1", {}, Exception("db down"))

    app.dependency_overrides[get_db] = lambda: BrokenSession()
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
