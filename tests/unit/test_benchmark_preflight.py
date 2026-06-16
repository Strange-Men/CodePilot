"""Tests for benchmark script preflight auth validation."""

from __future__ import annotations

import pytest

from scripts.benchmark_real_review import _preflight_auth_check


def test_preflight_fails_when_no_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """No API keys configured should fail."""
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    error = _preflight_auth_check()

    assert error is not None
    assert "No API key" in error


def test_preflight_fails_when_mimo_is_placeholder_template(monkeypatch: pytest.MonkeyPatch) -> None:
    """MIMO_API_KEY matching .env.example placeholder should fail."""
    monkeypatch.setenv("MIMO_API_KEY", "<your_mimo_api_key>")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    error = _preflight_auth_check()

    assert error is not None
    assert "placeholder" in error.lower()


def test_preflight_fails_when_mimo_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty MIMO_API_KEY should fail when no other key is set."""
    monkeypatch.setenv("MIMO_API_KEY", "")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    error = _preflight_auth_check()

    assert error is not None


def test_preflight_fails_when_openai_is_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    """OPENAI_API_KEY matching known placeholder should fail."""
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "placeholder")

    error = _preflight_auth_check()

    assert error is not None
    assert "placeholder" in error.lower()


def test_preflight_passes_with_valid_mimo_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-placeholder MIMO_API_KEY should pass."""
    monkeypatch.setenv("MIMO_API_KEY", "sk-real-looking-key-abc123def456")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    error = _preflight_auth_check()

    assert error is None


def test_preflight_passes_with_valid_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-placeholder OPENAI_API_KEY should pass."""
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-looking-key-abc123def456")

    error = _preflight_auth_check()

    assert error is None


def test_preflight_passes_with_both_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both keys present and valid should pass."""
    monkeypatch.setenv("MIMO_API_KEY", "real-mimo-key-123")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-openai-key-456")

    error = _preflight_auth_check()

    assert error is None


def test_preflight_fails_when_mimo_is_changeme(monkeypatch: pytest.MonkeyPatch) -> None:
    """Common placeholder 'changeme' should fail."""
    monkeypatch.setenv("MIMO_API_KEY", "changeme")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    error = _preflight_auth_check()

    assert error is not None


def test_preflight_does_not_expose_key_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Error message must not contain the key value."""
    monkeypatch.setenv("MIMO_API_KEY", "<your_mimo_api_key>")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    error = _preflight_auth_check()

    assert error is not None
    assert "<your_mimo_api_key>" not in error


def test_preflight_does_not_expose_key_length(monkeypatch: pytest.MonkeyPatch) -> None:
    """Error message must not mention key length."""
    monkeypatch.setenv("MIMO_API_KEY", "<your_mimo_api_key>")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    error = _preflight_auth_check()

    assert error is not None
    assert "28" not in error
    assert "length" not in error.lower()
