from backend.models.context import CodeFileSummary
from backend.services.prioritization import (
    is_test_path,
    ordered_by_importance,
    ordered_for_recommendations,
    paths_for_roles,
)


def summary(path: str, score: float, role: str = "Supporting Module") -> CodeFileSummary:
    return CodeFileSummary(
        path=path,
        purpose="Test.",
        summary="Test.",
        importance_score=score,
        file_role=role,
    )


def test_importance_order_is_score_descending_then_path() -> None:
    summaries = [
        summary("z.py", 10),
        summary("b.py", 20),
        summary("a.py", 20),
    ]

    assert [item.path for item in ordered_by_importance(summaries)] == ["a.py", "b.py", "z.py"]


def test_paths_for_roles_uses_shared_importance_order() -> None:
    summaries = [
        summary("support.py", 30),
        summary("core-low.py", 10, "Core Module"),
        summary("core-high.py", 50, "Core Module"),
    ]

    assert paths_for_roles(summaries, {"Core Module"}) == ["core-high.py", "core-low.py"]


def test_recommendation_order_prioritizes_production_over_tests_and_docs() -> None:
    summaries = [
        summary("tests/test_core.py", 100),
        summary("docs/conf.py", 90),
        summary("src/core.py", 20),
    ]

    assert [item.path for item in ordered_for_recommendations(summaries)] == [
        "src/core.py",
        "tests/test_core.py",
        "docs/conf.py",
    ]
    assert is_test_path("frontend/__tests__/app.test.tsx")
