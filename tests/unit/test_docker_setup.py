from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_docker_local_runtime_files_exist() -> None:
    for path in (
        "Dockerfile.backend",
        "Dockerfile.frontend",
        "docker-compose.yml",
        ".dockerignore",
        "docs/DOCKER.md",
    ):
        assert (ROOT / path).exists(), path


def test_docker_compose_defaults_to_mock_and_persists_sqlite() -> None:
    compose = _read("docker-compose.yml")

    assert "USE_MOCK_LLM: ${USE_MOCK_LLM:-true}" in compose
    assert "ENABLE_REAL_LLM: ${ENABLE_REAL_LLM:-false}" in compose
    assert "DATABASE_PATH: /app/backend/data/codepilot.db" in compose
    assert "backend-data:/app/backend/data" in compose
    assert "backend-workspace:/app/backend/workspace" in compose
    assert "reports:/app/reports" in compose
    assert "NEXT_PUBLIC_API_BASE: ${NEXT_PUBLIC_API_BASE:-http://localhost:8000}" in compose


def test_dockerignore_excludes_sensitive_and_heavy_paths() -> None:
    dockerignore = set(_read(".dockerignore").splitlines())

    for pattern in (
        ".env",
        ".env.*",
        ".git",
        ".claude",
        "backend/data",
        "backend/workspace",
        "frontend/node_modules",
        "**/node_modules",
    ):
        assert pattern in dockerignore
    assert "!.env.example" in dockerignore


def test_docker_docs_and_config_do_not_embed_real_keys() -> None:
    combined = "\n".join(
        _read(path)
        for path in (
            "Dockerfile.backend",
            "Dockerfile.frontend",
            "docker-compose.yml",
            ".dockerignore",
            ".env.example",
            "docs/DOCKER.md",
        )
    )

    suspicious_secret = re.compile(
        r"\b(?:sk|tp)-[A-Za-z0-9_-]{20,}\b|"
        r"(?i:(?:api[_-]?key|token|secret)[ \t]*[:=][ \t]*['\"]?[A-Za-z0-9_-]{16,})"
    )
    assert suspicious_secret.search(combined) is None
