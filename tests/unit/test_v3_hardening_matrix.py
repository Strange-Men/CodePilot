from __future__ import annotations

from pathlib import Path

import pytest

from backend.agents.orchestrator import AgentOrchestrator
from backend.core.config import Settings
from backend.llm.client import build_llm_client
from backend.llm.structured import StructuredLLMClient
from backend.models.context import EvidenceRecord
from backend.models.structured_review import RawLLMFinding, ReviewFinding
from backend.services.evidence import EvidenceStore, stable_evidence_id
from backend.services.sandbox import SandboxFilter, redact_secrets


@pytest.mark.parametrize(
    "source,secret",
    [
        ("api_key=abcdef123456", "abcdef123456"),
        ("API_KEY='abcdef123456'", "abcdef123456"),
        ("access_token=tokentoken", "tokentoken"),
        ("auth-token: tokentoken", "tokentoken"),
        ("client_secret=secretsecret", "secretsecret"),
        ("password=hunter22", "hunter22"),
        ("secret='supersecret'", "supersecret"),
        ("Authorization: Bearer tokenvalue", "tokenvalue"),
        ("token = 'ghp_12345678901234567890'", "ghp_12345678901234567890"),
        ("OPENAI_API_KEY=sk-1234567890123456", "sk-1234567890123456"),
        ("-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----", "abc"),
        ("no_secret = 'safe'", "should-not-exist"),
    ],
)
def test_secret_redaction_matrix(source: str, secret: str) -> None:
    redacted = redact_secrets(source)

    assert secret not in redacted


@pytest.mark.parametrize(
    "filename,selected",
    [
        ("app.py", True),
        ("index.js", True),
        ("component.jsx", True),
        ("service.ts", True),
        ("view.tsx", True),
        ("README.md", False),
        ("data.json", False),
        ("style.css", False),
        ("script.sh", False),
        ("Dockerfile", False),
    ],
)
def test_sandbox_extension_allowlist_matrix(temp_repo: Path, filename: str, selected: bool) -> None:
    path = temp_repo / filename
    path.write_text("x = 1\n", encoding="utf-8")

    manifest = SandboxFilter().build_manifest(temp_repo, max_files=10, max_file_size_bytes=1000)

    assert (filename in [file.path for file in manifest.files]) is selected


@pytest.mark.parametrize("line_count", [1, 40, 5000])
def test_sandbox_accepts_files_at_line_limit(temp_repo: Path, line_count: int) -> None:
    (temp_repo / "app.py").write_text("x = 1\n" * line_count, encoding="utf-8")

    manifest = SandboxFilter().build_manifest(temp_repo, max_files=10, max_file_size_bytes=100000)

    assert len(manifest.files) == 1


@pytest.mark.parametrize("line_count", [5001, 6000])
def test_sandbox_rejects_files_over_line_limit(temp_repo: Path, line_count: int) -> None:
    (temp_repo / "app.py").write_text("x = 1\n" * line_count, encoding="utf-8")

    manifest = SandboxFilter().build_manifest(temp_repo, max_files=10, max_file_size_bytes=100000)

    assert manifest.files == ()


@pytest.mark.parametrize(
    "left,right,should_match",
    [
        (("app.py", 1, 2, "def run():\n    pass"), ("app.py", 1, 2, "def run():\n    pass"), True),
        (("app.py", 1, 2, "def run():\n    pass"), ("app.py", 2, 3, "def run():\n    pass"), False),
        (("app.py", 1, 2, "def run():\n    pass"), ("other.py", 1, 2, "def run():\n    pass"), False),
        (("app.py", 1, 2, "def run():\n    pass"), ("app.py", 1, 2, "def other():\n    pass"), False),
        (("a\\b.py", 1, 1, "x = 1"), ("a/b.py", 1, 1, "x = 1"), True),
    ],
)
def test_stable_evidence_id_matrix(left, right, should_match: bool) -> None:
    assert (stable_evidence_id(*left) == stable_evidence_id(*right)) is should_match


@pytest.mark.parametrize(
    "finding,valid_ids,expected",
    [
        (RawLLMFinding(title="A", description="B", category="architecture", evidence_ids=["ev_a"]), {"ev_a"}, 1),
        (RawLLMFinding(title="A", description="B", category="architecture", evidence_ids=["ev_a"]), {"ev_b"}, 0),
        (RawLLMFinding(title="A", description="B", category="architecture", evidence_ids=[]), {"ev_a"}, 0),
    ],
)
def test_structured_client_filters_allowed_evidence_matrix(finding, valid_ids, expected) -> None:
    assert len(StructuredLLMClient._filter_allowed([finding], valid_ids)) == expected


@pytest.mark.parametrize("section", ["Architecture Summary", "Code Smells", "Maintainability Issues"])
def test_evidence_store_resolves_known_ids_across_sections(section: str) -> None:
    record = EvidenceRecord(
        evidence_id="ev_known",
        file_path="app.py",
        start_line=1,
        end_line=1,
        snippet="x = 1",
    )
    store = EvidenceStore([record])

    assert store.resolve("ev_known").file_path == "app.py"
    assert ReviewFinding(section=section, description="ok", evidence_ids=["ev_known"]).section == section


@pytest.mark.parametrize("missing_id", ["ev_missing", "ev_other", "not-an-evidence-id"])
def test_evidence_store_rejects_unknown_ids(missing_id: str) -> None:
    store = EvidenceStore(
        [
            EvidenceRecord(
                evidence_id="ev_known",
                file_path="app.py",
                start_line=1,
                end_line=1,
                snippet="x = 1",
            )
        ]
    )

    with pytest.raises(KeyError):
        store.resolve(missing_id)


@pytest.mark.parametrize(
    "use_mock,enable_real,should_raise",
    [(True, False, False), (False, False, True), (False, True, False)],
)
def test_real_llm_feature_flag_matrix(use_mock: bool, enable_real: bool, should_raise: bool) -> None:
    settings = Settings(USE_MOCK_LLM=use_mock, ENABLE_REAL_LLM=enable_real, OPENAI_API_KEY="test")

    if should_raise:
        with pytest.raises(RuntimeError):
            build_llm_client(settings)
    else:
        assert build_llm_client(settings) is not None


@pytest.mark.parametrize(
    "findings,expected_count",
    [
        ([], 0),
        ([ReviewFinding(section="Code Smells", description="a", title="A", evidence_ids=["ev_a"])], 1),
        (
            [
                ReviewFinding(section="Code Smells", description="a", title="A", evidence_ids=["ev_a"]),
                ReviewFinding(section="Code Smells", description="b", title="A", evidence_ids=["ev_b"]),
            ],
            2,
        ),
        (
            [
                ReviewFinding(section="Code Smells", description="a", title="A", evidence_ids=["ev_a"]),
                ReviewFinding(section="Code Smells", description="a", title="A", evidence_ids=["ev_a"]),
            ],
            1,
        ),
    ],
)
def test_deduplication_matrix(findings: list[ReviewFinding], expected_count: int) -> None:
    assert len(AgentOrchestrator._deduplicate(findings)) == expected_count
