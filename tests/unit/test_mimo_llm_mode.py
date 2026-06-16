from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.errors import APIError, install_error_handlers
from backend.api.reviews import build_reviews_router
from backend.core.config import Settings
from backend.llm.client import MockLLMClient, OpenAICompatibleClient, build_llm_client_for_mode
from backend.storage.sqlite import ReviewStore


class FakeRunner:
    def __init__(self, store: ReviewStore, settings: Settings) -> None:
        self.store = store
        self.settings = settings
        self.submissions: list[tuple[str, str]] = []

    def submit(self, repo_url: str, llm_mode: str = "mock") -> str:
        if llm_mode != "mock":
            try:
                build_llm_client_for_mode(self.settings, llm_mode)
            except RuntimeError as exc:
                raise APIError(
                    400,
                    "LLM configuration error",
                    "llm_config_error",
                    str(exc),
                ) from exc
        task_id = f"task-{len(self.submissions) + 1}"
        self.submissions.append((repo_url, llm_mode))
        self.store.create_review(task_id, repo_url)
        return task_id


@pytest.fixture
def settings_no_mimo_key(tmp_path) -> Settings:
    return Settings(
        DATABASE_PATH=str(tmp_path / "test.db"),
        WORKSPACE_PATH=str(tmp_path / "workspace"),
        REPORTS_PATH=str(tmp_path / "reports"),
        MIMO_API_KEY=None,
    )


@pytest.fixture
def settings_with_mimo_key(tmp_path) -> Settings:
    return Settings(
        DATABASE_PATH=str(tmp_path / "test.db"),
        WORKSPACE_PATH=str(tmp_path / "workspace"),
        REPORTS_PATH=str(tmp_path / "reports"),
        MIMO_API_KEY="test-mimo-key",
    )


def test_build_llm_client_for_mode_mock(settings_no_mimo_key: Settings) -> None:
    client = build_llm_client_for_mode(settings_no_mimo_key, "mock")
    assert isinstance(client, MockLLMClient)


def test_build_llm_client_for_mode_mimo_missing_key(settings_no_mimo_key: Settings) -> None:
    with pytest.raises(RuntimeError, match="MIMO_API_KEY is missing"):
        build_llm_client_for_mode(settings_no_mimo_key, "mimo")


def test_build_llm_client_for_mode_mimo_with_key(settings_with_mimo_key: Settings) -> None:
    client = build_llm_client_for_mode(settings_with_mimo_key, "mimo")
    assert isinstance(client, OpenAICompatibleClient)


def test_build_llm_client_for_mode_mimo_uses_correct_settings(settings_with_mimo_key: Settings) -> None:
    client = build_llm_client_for_mode(settings_with_mimo_key, "mimo")
    assert isinstance(client, OpenAICompatibleClient)
    assert client.resolved.provider == "mimo"
    assert client.resolved.api_key == "test-mimo-key"
    assert client.resolved.base_url == "https://token-plan-cn.xiaomimimo.com/v1"
    assert client.resolved.model == "mimo-v2.5-pro"
    assert client.resolved.api_key_env_name == "MIMO_API_KEY"


def test_build_llm_client_for_mode_unknown_raises() -> None:
    settings = Settings()
    with pytest.raises(ValueError, match="Unknown llm_mode"):
        build_llm_client_for_mode(settings, "unknown")


def test_build_llm_client_for_mode_does_not_expose_key_in_error(settings_no_mimo_key: Settings) -> None:
    with pytest.raises(RuntimeError) as exc_info:
        build_llm_client_for_mode(settings_no_mimo_key, "mimo")
    error_msg = str(exc_info.value)
    assert "test-mimo-key" not in error_msg
    assert "MIMO_API_KEY" in error_msg
    assert "OPENAI_API_KEY" not in error_msg


def test_api_default_review_uses_mock(tmp_path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    settings = Settings(
        DATABASE_PATH=str(tmp_path / "test.db"),
        WORKSPACE_PATH=str(tmp_path / "workspace"),
        REPORTS_PATH=str(tmp_path / "reports"),
    )
    runner = FakeRunner(store, settings)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(build_reviews_router(store, runner))
    client = TestClient(app)

    response = client.post("/api/reviews", json={"repo_url": "https://github.com/pallets/flask"})

    assert response.status_code == 202
    body = response.json()
    assert body["llm_mode"] == "mock"


def test_api_llm_mode_mock_explicit(tmp_path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    settings = Settings(
        DATABASE_PATH=str(tmp_path / "test.db"),
        WORKSPACE_PATH=str(tmp_path / "workspace"),
        REPORTS_PATH=str(tmp_path / "reports"),
    )
    runner = FakeRunner(store, settings)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(build_reviews_router(store, runner))
    client = TestClient(app)

    response = client.post(
        "/api/reviews",
        json={"repo_url": "https://github.com/pallets/flask", "llm_mode": "mock"},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["llm_mode"] == "mock"


def test_api_llm_mode_mimo_without_key_returns_error(tmp_path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    settings = Settings(
        DATABASE_PATH=str(tmp_path / "test.db"),
        WORKSPACE_PATH=str(tmp_path / "workspace"),
        REPORTS_PATH=str(tmp_path / "reports"),
        MIMO_API_KEY=None,
    )
    runner = FakeRunner(store, settings)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(build_reviews_router(store, runner))
    client = TestClient(app)

    response = client.post(
        "/api/reviews",
        json={"repo_url": "https://github.com/pallets/flask", "llm_mode": "mimo"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "llm_config_error"
    assert "MIMO_API_KEY is missing" in body["detail"]
    assert "OPENAI_API_KEY" not in body["detail"]


def test_api_llm_mode_mimo_error_does_not_expose_secret(tmp_path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    settings = Settings(
        DATABASE_PATH=str(tmp_path / "test.db"),
        WORKSPACE_PATH=str(tmp_path / "workspace"),
        REPORTS_PATH=str(tmp_path / "reports"),
        MIMO_API_KEY=None,
    )
    runner = FakeRunner(store, settings)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(build_reviews_router(store, runner))
    client = TestClient(app)

    response = client.post(
        "/api/reviews",
        json={"repo_url": "https://github.com/pallets/flask", "llm_mode": "mimo"},
    )

    body = response.json()
    assert "test-mimo-key" not in str(body)
    assert "secret" not in str(body).lower()
    assert "password" not in str(body).lower()


def test_api_request_without_llm_mode_backward_compatible(tmp_path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    settings = Settings(
        DATABASE_PATH=str(tmp_path / "test.db"),
        WORKSPACE_PATH=str(tmp_path / "workspace"),
        REPORTS_PATH=str(tmp_path / "reports"),
    )
    runner = FakeRunner(store, settings)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(build_reviews_router(store, runner))
    client = TestClient(app)

    response = client.post("/api/reviews", json={"repo_url": "https://github.com/pallets/flask"})

    assert response.status_code == 202
    assert response.json()["task_id"] == "task-1"
    assert runner.submissions[0] == ("https://github.com/pallets/flask", "mock")


def test_api_llm_mode_mimo_invalid_value_rejected(tmp_path) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    settings = Settings(
        DATABASE_PATH=str(tmp_path / "test.db"),
        WORKSPACE_PATH=str(tmp_path / "workspace"),
        REPORTS_PATH=str(tmp_path / "reports"),
    )
    runner = FakeRunner(store, settings)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(build_reviews_router(store, runner))
    client = TestClient(app)

    response = client.post(
        "/api/reviews",
        json={"repo_url": "https://github.com/pallets/flask", "llm_mode": "invalid"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
