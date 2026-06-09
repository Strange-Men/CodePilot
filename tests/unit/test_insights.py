from __future__ import annotations

from backend.models.review import CodeFileSummary, RepositoryContext
from backend.services.insights import RepositoryInsightEngine


def build_context(*summaries: CodeFileSummary, language: str = "Python") -> RepositoryContext:
    return RepositoryContext(
        repo_url="https://github.com/example/project",
        total_python_files=len(summaries),
        analyzed_files=len(summaries),
        skipped_files=0,
        file_summaries=list(summaries),
        repository_summary="Repository summary.",
        language=language,
        total_lines=sum(summary.line_count for summary in summaries),
        avg_complexity=(
            sum(summary.complexity_estimate for summary in summaries) / len(summaries)
            if summaries
            else 0.0
        ),
        entry_points=[
            summary.path for summary in summaries if summary.file_role == "Entry Point"
        ],
        core_modules=[
            summary.path for summary in summaries if summary.file_role == "Core Module"
        ],
        supporting_modules=[
            summary.path for summary in summaries if summary.file_role == "Supporting Module"
        ],
        hub_files=[summary.path for summary in summaries if summary.is_hub],
    )


def summary(path: str, **overrides) -> CodeFileSummary:
    values = {
        "path": path,
        "purpose": "Implements repository behavior.",
        "summary": "Repository behavior.",
        "line_count": 50,
        "function_count": 2,
        "complexity_estimate": 3,
        "importance_score": 30.0,
        "file_role": "Supporting Module",
    }
    values.update(overrides)
    return CodeFileSummary(**values)


def test_architecture_overview_classifies_mixed_language_repository() -> None:
    context = build_context(
        summary("backend/app.py", file_role="Entry Point"),
        summary("frontend/app.ts", file_role="Entry Point"),
        language="Python + TypeScript",
    )

    insights = RepositoryInsightEngine().generate(context)

    assert insights.repository_type == "Full-stack mixed-language application"
    assert insights.major_components == ["backend (1 files)", "frontend (1 files)"]
    assert any(item.title == "Runtime entry points" for item in insights.architecture_overview)


def test_risk_hotspots_explain_high_fan_in_impact() -> None:
    context = build_context(
        summary("services/core.py", fan_in=4, is_hub=True, file_role="Core Module"),
    )

    insights = RepositoryInsightEngine().generate(context)

    hotspot = next(item for item in insights.risk_hotspots if "dependency pressure" in item.title)
    assert hotspot.files == ["services/core.py"]
    assert "changes here can spread widely" in hotspot.explanation


def test_risk_hotspots_detect_responsibility_concentration() -> None:
    context = build_context(
        summary(
            "services/large.py",
            line_count=500,
            function_count=18,
            complexity_estimate=30,
            importance_score=80,
        ),
        summary("services/small.py"),
    )

    insights = RepositoryInsightEngine().generate(context)

    hotspot = next(item for item in insights.risk_hotspots if "Responsibility concentration" in item.title)
    assert "multiple reasons to change" in hotspot.explanation


def test_risk_hotspots_explain_dependency_cycles() -> None:
    context = build_context(summary("a.py"), summary("b.py"))
    context.circular_dependencies = [["a.py", "b.py"]]

    insights = RepositoryInsightEngine().generate(context)

    cycle = next(item for item in insights.risk_hotspots if item.title == "Circular dependency group (2 modules)")
    assert cycle.files == ["a.py", "b.py"]
    assert "initialization, testing, and ownership" in cycle.explanation


def test_onboarding_guide_prioritizes_entry_point_then_core() -> None:
    context = build_context(
        summary("helper.py", importance_score=90),
        summary("services/core.py", file_role="Core Module", importance_score=60),
        summary("app.py", file_role="Entry Point", importance_score=40),
    )

    insights = RepositoryInsightEngine().generate(context)

    assert insights.onboarding_guide[0].files == ["app.py"]
    assert insights.onboarding_guide[1].files == ["services/core.py"]
    assert "application boots" in insights.onboarding_guide[0].explanation


def test_refactoring_candidates_cover_bottlenecks_and_cycles() -> None:
    context = build_context(
        summary("services/core.py", fan_in=3, is_hub=True, file_role="Core Module"),
        summary("adapter.py"),
    )
    context.circular_dependencies = [["services/core.py", "adapter.py"]]

    insights = RepositoryInsightEngine().generate(context)

    titles = {item.title for item in insights.refactoring_candidates}
    assert "Stabilize the boundary around services/core.py" in titles
    assert "Break a circular dependency" in titles


def test_empty_repository_receives_safe_actionable_defaults() -> None:
    insights = RepositoryInsightEngine().generate(build_context())

    assert insights.repository_type == "Python library"
    assert insights.onboarding_guide[0].title == "No source reading order available"
    assert insights.refactoring_candidates[0].title == "Preserve current module boundaries"


def test_no_hotspots_explains_scope_of_structural_signal() -> None:
    insights = RepositoryInsightEngine().generate(build_context(summary("helper.py")))

    assert insights.risk_hotspots[0].title == "No concentrated structural hotspot detected"
    assert "does not replace behavioral or security review" in insights.risk_hotspots[0].explanation


def test_flask_like_framework_is_not_classified_as_cli() -> None:
    context = build_context(
        summary("src/flask/app.py", classes=["Flask"], functions=["request"]),
        summary("src/flask/cli.py", functions=["main"]),
        summary("src/flask/blueprints.py", classes=["Blueprint", "Response"]),
    )

    insights = RepositoryInsightEngine().generate(context)

    assert insights.repository_type == "Python web framework"


def test_generic_request_response_library_is_not_classified_as_web_framework() -> None:
    """Generic 'Request' and 'Response' class names alone must not trigger web framework classification."""
    context = build_context(
        summary("src/client/request.py", classes=["Request"], functions=["send"]),
        summary("src/client/response.py", classes=["Response"], functions=["parse"]),
        summary("src/client/session.py", classes=["Session"], functions=["open", "close"]),
    )

    insights = RepositoryInsightEngine().generate(context)

    assert "web framework" not in insights.repository_type.lower()


def test_test_hotspots_do_not_displace_production_hotspots_or_recommendations() -> None:
    context = build_context(
        summary(
            "tests/test_everything.py",
            line_count=2000,
            function_count=80,
            complexity_estimate=100,
            importance_score=100,
        ),
        summary(
            "src/service.py",
            line_count=500,
            function_count=18,
            complexity_estimate=30,
            importance_score=30,
        ),
    )

    insights = RepositoryInsightEngine().generate(context)

    assert insights.risk_hotspots[0].files == ["src/service.py"]
    assert insights.test_hotspots[0].files == ["tests/test_everything.py"]
    assert all("tests/" not in path for item in insights.refactoring_candidates for path in item.files)
