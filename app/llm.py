"""Minimal LLM clients (Anthropic and OpenAI) over plain HTTP.

No vendor SDK is used: both providers are called with httpx, which keeps the
dependency list short and makes the clients easy to test with
``httpx.MockTransport``. Every client exposes the same method,
``complete(system, user) -> str``, so the rest of the app does not care which
provider is configured.
"""

from typing import Protocol

import httpx

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MAX_OUTPUT_TOKENS = 1024


class LLMError(Exception):
    """The provider failed or returned something unusable."""


class LLMClient(Protocol):
    model: str

    def complete(self, system: str, user: str) -> str:
        """Return the model's text answer for one system + user prompt."""
        ...


class _HttpClientMixin:
    _http: httpx.Client

    def close(self) -> None:
        self._http.close()


class AnthropicClient(_HttpClientMixin):
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self._http = httpx.Client(
            timeout=timeout,
            transport=transport,
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
        )

    def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "temperature": 0,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        data = _post_json(self._http, ANTHROPIC_URL, payload)
        try:
            return "".join(
                block["text"] for block in data["content"] if block.get("type") == "text"
            )
        except (KeyError, TypeError) as exc:
            raise LLMError("unexpected Anthropic response shape") from exc


class OpenAIClient(_HttpClientMixin):
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self._http = httpx.Client(
            timeout=timeout,
            transport=transport,
            headers={"authorization": f"Bearer {api_key}", "content-type": "application/json"},
        )

    def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        data = _post_json(self._http, OPENAI_URL, payload)
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("unexpected OpenAI response shape") from exc


def _post_json(http: httpx.Client, url: str, payload: dict) -> dict:
    try:
        response = http.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise LLMError(f"could not reach the LLM provider: {exc.__class__.__name__}") from exc
    if response.status_code != 200:
        # The body may echo the request; only the status code is surfaced.
        raise LLMError(f"LLM provider returned HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise LLMError("LLM provider returned invalid JSON") from exc
