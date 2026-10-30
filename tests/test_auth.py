"""Tests for /auth/register, /auth/login and /auth/me."""

import pytest
from fastapi.testclient import TestClient

PASSWORD = "supersecret1"
USER_EMAIL = "alice@example.com"


def register(client: TestClient, email: str = USER_EMAIL, password: str = PASSWORD):
    return client.post("/auth/register", json={"email": email, "password": password})


def login(client: TestClient, email: str = USER_EMAIL, password: str = PASSWORD):
    return client.post("/auth/login", data={"username": email, "password": password})


def test_register_returns_user_without_password(client: TestClient) -> None:
    response = register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == USER_EMAIL
    assert isinstance(body["id"], int)
    assert "created_at" in body
    assert "password" not in body
    assert "hashed_password" not in body


def test_register_lowercases_email(client: TestClient) -> None:
    response = register(client, email="Alice@Example.com")
    assert response.status_code == 201
    assert response.json()["email"] == "alice@example.com"


def test_register_duplicate_returns_409(client: TestClient) -> None:
    register(client)
    response = register(client)
    assert response.status_code == 409
    assert response.json() == {"detail": "Email already registered"}


def test_register_duplicate_is_case_insensitive(client: TestClient) -> None:
    register(client)
    assert register(client, email="ALICE@example.com").status_code == 409


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("not-an-email", PASSWORD),
        ("", PASSWORD),
        (USER_EMAIL, "short"),
        (USER_EMAIL, "1234567"),
        (USER_EMAIL, "x" * 129),
    ],
)
def test_register_invalid_input_returns_422(client: TestClient, email: str, password: str) -> None:
    assert register(client, email=email, password=password).status_code == 422


def test_register_missing_fields_returns_422(client: TestClient) -> None:
    assert client.post("/auth/register", json={}).status_code == 422


def test_login_returns_bearer_token(client: TestClient) -> None:
    register(client)
    response = login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_email_is_case_insensitive(client: TestClient) -> None:
    register(client)
    assert login(client, email="ALICE@EXAMPLE.COM").status_code == 200


def test_login_wrong_password_returns_401(client: TestClient) -> None:
    register(client)
    response = login(client, password="wrong-password")
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect email or password"}


def test_login_unknown_user_returns_401(client: TestClient) -> None:
    response = login(client, email="nobody@example.com")
    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect email or password"}


def test_me_returns_current_user(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == USER_EMAIL


def test_me_without_token_returns_401(client: TestClient) -> None:
    assert client.get("/auth/me").status_code == 401
