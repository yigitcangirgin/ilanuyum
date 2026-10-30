"""Tests for the HTML pages."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize("path", ["/", "/app"])
def test_page_returns_html_with_brand(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "İlanUyum" in response.text


@pytest.mark.parametrize("path", ["/", "/app"])
def test_pages_are_hidden_from_openapi(client: TestClient, path: str) -> None:
    assert path not in client.get("/openapi.json").json()["paths"]
