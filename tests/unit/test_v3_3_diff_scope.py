from __future__ import annotations

from pathlib import Path

from backend.llm.client import MockLLMClient
from backend.models.context import EvidenceRecord
from backend.models.review_scope import ReviewScope
from backend.reviewers.report_generator import ReportGenerator
from backend.services.evidence import EvidenceRetriever, RetrievalPolicy


def test_review_scope_includes_changed_files_and_dependency_neighbors(sample_context) -> None:
    context = sample_context.to_review_context()
    scope = ReviewScope.for_changed_paths({"app.py"})

    assert scope.candidate_paths(context) == {"app.py", "services/review.py"}


def test_review_scope_can_disable_dependency_neighbors(sample_context) -> None:
    context = sample_context.to_review_context()
    scope = ReviewScope.for_changed_paths({"app.py"}, include_dependency_neighbors=False)

    assert scope.candidate_paths(context) == {"app.py"}


def test_evidence_retrieval_respects_diff_candidate_paths(sample_context) -> None:
    context = sample_context.to_review_context()
    context.evidence = [
        EvidenceRecord(
            evidence_id="ev_app",
            file_path="app.py",
            start_line=1,
            end_line=2,
            snippet="def create_app():\n    return review()",
            symbols=["create_app"],
        ),
        EvidenceRecord(
            evidence_id="ev_other",
            file_path="other.py",
            start_line=1,
            end_line=2,
            snippet="def unrelated():\n    return 1",
            symbols=["unrelated"],
        ),
    ]

    result = EvidenceRetriever(context).retrieve_with_policy(
        RetrievalPolicy(query="create app", limit=5),
        candidate_paths={"app.py"},
    )

    assert [record.file_path for record in result.records] == ["app.py"]


def test_report_generator_focuses_v3_findings_and_documents_diff_scope(
    sample_context,
    tmp_path: Path,
) -> None:
    context = sample_context.to_review_context()
    context.evidence = [
        EvidenceRecord(
            evidence_id="ev_aaaaaaaaaaaaaaaaaaaa",
            file_path="app.py",
            start_line=1,
            end_line=2,
            snippet="def create_app():\n    return review()",
            symbols=["create_app"],
        ),
        EvidenceRecord(
            evidence_id="ev_bbbbbbbbbbbbbbbbbbbb",
            file_path="services/review.py",
            start_line=1,
            end_line=2,
            snippet="def review():\n    return True",
            symbols=["review"],
        ),
    ]
    generator = ReportGenerator(MockLLMClient(), tmp_path, 8000)
    generator.configure_engine("v3_multi_agent")
    generator.configure_review_scope(
        ReviewScope.for_changed_paths({"app.py"}, include_dependency_neighbors=False)
    )

    result = generator.generate("diff-task", context)

    assert "# Diff Review Scope" in result.report
    assert "## Changed Files\n- `app.py`" in result.report
    assert result.structured_draft is not None
    assert result.structured_draft.findings
    assert all(finding.files == ["app.py"] for finding in result.structured_draft.findings)
