"""Tests for pipeline provider/model label resolution."""

from __future__ import annotations

from backend.core.config import Settings
from backend.tasks.pipeline import ReviewPipeline


def _pipeline_settings(**overrides: object) -> Settings:
    """Create Settings for pipeline tests."""
    return Settings(**overrides)


def test_resolve_token_model_returns_openai_when_no_mimo_key() -> None:
    """Without MIMO_API_KEY, should return openai_model."""
    settings = _pipeline_settings(OPENAI_API_KEY="test-key", MIMO_API_KEY="")
    pipeline = ReviewPipeline(settings=settings, store=None, llm_client=None)

    model = pipeline._resolve_token_model()

    assert model == "gpt-4o-mini"


def test_resolve_token_model_returns_mimo_when_mimo_key_set() -> None:
    """With MIMO_API_KEY set, should return mimo_model_name."""
    settings = _pipeline_settings(
        OPENAI_API_KEY="test-key",
        MIMO_API_KEY="test-mimo-key",
    )
    pipeline = ReviewPipeline(settings=settings, store=None, llm_client=None)

    model = pipeline._resolve_token_model()

    assert model == "mimo-v2.5-pro"


def test_resolve_token_model_returns_custom_mimo_model() -> None:
    """With custom MIMO_MODEL_NAME, should return that model."""
    settings = _pipeline_settings(
        OPENAI_API_KEY="test-key",
        MIMO_API_KEY="test-mimo-key",
        MIMO_MODEL_NAME="custom-mimo-model",
    )
    pipeline = ReviewPipeline(settings=settings, store=None, llm_client=None)

    model = pipeline._resolve_token_model()

    assert model == "custom-mimo-model"


def test_resolve_provider_label_returns_openai_when_no_mimo_key() -> None:
    """Without MIMO_API_KEY, provider should be 'openai'."""
    settings = _pipeline_settings(OPENAI_API_KEY="test-key", MIMO_API_KEY="")
    pipeline = ReviewPipeline(settings=settings, store=None, llm_client=None)

    provider = pipeline._resolve_provider_label()

    assert provider == "openai"


def test_resolve_provider_label_returns_mimo_when_mimo_key_set() -> None:
    """With MIMO_API_KEY set, provider should be 'mimo'."""
    settings = _pipeline_settings(
        OPENAI_API_KEY="test-key",
        MIMO_API_KEY="test-mimo-key",
    )
    pipeline = ReviewPipeline(settings=settings, store=None, llm_client=None)

    provider = pipeline._resolve_provider_label()

    assert provider == "mimo"


def test_resolve_provider_label_not_expose_api_key() -> None:
    """Provider label must never contain API key material."""
    settings = _pipeline_settings(
        OPENAI_API_KEY="sk-secret-key-123",
        MIMO_API_KEY="mimo-secret-key-456",
    )
    pipeline = ReviewPipeline(settings=settings, store=None, llm_client=None)

    provider = pipeline._resolve_provider_label()
    model = pipeline._resolve_token_model()

    assert "sk-secret" not in provider
    assert "mimo-secret" not in provider
    assert "sk-secret" not in model
    assert "mimo-secret" not in model
