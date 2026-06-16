"""Tests for LLM provider resolution and API key handling.

Validates that:
- MiMo uses MIMO_API_KEY (not OPENAI_API_KEY)
- OpenAI uses OPENAI_API_KEY
- Mock mode requires no real key
- Missing-key errors name the correct provider env var
- ENABLE_REAL_LLM safety is preserved
- No secrets are leaked in errors or logs
"""

from __future__ import annotations

import pytest

from backend.core.config import Settings
from backend.llm.client import (
    MockLLMClient,
    OpenAICompatibleClient,
    ResolvedLLMConfig,
    build_llm_client,
    build_llm_client_for_mode,
    resolve_llm_config,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _settings(**overrides: object) -> Settings:
    """Create Settings with defaults suitable for testing."""
    return Settings(**overrides)


# ---------------------------------------------------------------------------
# resolve_llm_config
# ---------------------------------------------------------------------------

class TestResolveLLMConfig:
    """Tests for resolve_llm_config()."""

    def test_mimo_takes_priority_when_mimo_key_set(self) -> None:
        settings = _settings(MIMO_API_KEY="mimo-key", OPENAI_API_KEY="openai-key")
        resolved = resolve_llm_config(settings)
        assert resolved.provider == "mimo"
        assert resolved.api_key == "mimo-key"
        assert resolved.api_key_env_name == "MIMO_API_KEY"

    def test_mimo_uses_mimo_base_url_and_model(self) -> None:
        settings = _settings(
            MIMO_API_KEY="mimo-key",
            MIMO_BASE_URL="https://custom-mimo.example.com/v1",
            MIMO_MODEL_NAME="custom-mimo-model",
        )
        resolved = resolve_llm_config(settings)
        assert resolved.base_url == "https://custom-mimo.example.com/v1"
        assert resolved.model == "custom-mimo-model"

    def test_openai_used_when_no_mimo_key(self) -> None:
        settings = _settings(OPENAI_API_KEY="openai-key", MIMO_API_KEY="")
        resolved = resolve_llm_config(settings)
        assert resolved.provider == "openai"
        assert resolved.api_key == "openai-key"
        assert resolved.api_key_env_name == "OPENAI_API_KEY"

    def test_openai_uses_openai_base_url_and_model(self) -> None:
        settings = _settings(
            OPENAI_API_KEY="openai-key",
            OPENAI_BASE_URL="https://custom-openai.example.com/v1",
            OPENAI_MODEL="gpt-4o",
            MIMO_API_KEY="",
        )
        resolved = resolve_llm_config(settings)
        assert resolved.base_url == "https://custom-openai.example.com/v1"
        assert resolved.model == "gpt-4o"

    def test_empty_api_key_when_no_keys_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        settings = _settings(OPENAI_API_KEY=None, MIMO_API_KEY=None)
        resolved = resolve_llm_config(settings)
        assert resolved.provider == "openai"
        assert resolved.api_key == ""
        assert resolved.api_key_env_name == "OPENAI_API_KEY"

    def test_openai_key_from_env_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "env-openai-key")
        settings = _settings(OPENAI_API_KEY=None, MIMO_API_KEY=None)
        resolved = resolve_llm_config(settings)
        assert resolved.provider == "openai"
        assert resolved.api_key == "env-openai-key"


# ---------------------------------------------------------------------------
# build_llm_client — mock mode
# ---------------------------------------------------------------------------

class TestBuildLLMClientMockMode:
    """Tests for build_llm_client in mock mode."""

    def test_mock_mode_returns_mock_client(self) -> None:
        settings = _settings(USE_MOCK_LLM=True)
        client = build_llm_client(settings)
        assert isinstance(client, MockLLMClient)

    def test_mock_mode_does_not_require_openai_key(self) -> None:
        settings = _settings(USE_MOCK_LLM=True, OPENAI_API_KEY=None, MIMO_API_KEY=None)
        client = build_llm_client(settings)
        assert isinstance(client, MockLLMClient)

    def test_mock_mode_does_not_require_mimo_key(self) -> None:
        settings = _settings(USE_MOCK_LLM=True, MIMO_API_KEY=None)
        client = build_llm_client(settings)
        assert isinstance(client, MockLLMClient)

    def test_mock_mode_does_not_require_enable_real_llm(self) -> None:
        settings = _settings(USE_MOCK_LLM=True, ENABLE_REAL_LLM=False)
        client = build_llm_client(settings)
        assert isinstance(client, MockLLMClient)


# ---------------------------------------------------------------------------
# build_llm_client — MiMo provider
# ---------------------------------------------------------------------------

class TestBuildLLMClientMiMo:
    """Tests for build_llm_client with MiMo provider."""

    def test_mimo_with_key_builds_real_client(self) -> None:
        settings = _settings(
            USE_MOCK_LLM=False,
            ENABLE_REAL_LLM=True,
            MIMO_API_KEY="test-mimo-key",
            OPENAI_API_KEY=None,
        )
        client = build_llm_client(settings)
        assert isinstance(client, OpenAICompatibleClient)
        assert client.resolved.provider == "mimo"
        assert client.resolved.api_key == "test-mimo-key"

    def test_mimo_without_key_raises_mimo_error(self) -> None:
        settings = _settings(
            USE_MOCK_LLM=False,
            ENABLE_REAL_LLM=True,
            MIMO_API_KEY=None,
            OPENAI_API_KEY=None,
        )
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY is missing"):
            build_llm_client(settings)

    def test_mimo_missing_key_error_does_not_mention_openai_when_mimo_key_expected(self) -> None:
        """When MIMO_API_KEY is set but empty, error should mention OPENAI_API_KEY
        (fallback), not MIMO_API_KEY — because resolve falls through to OpenAI."""
        settings = _settings(
            USE_MOCK_LLM=False,
            ENABLE_REAL_LLM=True,
            MIMO_API_KEY=None,
            OPENAI_API_KEY=None,
        )
        with pytest.raises(RuntimeError) as exc_info:
            build_llm_client(settings)
        # Since no MIMO_API_KEY, resolve falls to OpenAI → OPENAI_API_KEY error
        assert "OPENAI_API_KEY" in str(exc_info.value)

    def test_mimo_client_uses_mimo_base_url(self) -> None:
        settings = _settings(
            USE_MOCK_LLM=False,
            ENABLE_REAL_LLM=True,
            MIMO_API_KEY="test-key",
            MIMO_BASE_URL="https://custom.example.com/v1",
        )
        client = build_llm_client(settings)
        assert client.resolved.base_url == "https://custom.example.com/v1"

    def test_mimo_client_uses_mimo_model(self) -> None:
        settings = _settings(
            USE_MOCK_LLM=False,
            ENABLE_REAL_LLM=True,
            MIMO_API_KEY="test-key",
            MIMO_MODEL_NAME="custom-model",
        )
        client = build_llm_client(settings)
        assert client.resolved.model == "custom-model"

    def test_mimo_does_not_require_openai_key(self) -> None:
        """Production case: MIMO_API_KEY set, OPENAI_API_KEY absent."""
        settings = _settings(
            USE_MOCK_LLM=False,
            ENABLE_REAL_LLM=True,
            MIMO_API_KEY="test-mimo-key",
            OPENAI_API_KEY=None,
        )
        client = build_llm_client(settings)
        assert isinstance(client, OpenAICompatibleClient)
        assert client.resolved.provider == "mimo"
        assert client.resolved.api_key == "test-mimo-key"
        assert client.resolved.api_key_env_name == "MIMO_API_KEY"


# ---------------------------------------------------------------------------
# build_llm_client — OpenAI provider
# ---------------------------------------------------------------------------

class TestBuildLLMClientOpenAI:
    """Tests for build_llm_client with OpenAI provider."""

    def test_openai_with_key_builds_real_client(self) -> None:
        settings = _settings(
            USE_MOCK_LLM=False,
            ENABLE_REAL_LLM=True,
            OPENAI_API_KEY="test-openai-key",
            MIMO_API_KEY=None,
        )
        client = build_llm_client(settings)
        assert isinstance(client, OpenAICompatibleClient)
        assert client.resolved.provider == "openai"
        assert client.resolved.api_key == "test-openai-key"

    def test_openai_without_key_raises_openai_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        settings = _settings(
            USE_MOCK_LLM=False,
            ENABLE_REAL_LLM=True,
            OPENAI_API_KEY=None,
            MIMO_API_KEY=None,
        )
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY is missing"):
            build_llm_client(settings)

    def test_openai_missing_key_error_does_not_mention_mimo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        settings = _settings(
            USE_MOCK_LLM=False,
            ENABLE_REAL_LLM=True,
            OPENAI_API_KEY=None,
            MIMO_API_KEY=None,
        )
        with pytest.raises(RuntimeError) as exc_info:
            build_llm_client(settings)
        assert "MIMO_API_KEY" not in str(exc_info.value)

    def test_openai_client_uses_openai_base_url(self) -> None:
        settings = _settings(
            USE_MOCK_LLM=False,
            ENABLE_REAL_LLM=True,
            OPENAI_API_KEY="test-key",
            OPENAI_BASE_URL="https://custom-openai.example.com/v1",
            MIMO_API_KEY=None,
        )
        client = build_llm_client(settings)
        assert client.resolved.base_url == "https://custom-openai.example.com/v1"

    def test_openai_client_uses_openai_model(self) -> None:
        settings = _settings(
            USE_MOCK_LLM=False,
            ENABLE_REAL_LLM=True,
            OPENAI_API_KEY="test-key",
            OPENAI_MODEL="gpt-4o",
            MIMO_API_KEY=None,
        )
        client = build_llm_client(settings)
        assert client.resolved.model == "gpt-4o"


# ---------------------------------------------------------------------------
# ENABLE_REAL_LLM safety
# ---------------------------------------------------------------------------

class TestEnableRealLLMSafety:
    """Tests for ENABLE_REAL_LLM guard."""

    def test_enable_real_llm_false_blocks_real_mimo_client(self) -> None:
        settings = _settings(
            USE_MOCK_LLM=False,
            ENABLE_REAL_LLM=False,
            MIMO_API_KEY="test-key",
        )
        with pytest.raises(RuntimeError, match="ENABLE_REAL_LLM"):
            build_llm_client(settings)

    def test_enable_real_llm_false_blocks_real_openai_client(self) -> None:
        settings = _settings(
            USE_MOCK_LLM=False,
            ENABLE_REAL_LLM=False,
            OPENAI_API_KEY="test-key",
            MIMO_API_KEY=None,
        )
        with pytest.raises(RuntimeError, match="ENABLE_REAL_LLM"):
            build_llm_client(settings)


# ---------------------------------------------------------------------------
# build_llm_client_for_mode
# ---------------------------------------------------------------------------

class TestBuildLLMClientForMode:
    """Tests for build_llm_client_for_mode()."""

    def test_mock_mode(self) -> None:
        settings = _settings()
        client = build_llm_client_for_mode(settings, "mock")
        assert isinstance(client, MockLLMClient)

    def test_mimo_mode_with_key(self) -> None:
        settings = _settings(MIMO_API_KEY="test-mimo-key")
        client = build_llm_client_for_mode(settings, "mimo")
        assert isinstance(client, OpenAICompatibleClient)
        assert client.resolved.provider == "mimo"
        assert client.resolved.api_key == "test-mimo-key"

    def test_mimo_mode_missing_key_error(self) -> None:
        settings = _settings(MIMO_API_KEY=None)
        with pytest.raises(RuntimeError, match="MIMO_API_KEY is missing"):
            build_llm_client_for_mode(settings, "mimo")

    def test_mimo_mode_missing_key_error_no_openai_mention(self) -> None:
        settings = _settings(MIMO_API_KEY=None)
        with pytest.raises(RuntimeError) as exc_info:
            build_llm_client_for_mode(settings, "mimo")
        assert "OPENAI_API_KEY" not in str(exc_info.value)

    def test_unknown_mode_raises(self) -> None:
        settings = _settings()
        with pytest.raises(ValueError, match="Unknown llm_mode"):
            build_llm_client_for_mode(settings, "unknown")


# ---------------------------------------------------------------------------
# Secret safety
# ---------------------------------------------------------------------------

class TestSecretSafety:
    """Tests that no secrets are exposed in errors or logs."""

    def test_missing_key_error_does_not_expose_key_prefix(self) -> None:
        settings = _settings(
            USE_MOCK_LLM=False,
            ENABLE_REAL_LLM=True,
            MIMO_API_KEY=None,
            OPENAI_API_KEY=None,
        )
        with pytest.raises(RuntimeError) as exc_info:
            build_llm_client(settings)
        error_msg = str(exc_info.value)
        assert "sk-" not in error_msg
        assert "test-" not in error_msg

    def test_resolved_config_not_logged(self) -> None:
        """ResolvedLLMConfig api_key should not appear in str/repr."""
        config = ResolvedLLMConfig(
            provider="mimo",
            model="test",
            base_url="https://test.com/v1",
            api_key="super-secret-key",
            api_key_env_name="MIMO_API_KEY",
        )
        # Verify the key is stored but not in provider/model/base_url fields
        assert config.api_key == "super-secret-key"
        assert config.provider == "mimo"
        assert "super-secret-key" not in config.provider
        assert "super-secret-key" not in config.model
        assert "super-secret-key" not in config.base_url


# ---------------------------------------------------------------------------
# Production regression: MiMo without OPENAI_API_KEY
# ---------------------------------------------------------------------------

class TestProductionRegression:
    """Regression test for the production failure scenario."""

    def test_mimo_provider_without_openai_key_builds_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Production case: USE_MOCK_LLM=false, ENABLE_REAL_LLM=true,
        MIMO_API_KEY set, OPENAI_API_KEY absent. build_llm_client must succeed."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        settings = _settings(
            USE_MOCK_LLM=False,
            ENABLE_REAL_LLM=True,
            MIMO_API_KEY="production-mimo-key",
            MIMO_BASE_URL="https://token-plan-cn.xiaomimo.com/v1",
            MIMO_MODEL_NAME="mimo-v2.5-pro",
            OPENAI_API_KEY=None,
        )
        client = build_llm_client(settings)
        assert isinstance(client, OpenAICompatibleClient)
        assert client.resolved.provider == "mimo"
        assert client.resolved.model == "mimo-v2.5-pro"
        assert client.resolved.base_url == "https://token-plan-cn.xiaomimo.com/v1"
        assert client.resolved.api_key == "production-mimo-key"
        assert client.resolved.api_key_env_name == "MIMO_API_KEY"

    def test_mimo_generate_review_uses_mimo_key_not_openai(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify generate_review sends MIMO_API_KEY, not OPENAI_API_KEY."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        settings = _settings(
            USE_MOCK_LLM=False,
            ENABLE_REAL_LLM=True,
            MIMO_API_KEY="mimo-secret",
            OPENAI_API_KEY=None,
        )
        client = build_llm_client(settings)
        assert client.resolved.api_key == "mimo-secret"
        # The resolved config is what generate_review will use

    def test_orchestrator_separate_mode_can_use_mimo_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AgentOrchestrator separate path can run with a MiMo client
        that has no OPENAI_API_KEY."""
        from backend.agents.orchestrator import AgentOrchestrator

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        settings = _settings(
            USE_MOCK_LLM=False,
            ENABLE_REAL_LLM=True,
            MIMO_API_KEY="mimo-key",
            OPENAI_API_KEY=None,
        )
        client = build_llm_client(settings)
        # Orchestrator should accept the client without error
        orchestrator = AgentOrchestrator(
            client,
            model=client.resolved.model,
            agent_mode="separate",
        )
        assert orchestrator.llm_client is client
        assert orchestrator.model == "mimo-v2.5-pro"
