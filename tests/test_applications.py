"""Tests for /applications: CRUD, PATCH vs PUT, filters, pagination, stats, ownership."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

Headers = dict[str, str]
Factory = Callable[..., dict[str, Any]]

STATUS_KEYS = {"applied", "interview", "offer", "rejected"}


# ---------- auth ----------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/applications"),
        ("GET", "/applications/stats"),
        ("POST", "/applications"),
        ("GET", "/applications/1"),
        ("PUT", "/applications/1"),
        ("PATCH", "/applications/1"),
        ("DELETE", "/applications/1"),
    ],
)
def test_endpoints_require_authentication(client: TestClient, method: str, path: str) -> None:
    assert client.request(method, path).status_code == 401


# ---------- create / read ----------


def test_create_with_defaults(client: TestClient, auth_headers: Headers) -> None:
    payload = {"company": "Acme", "position": "Dev"}
    response = client.post("/applications", json=payload, headers=auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["company"] == "Acme"
    assert body["status"] == "applied"
    assert body["job_url"] is None
    assert body["notes"] is None
    assert body["applied_at"]
    assert body["id"] and body["created_at"] and body["updated_at"]


def test_create_with_all_fields(client: TestClient, auth_headers: Headers) -> None:
    payload = {
        "company": "Acme",
        "position": "Dev",
        "job_url": "https://acme.example.com/jobs/1",
        "status": "interview",
        "applied_at": "2025-03-01",
        "notes": "Referred by a friend",
    }
    response = client.post("/applications", json=payload, headers=auth_headers)
    assert response.status_code == 201
    assert response.json().items() >= payload.items()


def test_create_strips_whitespace(client: TestClient, auth_headers: Headers) -> None:
    payload = {"company": "  Acme  ", "position": " Dev "}
    body = client.post("/applications", json=payload, headers=auth_headers).json()
    assert (body["company"], body["position"]) == ("Acme", "Dev")


def test_get_returns_created_application(
    client: TestClient, auth_headers: Headers, make_application: Factory
) -> None:
    created = make_application(auth_headers)
    response = client.get(f"/applications/{created['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == created


def test_get_missing_returns_404(client: TestClient, auth_headers: Headers) -> None:
    response = client.get("/applications/9999", headers=auth_headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "Application not found"}


# ---------- validation ----------


@pytest.mark.parametrize(
    "bad_fields",
    [
        {"company": ""},
        {"company": "   "},
        {"company": "x" * 201},
        {"position": ""},
        {"position": "x" * 201},
        {"status": "hired"},
        {"applied_at": "not-a-date"},
        {"notes": "x" * 5001},
        {"job_url": "ftp://example.com/job"},
        {"job_url": "example.com/job"},
        {"job_url": "https://example.com/" + "a" * 500},
    ],
)
def test_create_invalid_input_returns_422(
    client: TestClient, auth_headers: Headers, bad_fields: dict[str, Any]
) -> None:
    payload = {"company": "Acme", "position": "Dev", **bad_fields}
    assert client.post("/applications", json=payload, headers=auth_headers).status_code == 422


@pytest.mark.parametrize("missing", ["company", "position"])
def test_create_missing_required_field_returns_422(
    client: TestClient, auth_headers: Headers, missing: str
) -> None:
    payload = {"company": "Acme", "position": "Dev"}
    del payload[missing]
    assert client.post("/applications", json=payload, headers=auth_headers).status_code == 422


@pytest.mark.parametrize("empty", ["", "   "])
def test_empty_job_url_is_stored_as_null(
    client: TestClient, auth_headers: Headers, empty: str
) -> None:
    payload = {"company": "Acme", "position": "Dev", "job_url": empty}
    response = client.post("/applications", json=payload, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["job_url"] is None


def test_http_job_url_is_accepted(client: TestClient, auth_headers: Headers) -> None:
    payload = {"company": "Acme", "position": "Dev", "job_url": "http://example.com/j"}
    assert client.post("/applications", json=payload, headers=auth_headers).status_code == 201


# ---------- PUT vs PATCH ----------


def test_put_replaces_all_fields(
    client: TestClient, auth_headers: Headers, make_application: Factory
) -> None:
    created = make_application(
        auth_headers, job_url="https://example.com/j", status="offer", notes="old"
    )
    new_data = {"company": "NewCo", "position": "Lead"}
    response = client.put(f"/applications/{created['id']}", json=new_data, headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert (body["company"], body["position"]) == ("NewCo", "Lead")
    # PUT'ta gönderilmeyen alanlar varsayılana döner.
    assert body["status"] == "applied"
    assert body["job_url"] is None
    assert body["notes"] is None


def test_put_requires_full_body(
    client: TestClient, auth_headers: Headers, make_application: Factory
) -> None:
    created = make_application(auth_headers)
    response = client.put(
        f"/applications/{created['id']}", json={"company": "OnlyCompany"}, headers=auth_headers
    )
    assert response.status_code == 422


def test_patch_changes_only_sent_fields(
    client: TestClient, auth_headers: Headers, make_application: Factory
) -> None:
    created = make_application(
        auth_headers, job_url="https://example.com/j", notes="keep me", applied_at="2025-01-15"
    )
    response = client.patch(
        f"/applications/{created['id']}", json={"status": "interview"}, headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "interview"
    for field in ("company", "position", "job_url", "notes", "applied_at"):
        assert body[field] == created[field]


def test_patch_can_clear_nullable_fields(
    client: TestClient, auth_headers: Headers, make_application: Factory
) -> None:
    created = make_application(auth_headers, notes="remove me", job_url="https://example.com/j")
    response = client.patch(
        f"/applications/{created['id']}",
        json={"notes": None, "job_url": None},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["notes"] is None
    assert response.json()["job_url"] is None


def test_patch_persists(
    client: TestClient, auth_headers: Headers, make_application: Factory
) -> None:
    created = make_application(auth_headers)
    client.patch(f"/applications/{created['id']}", json={"company": "Zed"}, headers=auth_headers)
    fetched = client.get(f"/applications/{created['id']}", headers=auth_headers).json()
    assert fetched["company"] == "Zed"


@pytest.mark.parametrize("field", ["company", "position", "status", "applied_at"])
def test_patch_explicit_null_on_required_field_returns_422(
    client: TestClient, auth_headers: Headers, make_application: Factory, field: str
) -> None:
    created = make_application(auth_headers)
    response = client.patch(
        f"/applications/{created['id']}", json={field: None}, headers=auth_headers
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "bad_fields",
    [{"status": "hired"}, {"company": ""}, {"job_url": "ftp://example.com"}],
)
def test_patch_invalid_input_returns_422(
    client: TestClient,
    auth_headers: Headers,
    make_application: Factory,
    bad_fields: dict[str, Any],
) -> None:
    created = make_application(auth_headers)
    response = client.patch(f"/applications/{created['id']}", json=bad_fields, headers=auth_headers)
    assert response.status_code == 422


# ---------- delete ----------


def test_delete_removes_application(
    client: TestClient, auth_headers: Headers, make_application: Factory
) -> None:
    created = make_application(auth_headers)
    response = client.delete(f"/applications/{created['id']}", headers=auth_headers)
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/applications/{created['id']}", headers=auth_headers).status_code == 404


def test_delete_missing_returns_404(client: TestClient, auth_headers: Headers) -> None:
    assert client.delete("/applications/9999", headers=auth_headers).status_code == 404


# ---------- list: order, filter, pagination ----------


def test_list_is_empty_for_new_user(client: TestClient, auth_headers: Headers) -> None:
    response = client.get("/applications", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


def test_list_orders_newest_applied_at_first_then_id_desc(
    client: TestClient, auth_headers: Headers, make_application: Factory
) -> None:
    old = make_application(auth_headers, applied_at="2025-01-01")
    new_first = make_application(auth_headers, applied_at="2025-06-01")
    new_second = make_application(auth_headers, applied_at="2025-06-01")
    ids = [a["id"] for a in client.get("/applications", headers=auth_headers).json()]
    assert ids == [new_second["id"], new_first["id"], old["id"]]


def test_list_filters_by_status(
    client: TestClient, auth_headers: Headers, make_application: Factory
) -> None:
    make_application(auth_headers, status="applied")
    interview = make_application(auth_headers, status="interview")
    make_application(auth_headers, status="offer")
    response = client.get("/applications", params={"status": "interview"}, headers=auth_headers)
    assert [a["id"] for a in response.json()] == [interview["id"]]


def test_list_invalid_status_filter_returns_422(client: TestClient, auth_headers: Headers) -> None:
    response = client.get("/applications", params={"status": "hired"}, headers=auth_headers)
    assert response.status_code == 422


def test_list_pagination_skip_and_limit(
    client: TestClient, auth_headers: Headers, make_application: Factory
) -> None:
    for day in range(1, 6):
        make_application(auth_headers, applied_at=f"2025-01-0{day}")
    everything = client.get("/applications", headers=auth_headers).json()
    page = client.get("/applications", params={"skip": 1, "limit": 2}, headers=auth_headers).json()
    assert len(everything) == 5
    assert page == everything[1:3]


def test_list_skip_beyond_total_returns_empty(
    client: TestClient, auth_headers: Headers, make_application: Factory
) -> None:
    make_application(auth_headers)
    response = client.get("/applications", params={"skip": 10}, headers=auth_headers)
    assert response.json() == []


@pytest.mark.parametrize(
    "params",
    [{"limit": 101}, {"limit": 0}, {"limit": -1}, {"skip": -1}],
)
def test_list_invalid_pagination_returns_422(
    client: TestClient, auth_headers: Headers, params: dict[str, int]
) -> None:
    assert client.get("/applications", params=params, headers=auth_headers).status_code == 422


def test_list_limit_100_is_allowed(client: TestClient, auth_headers: Headers) -> None:
    assert (
        client.get("/applications", params={"limit": 100}, headers=auth_headers).status_code == 200
    )


# ---------- stats ----------


def test_stats_empty_has_all_four_keys(client: TestClient, auth_headers: Headers) -> None:
    response = client.get("/applications/stats", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {
        "total": 0,
        "by_status": {"applied": 0, "interview": 0, "offer": 0, "rejected": 0},
    }


def test_stats_counts_by_status(
    client: TestClient, auth_headers: Headers, make_application: Factory
) -> None:
    for status in ("applied", "applied", "offer", "rejected"):
        make_application(auth_headers, status=status)
    body = client.get("/applications/stats", headers=auth_headers).json()
    assert body["total"] == 4
    assert set(body["by_status"]) == STATUS_KEYS
    assert body["by_status"] == {"applied": 2, "interview": 0, "offer": 1, "rejected": 1}


def test_stats_follow_status_changes(
    client: TestClient, auth_headers: Headers, make_application: Factory
) -> None:
    created = make_application(auth_headers)
    client.patch(f"/applications/{created['id']}", json={"status": "offer"}, headers=auth_headers)
    by_status = client.get("/applications/stats", headers=auth_headers).json()["by_status"]
    assert by_status["applied"] == 0
    assert by_status["offer"] == 1


def test_stats_route_is_not_treated_as_an_id(client: TestClient, auth_headers: Headers) -> None:
    # /stats, /{id} rotasından önce tanımlı olmalı; yoksa 422 döner.
    assert client.get("/applications/stats", headers=auth_headers).status_code == 200


# ---------- ownership isolation ----------


def test_other_user_sees_empty_list(
    client: TestClient,
    auth_headers: Headers,
    other_auth_headers: Headers,
    make_application: Factory,
) -> None:
    make_application(auth_headers)
    assert client.get("/applications", headers=other_auth_headers).json() == []


@pytest.mark.parametrize(
    ("method", "body"),
    [
        ("GET", None),
        ("PUT", {"company": "Hacked", "position": "Hacker"}),
        ("PATCH", {"company": "Hacked"}),
        ("DELETE", None),
    ],
)
def test_other_user_gets_404_and_cannot_modify(
    client: TestClient,
    auth_headers: Headers,
    other_auth_headers: Headers,
    make_application: Factory,
    method: str,
    body: dict[str, str] | None,
) -> None:
    created = make_application(auth_headers)
    url = f"/applications/{created['id']}"
    response = client.request(method, url, json=body, headers=other_auth_headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "Application not found"}
    # Sahibin kaydı hiç değişmemiş olmalı.
    assert client.get(url, headers=auth_headers).json() == created


def test_stats_never_count_other_users_rows(
    client: TestClient,
    auth_headers: Headers,
    other_auth_headers: Headers,
    make_application: Factory,
) -> None:
    make_application(auth_headers, status="offer")
    make_application(auth_headers, status="offer")
    make_application(other_auth_headers, status="rejected")
    mine = client.get("/applications/stats", headers=auth_headers).json()
    theirs = client.get("/applications/stats", headers=other_auth_headers).json()
    assert mine["total"] == 2
    assert mine["by_status"]["rejected"] == 0
    assert theirs["total"] == 1
    assert theirs["by_status"]["offer"] == 0


def test_status_filter_only_returns_own_rows(
    client: TestClient,
    auth_headers: Headers,
    other_auth_headers: Headers,
    make_application: Factory,
) -> None:
    mine = make_application(auth_headers, status="offer")
    make_application(other_auth_headers, status="offer")
    response = client.get("/applications", params={"status": "offer"}, headers=auth_headers)
    assert [a["id"] for a in response.json()] == [mine["id"]]
