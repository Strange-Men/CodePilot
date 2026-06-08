from __future__ import annotations

from pathlib import Path

import pytest

from backend.models.context import EvidenceRecord
from backend.parsers.python_parser import PythonParser
from backend.services.evidence import EvidenceRetriever, EvidenceStore, stable_evidence_id
from backend.services.indexer import RepositoryIndexer
from backend.services.sandbox import SandboxFilter, redact_secrets


def test_sandbox_manifest_filters_size_symlinks_and_redacts(temp_repo: Path) -> None:
    source = temp_repo / "app.py"
    source.write_text("OPENAI_API_KEY='sk-secretsecretsecret'\n\ndef run():\n    return 1\n", encoding="utf-8")
    large = temp_repo / "large.py"
    large.write_text("x = '" + ("a" * 500) + "'\n", encoding="utf-8")
    unsupported = temp_repo / "README.md"
    unsupported.write_text("OPENAI_API_KEY=sk-should-not-enter\n", encoding="utf-8")
    link = temp_repo / "linked.py"
    try:
        link.symlink_to(source)
    except OSError:
        link = None

    manifest = SandboxFilter().build_manifest(temp_repo, max_files=10, max_file_size_bytes=100)

    assert [file.path for file in manifest.files] == ["app.py"]
    assert manifest.total_supported_files == 2 + (1 if link is not None else 0)
    assert manifest.skipped_files >= 1
    assert "sk-secretsecretsecret" not in manifest.files[0].content
    assert "[REDACTED]" in manifest.files[0].content


def test_redact_secrets_handles_common_token_shapes() -> None:
    text = "api_key=abcdef123456\nAuthorization: Bearer ghp_123456789012345678901234\n"

    redacted = redact_secrets(text)

    assert "abcdef123456" not in redacted
    assert "ghp_123456789012345678901234" not in redacted
    assert redacted.count("[REDACTED]") == 2


def test_python_deep_context_extracts_symbols_calls_and_routes(temp_repo: Path) -> None:
    source = temp_repo / "api.py"
    source.write_text(
        "from fastapi import APIRouter\n"
        "router = APIRouter()\n\n"
        "class Base: pass\n\n"
        "class Service(Base):\n"
        "    \"\"\"Service docs.\"\"\"\n"
        "    def work(self):\n"
        "        return helper()\n\n"
        "@router.get('/health')\n"
        "def health(name: str) -> dict:\n"
        "    \"\"\"Health route.\"\"\"\n"
        "    return {'ok': helper()}\n\n"
        "def helper():\n"
        "    return True\n",
        encoding="utf-8",
    )

    parsed = PythonParser().parse_file(temp_repo, source)

    health = next(function for function in parsed.function_details if function.name == "health")
    service = next(class_detail for class_detail in parsed.class_details if class_detail.name == "Service")
    assert health.params == ["name"]
    assert health.return_type == "dict"
    assert "helper" in health.calls
    assert service.bases == ["Base"]
    assert parsed.route_patterns[0].method == "GET"
    assert parsed.route_patterns[0].path == "/health"


def test_indexer_builds_deep_context_and_stable_evidence(temp_repo: Path) -> None:
    source = temp_repo / "service.py"
    source.write_text("def review(items):\n    return [item for item in items]\n", encoding="utf-8")
    manifest = SandboxFilter().build_manifest(temp_repo, max_files=10, max_file_size_bytes=1000)

    context = RepositoryIndexer(
        PythonParser(),
        max_files=10,
        max_file_size_bytes=1000,
        manifest=manifest,
    ).build_review_context(temp_repo, "https://github.com/example/project")

    assert "review" in context.deep_context.symbol_index
    assert context.evidence
    assert context.file_summaries[0].evidence_ids == [context.evidence[0].evidence_id]
    rebuilt = RepositoryIndexer(
        PythonParser(),
        max_files=10,
        max_file_size_bytes=1000,
        manifest=SandboxFilter().build_manifest(temp_repo, max_files=10, max_file_size_bytes=1000),
    ).build_review_context(temp_repo, "https://github.com/example/project")
    assert rebuilt.evidence[0].evidence_id == context.evidence[0].evidence_id


def test_evidence_store_and_retriever_resolve_grounded_records(sample_context) -> None:
    context = sample_context.to_review_context()
    evidence_id = stable_evidence_id("services/review.py", 1, 2, "def review():\n    pass")
    context.evidence = [
        EvidenceRecord(
            evidence_id=evidence_id,
            file_path="services/review.py",
            start_line=1,
            end_line=2,
            snippet="def review():\n    pass",
            kind="symbol",
            symbols=["review"],
        )
    ]

    store = EvidenceStore.from_context(context)
    results = EvidenceRetriever(context).retrieve("review service", limit=1)

    assert store.resolve(evidence_id).file_path == "services/review.py"
    assert results[0].evidence_id == evidence_id


def test_sandbox_rejects_paths_outside_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("x = 1\n", encoding="utf-8")
    link = repo / "outside.py"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable on this filesystem")

    manifest = SandboxFilter().build_manifest(repo, max_files=10, max_file_size_bytes=1000)

    assert manifest.files == ()
    assert manifest.skipped_files == 1
