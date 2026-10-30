"""Shared fixtures: in-memory DB, TestClient, authenticated users, application factory."""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  # tabloların Base'e kayıt olması için
from app.database import Base, get_db
from app.main import app

PASSWORD = "supersecret1"
USER_EMAIL = "alice@example.com"
OTHER_EMAIL = "bob@example.com"


@pytest.fixture
def client() -> Iterator[TestClient]:
    # StaticPool: tüm bağlantılar aynı in-memory veritabanını görür.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db() -> Iterator[Any]:
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def register_and_login(client: TestClient, email: str) -> dict[str, str]:
    client.post("/auth/register", json={"email": email, "password": PASSWORD})
    response = client.post("/auth/login", data={"username": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    return register_and_login(client, USER_EMAIL)


@pytest.fixture
def other_auth_headers(client: TestClient) -> dict[str, str]:
    return register_and_login(client, OTHER_EMAIL)


@pytest.fixture
def make_application(client: TestClient) -> Callable[..., dict[str, Any]]:
    """Factory: create an application via the API and return its JSON."""

    def _make(headers: dict[str, str], **overrides: Any) -> dict[str, Any]:
        payload = {"company": "Acme", "position": "Backend Developer", **overrides}
        response = client.post("/applications", json=payload, headers=headers)
        assert response.status_code == 201, response.text
        return response.json()

    return _make
