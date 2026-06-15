from __future__ import annotations

from collections.abc import Iterable

import httpx
import pytest

from backend.core.config import Settings
from backend.llm.client import MockLLMClient, OpenAICompatibleClient


class FakeClient:
    def __init__(self, outcomes: Iterable[httpx.Response | Exception]) -> None:
        self.outcomes = iter(outcomes)
        self.calls = 0
        self.last_payload: dict | None = None

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def post(self, *_args: object, **_kwargs: object) -> httpx.Response:
        self.calls += 1
        self.last_payload = _kwargs.get("json")  # type: ignore[assignment]
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def response(status_code: int, content: str = "review") -> httpx.Response:
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    return httpx.Response(
        status_code,
        request=request,
        json={"choices": [{"message": {"content": content}}]},
    )


def settings(**overrides: object) -> Settings:
    values = {
        "OPENAI_API_KEY": "test-key",
        "OPENAI_BASE_URL": "https://example.test/v1",
        **overrides,
    }
    return Settings(**values)


def install_fake_client(monkeypatch: pytest.MonkeyPatch, fake: FakeClient) -> None:
    monkeypatch.setattr("backend.llm.client.httpx.Client", lambda **_kwargs: fake)


def test_openai_compatible_client_returns_review_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient([response(200, "complete review")])
    install_fake_client(monkeypatch, fake)

    result = OpenAICompatibleClient(settings(), sleep=lambda _delay: None).generate_review("prompt")

    assert result == "complete review"
    assert fake.calls == 1


def test_openai_compatible_client_retries_request_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    fake = FakeClient([httpx.ConnectError("temporary", request=request), response(200)])
    delays: list[float] = []
    install_fake_client(monkeypatch, fake)

    OpenAICompatibleClient(settings(), sleep=delays.append).generate_review("prompt")

    assert fake.calls == 2
    assert delays == [1.0]


@pytest.mark.parametrize("status_code", [408, 409, 429, 500, 503])
def test_openai_compatible_client_retries_transient_statuses(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
) -> None:
    fake = FakeClient([response(status_code), response(200)])
    install_fake_client(monkeypatch, fake)

    OpenAICompatibleClient(settings(), sleep=lambda _delay: None).generate_review("prompt")

    assert fake.calls == 2


def test_openai_compatible_client_uses_exponential_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient([response(500), response(500), response(200)])
    delays: list[float] = []
    install_fake_client(monkeypatch, fake)

    OpenAICompatibleClient(settings(), sleep=delays.append).generate_review("prompt")

    assert delays == [1.0, 2.0]
    assert fake.calls == 3


def test_openai_compatible_client_stops_after_max_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient([response(500), response(500), response(500)])
    install_fake_client(monkeypatch, fake)

    with pytest.raises(httpx.HTTPStatusError):
        OpenAICompatibleClient(settings(), sleep=lambda _delay: None).generate_review("prompt")

    assert fake.calls == 3


def test_openai_compatible_client_respects_configurable_max_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient([response(500), response(500), response(500), response(500)])
    install_fake_client(monkeypatch, fake)

    with pytest.raises(httpx.HTTPStatusError):
        OpenAICompatibleClient(settings(LLM_MAX_RETRIES=3), sleep=lambda _delay: None).generate_review("prompt")

    assert fake.calls == 4


def test_openai_compatible_client_does_not_retry_non_transient_4xx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeClient([response(400)])
    install_fake_client(monkeypatch, fake)

    with pytest.raises(httpx.HTTPStatusError):
        OpenAICompatibleClient(settings(), sleep=lambda _delay: None).generate_review("prompt")

    assert fake.calls == 1


def test_openai_compatible_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is missing"):
        OpenAICompatibleClient(settings(OPENAI_API_KEY=None)).generate_review("prompt")


def test_openai_compatible_client_requests_json_for_structured_agent_prompts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeClient([response(200, '{"findings": []}')])
    install_fake_client(monkeypatch, fake)

    OpenAICompatibleClient(settings()).generate_review("Return only JSON: {\"findings\": []}")

    assert fake.last_payload is not None
    assert "Return only valid JSON" in fake.last_payload["messages"][0]["content"]


def test_mock_client_remains_deterministic() -> None:
    first = MockLLMClient().generate_review("Repository language: Python\nAnalyzed files: 3")
    second = MockLLMClient().generate_review("Repository language: Python\nAnalyzed files: 3")

    assert first == second


def test_mock_client_uses_repository_evidence_in_findings() -> None:
    report = MockLLMClient().generate_review(
        "Repository language: Python\n"
        "Analyzed files: 2\n"
        "Risk Hotspots:\n"
        "- High dependency pressure in services/core.py: 4 modules depend on this file.\n"
        "Recommended Reading Order:\n"
        "- 1. app.py: Start here.\n"
        "Refactoring Candidates:\n"
        "- Stabilize the boundary around services/core.py: Add contract tests.\n"
        "Architecture Summary Context:\n"
    )

    assert "High dependency pressure in services/core.py" in report
    assert "Stabilize the boundary around services/core.py" in report


def test_openai_compatible_client_retries_read_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    fake = FakeClient([httpx.ReadTimeout("read timed out", request=request), response(200)])
    delays: list[float] = []
    install_fake_client(monkeypatch, fake)

    result = OpenAICompatibleClient(settings(), sleep=delays.append).generate_review("prompt")

    assert result == "review"
    assert fake.calls == 2
    assert delays == [1.0]


def test_openai_compatible_client_retries_connect_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    fake = FakeClient([httpx.ConnectTimeout("connect timed out", request=request), response(200)])
    delays: list[float] = []
    install_fake_client(monkeypatch, fake)

    result = OpenAICompatibleClient(settings(), sleep=delays.append).generate_review("prompt")

    assert result == "review"
    assert fake.calls == 2


def test_openai_compatible_client_stops_after_max_timeout_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    fake = FakeClient([
        httpx.ReadTimeout("timeout 1", request=request),
        httpx.ReadTimeout("timeout 2", request=request),
        httpx.ReadTimeout("timeout 3", request=request),
    ])
    install_fake_client(monkeypatch, fake)

    with pytest.raises(httpx.ReadTimeout):
        OpenAICompatibleClient(settings(), sleep=lambda _delay: None).generate_review("prompt")

    assert fake.calls == 3


def test_openai_compatible_client_uses_configurable_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeClient([response(200)])
    captured_kwargs: dict = {}

    def capturing_lambda(**kwargs):
        captured_kwargs.update(kwargs)
        return fake

    monkeypatch.setattr("backend.llm.client.httpx.Client", capturing_lambda)

    OpenAICompatibleClient(
        settings(
            LLM_CONNECT_TIMEOUT_SECONDS=5,
            LLM_READ_TIMEOUT_SECONDS=120,
            LLM_WRITE_TIMEOUT_SECONDS=15,
            LLM_POOL_TIMEOUT_SECONDS=8,
        ),
        sleep=lambda _delay: None,
    ).generate_review("prompt")

    assert "timeout" in captured_kwargs
    timeout = captured_kwargs["timeout"]
    assert timeout.connect == 5.0
    assert timeout.read == 120.0
    assert timeout.write == 15.0
    assert timeout.pool == 8.0
