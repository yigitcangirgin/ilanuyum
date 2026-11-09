"""CV <-> job posting match analysis: endpoint, parsing and LLM clients."""

import json
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from app.deps import get_llm_client
from app.llm import AnthropicClient, LLMError, OpenAIClient
from app.main import app
from app.matching import SYSTEM_PROMPT, analyse_match, parse_match_result

CV = "Python backend developer. FastAPI, SQLAlchemy, PostgreSQL, Docker, pytest, JWT auth. " * 2
JOB = "We need a backend developer with FastAPI, PostgreSQL and Kubernetes experience. " * 2

VALID_ANSWER = {
    "score": 72,
    "summary": "Strong FastAPI and PostgreSQL match; no Kubernetes experience.",
    "matched_skills": ["FastAPI", "PostgreSQL", "Docker"],
    "missing_skills": ["Kubernetes"],
    "suggestions": ["Mention the Docker Compose setup in the CV."],
}


class FakeLLM:
    """Returns queued answers and records every prompt it receives."""

    def __init__(self, *answers: str) -> None:
        self.model = "fake-model"
        self.answers = list(answers)
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if not self.answers:
            raise LLMError("no more answers")
        return self.answers.pop(0)


@pytest.fixture
def use_llm(client: TestClient) -> Iterator[Callable[..., FakeLLM]]:
    """Install a FakeLLM as the app's LLM client for one test."""

    def _install(*answers: str) -> FakeLLM:
        fake = FakeLLM(*answers)
        app.dependency_overrides[get_llm_client] = lambda: fake
        return fake

    yield _install
    app.dependency_overrides.pop(get_llm_client, None)


def _match(client: TestClient, headers: dict[str, str], app_id: int, **body: Any):
    return client.post(
        f"/applications/{app_id}/match", json={"cv_text": CV, **body}, headers=headers
    )


# --- endpoint ---------------------------------------------------------------


def test_match_creates_and_returns_analysis(client, auth_headers, make_application, use_llm):
    fake = use_llm(json.dumps(VALID_ANSWER))
    application = make_application(auth_headers, job_description=JOB)

    response = _match(client, auth_headers, application["id"])

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["score"] == 72
    assert body["missing_skills"] == ["Kubernetes"]
    assert body["model"] == "fake-model"
    assert body["application_id"] == application["id"]
    # Both texts reach the model inside their tags.
    system, user = fake.calls[0]
    assert system == SYSTEM_PROMPT
    assert "<cv>" in user and "<job_posting>" in user and "Kubernetes" in user


def test_job_description_in_request_is_saved(client, auth_headers, make_application, use_llm):
    use_llm(json.dumps(VALID_ANSWER))
    application = make_application(auth_headers)

    response = _match(client, auth_headers, application["id"], job_description=JOB)

    assert response.status_code == 201
    saved = client.get(f"/applications/{application['id']}", headers=auth_headers).json()
    assert saved["job_description"] == JOB.strip()


def test_missing_job_description_returns_422(client, auth_headers, make_application, use_llm):
    fake = use_llm(json.dumps(VALID_ANSWER))
    application = make_application(auth_headers)

    response = _match(client, auth_headers, application["id"])

    assert response.status_code == 422
    assert fake.calls == []  # no paid LLM call was made


def test_short_cv_is_rejected(client, auth_headers, make_application, use_llm):
    use_llm(json.dumps(VALID_ANSWER))
    application = make_application(auth_headers, job_description=JOB)

    response = client.post(
        f"/applications/{application['id']}/match",
        json={"cv_text": "too short"},
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_other_users_application_returns_404(
    client, auth_headers, other_auth_headers, make_application, use_llm
):
    fake = use_llm(json.dumps(VALID_ANSWER))
    application = make_application(auth_headers, job_description=JOB)

    assert _match(client, other_auth_headers, application["id"]).status_code == 404
    lists = client.get(f"/applications/{application['id']}/matches", headers=other_auth_headers)
    assert lists.status_code == 404
    assert fake.calls == []


def test_match_requires_authentication(client, make_application, auth_headers, use_llm):
    use_llm(json.dumps(VALID_ANSWER))
    application = make_application(auth_headers, job_description=JOB)

    assert (
        client.post(f"/applications/{application['id']}/match", json={"cv_text": CV}).status_code
        == 401
    )


def test_invalid_answer_is_retried_once(client, auth_headers, make_application, use_llm):
    fake = use_llm("Sure! Here is my analysis: not json", json.dumps(VALID_ANSWER))
    application = make_application(auth_headers, job_description=JOB)

    response = _match(client, auth_headers, application["id"])

    assert response.status_code == 201
    assert len(fake.calls) == 2


def test_two_invalid_answers_return_502_and_store_nothing(
    client, auth_headers, make_application, use_llm
):
    bad = json.dumps({**VALID_ANSWER, "score": 250})
    use_llm(bad, bad)
    application = make_application(auth_headers)

    response = _match(client, auth_headers, application["id"], job_description=JOB)

    assert response.status_code == 502
    history = client.get(f"/applications/{application['id']}/matches", headers=auth_headers)
    assert history.json() == []
    # The job description sent with the failed request was rolled back too.
    saved = client.get(f"/applications/{application['id']}", headers=auth_headers).json()
    assert saved["job_description"] is None


def test_provider_error_returns_502(client, auth_headers, make_application, use_llm):
    use_llm()  # FakeLLM with no answers raises LLMError
    application = make_application(auth_headers, job_description=JOB)

    assert _match(client, auth_headers, application["id"]).status_code == 502


def test_history_is_newest_first(client, auth_headers, make_application, use_llm):
    use_llm(json.dumps(VALID_ANSWER), json.dumps({**VALID_ANSWER, "score": 90}))
    application = make_application(auth_headers, job_description=JOB)
    _match(client, auth_headers, application["id"])
    _match(client, auth_headers, application["id"])

    history = client.get(f"/applications/{application['id']}/matches", headers=auth_headers)

    assert history.status_code == 200
    assert [item["score"] for item in history.json()] == [90, 72]


def test_deleting_application_deletes_its_analyses(client, auth_headers, make_application, use_llm):
    use_llm(json.dumps(VALID_ANSWER))
    application = make_application(auth_headers, job_description=JOB)
    _match(client, auth_headers, application["id"])

    response = client.delete(f"/applications/{application['id']}", headers=auth_headers)

    assert response.status_code == 204
    assert (
        client.get(f"/applications/{application['id']}/matches", headers=auth_headers).status_code
        == 404
    )


def test_without_api_key_returns_503(client, auth_headers, make_application, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "anthropic_api_key", None)
    monkeypatch.setattr(settings, "openai_api_key", None)
    application = make_application(auth_headers, job_description=JOB)

    assert _match(client, auth_headers, application["id"]).status_code == 503


# --- parsing ----------------------------------------------------------------


def test_parse_accepts_json_wrapped_in_text_or_code_fence():
    raw = "```json\n" + json.dumps(VALID_ANSWER) + "\n```"
    assert parse_match_result(raw).score == 72


@pytest.mark.parametrize(
    "raw",
    [
        "no json here",
        "{not valid json}",
        json.dumps({**VALID_ANSWER, "score": -1}),
        json.dumps({k: v for k, v in VALID_ANSWER.items() if k != "summary"}),
    ],
)
def test_parse_rejects_bad_answers(raw):
    with pytest.raises(ValueError):
        parse_match_result(raw)


def test_analyse_match_gives_up_after_two_bad_answers():
    fake = FakeLLM("nope", "still nope")
    with pytest.raises(LLMError):
        analyse_match(fake, CV, JOB, "Backend Developer", "Acme")
    assert len(fake.calls) == 2


# --- HTTP clients (no network: httpx.MockTransport) --------------------------


def _transport(status: int, body: dict, seen: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json=body)

    return httpx.MockTransport(handler)


def test_anthropic_client_request_and_response():
    seen: list[httpx.Request] = []
    body = {"content": [{"type": "text", "text": '{"score": 1}'}]}
    client = AnthropicClient("key-123", "claude-test", transport=_transport(200, body, seen))

    assert client.complete("sys", "hello") == '{"score": 1}'
    request = seen[0]
    assert str(request.url) == "https://api.anthropic.com/v1/messages"
    assert request.headers["x-api-key"] == "key-123"
    assert request.headers["anthropic-version"] == "2023-06-01"
    sent = json.loads(request.content)
    assert sent["model"] == "claude-test"
    assert sent["system"] == "sys"
    assert sent["messages"] == [{"role": "user", "content": "hello"}]


def test_openai_client_request_and_response():
    seen: list[httpx.Request] = []
    body = {"choices": [{"message": {"content": '{"score": 2}'}}]}
    client = OpenAIClient("key-456", "gpt-test", transport=_transport(200, body, seen))

    assert client.complete("sys", "hello") == '{"score": 2}'
    request = seen[0]
    assert str(request.url) == "https://api.openai.com/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer key-456"
    sent = json.loads(request.content)
    assert sent["response_format"] == {"type": "json_object"}
    assert sent["messages"][0] == {"role": "system", "content": "sys"}


@pytest.mark.parametrize("client_cls", [AnthropicClient, OpenAIClient])
def test_clients_raise_llm_error_on_http_error(client_cls):
    client = client_cls("k", "m", transport=_transport(429, {"error": "rate limited"}, []))
    with pytest.raises(LLMError, match="429"):
        client.complete("sys", "hello")


@pytest.mark.parametrize("client_cls", [AnthropicClient, OpenAIClient])
def test_clients_raise_llm_error_on_unexpected_shape(client_cls):
    client = client_cls("k", "m", transport=_transport(200, {"unexpected": True}, []))
    with pytest.raises(LLMError):
        client.complete("sys", "hello")
