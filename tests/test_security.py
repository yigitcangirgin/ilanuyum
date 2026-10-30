"""Tests for password hashing, JWT helpers and token rejection by the API."""

from datetime import timedelta

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_is_not_plain_text() -> None:
    assert hash_password("supersecret1") != "supersecret1"


def test_verify_password_accepts_correct_and_rejects_wrong() -> None:
    hashed = hash_password("supersecret1")
    assert verify_password("supersecret1", hashed) is True
    assert verify_password("another-pass", hashed) is False


def test_same_password_gets_different_hashes() -> None:
    # Her hash'te rastgele salt kullanılır.
    assert hash_password("supersecret1") != hash_password("supersecret1")


def test_token_roundtrip_returns_subject() -> None:
    assert decode_access_token(create_access_token("42")) == "42"


def test_decode_garbage_returns_none() -> None:
    assert decode_access_token("not.a.jwt") is None


def test_decode_expired_token_returns_none() -> None:
    token = create_access_token("42", timedelta(minutes=-5))
    assert decode_access_token(token) is None


def test_decode_token_signed_with_other_key_returns_none() -> None:
    token = jwt.encode({"sub": "42"}, "some-other-secret-key-of-length-32!", algorithm="HS256")
    assert decode_access_token(token) is None


def test_decode_token_without_subject_returns_none() -> None:
    token = jwt.encode({"foo": "bar"}, settings.secret_key, algorithm=settings.algorithm)
    assert decode_access_token(token) is None


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_api_rejects_expired_token(client: TestClient, auth_headers: dict[str, str]) -> None:
    me = client.get("/auth/me", headers=auth_headers).json()
    token = create_access_token(str(me["id"]), timedelta(minutes=-1))
    response = client.get("/auth/me", headers=_bearer(token))
    assert response.status_code == 401


def test_api_rejects_tampered_token(client: TestClient, auth_headers: dict[str, str]) -> None:
    token = auth_headers["Authorization"].removeprefix("Bearer ")
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    assert client.get("/auth/me", headers=_bearer(tampered)).status_code == 401


@pytest.mark.parametrize("subject", ["abc", "999999"])
def test_api_rejects_token_with_bad_or_unknown_subject(client: TestClient, subject: str) -> None:
    # Geçerli imza ama sub sayı değil / kullanıcı yok.
    response = client.get("/auth/me", headers=_bearer(create_access_token(subject)))
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_api_rejects_malformed_authorization_header(client: TestClient) -> None:
    response = client.get("/auth/me", headers={"Authorization": "Token abc"})
    assert response.status_code == 401
