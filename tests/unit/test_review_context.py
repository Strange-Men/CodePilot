from backend.models.context import (
    DependencyStructure,
    FileAnalysisBundle,
    InsightReport,
    RepoMetadata,
    RepositoryContext,
    RepositoryInsight,
    ReviewContext,
    as_review_context,
)
from backend.models.review import CodeFileSummary


def build_review_context() -> ReviewContext:
    summary = CodeFileSummary(
        path="app.py",
        purpose="Starts the application.",
        summary="Application entry point.",
        line_count=20,
        complexity_estimate=3,
        file_role="Entry Point",
    )
    return ReviewContext(
        metadata=RepoMetadata(
            repo_url="https://github.com/example/project",
            total_source_files=1,
            analyzed_files=1,
            repository_summary="Python application.",
            total_lines=20,
            avg_complexity=3.0,
        ),
        files=FileAnalysisBundle(summaries=[summary], entry_points=["app.py"]),
        dependencies=DependencyStructure(edges={"app.py": []}, orphan_files=["app.py"]),
        insights=InsightReport(
            repository_type="Python application",
            architecture_overview=[
                RepositoryInsight(title="Runtime entry points", explanation="Start here.", files=["app.py"])
            ],
        ),
    )


def test_review_context_exposes_legacy_read_properties() -> None:
    context = build_review_context()

    assert context.total_python_files == 1
    assert context.file_summaries[0].path == "app.py"
    assert context.entry_points == ["app.py"]
    assert context.dependency_edges == {"app.py": []}


def test_repository_context_round_trip_preserves_flat_contract() -> None:
    review_context = build_review_context()

    legacy = RepositoryContext.from_review_context(review_context)
    restored = legacy.to_review_context()

    assert RepositoryContext.from_review_context(restored).model_dump() == legacy.model_dump()
    assert legacy.total_python_files == 1
    assert legacy.insights.repository_type == "Python application"


def test_as_review_context_accepts_both_context_generations() -> None:
    review_context = build_review_context()
    legacy_context = RepositoryContext.from_review_context(review_context)

    assert as_review_context(review_context) is review_context
    assert as_review_context(legacy_context) == review_context


def test_focused_context_models_have_safe_defaults() -> None:
    context = ReviewContext(
        metadata=RepoMetadata(repo_url="https://github.com/example/empty"),
    )

    assert context.total_python_files == 0
    assert context.file_summaries == []
    assert context.dependency_edges == {}
    assert context.insights.repository_type == "Software repository"
