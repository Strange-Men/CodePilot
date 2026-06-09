from __future__ import annotations

from collections.abc import Iterable

from backend.models.context import CodeFileSummary, RepositoryContext, ReviewContext, as_review_context


def importance_sort_key(summary: CodeFileSummary) -> tuple[float, str]:
    return -summary.importance_score, summary.path


def is_test_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    parts = normalized.split("/")
    filename = parts[-1]
    return (
        any(part in {"test", "tests", "__tests__"} for part in parts[:-1])
        or filename.startswith("test_")
        or filename.endswith(("_test.py", ".test.js", ".test.jsx", ".test.ts", ".test.tsx"))
        or filename.endswith(("_spec.py", ".spec.js", ".spec.jsx", ".spec.ts", ".spec.tsx"))
    )


def is_docs_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    parts = normalized.split("/")
    return any(part in {"doc", "docs", "documentation"} for part in parts[:-1])


def recommendation_sort_key(summary: CodeFileSummary) -> tuple[int, float, str]:
    if is_test_path(summary.path):
        path_rank = 1
    elif is_docs_path(summary.path):
        path_rank = 2
    else:
        path_rank = 0
    return path_rank, -summary.importance_score, summary.path


def ordered_by_importance(summaries: Iterable[CodeFileSummary]) -> list[CodeFileSummary]:
    return sorted(summaries, key=importance_sort_key)


def ordered_for_recommendations(summaries: Iterable[CodeFileSummary]) -> list[CodeFileSummary]:
    return sorted(summaries, key=recommendation_sort_key)


def top_important_files(
    context: ReviewContext | RepositoryContext,
    *,
    limit: int,
) -> list[CodeFileSummary]:
    return ordered_for_recommendations(as_review_context(context).file_summaries)[:limit]


def paths_for_roles(
    summaries: Iterable[CodeFileSummary],
    roles: set[str],
) -> list[str]:
    return [
        summary.path
        for summary in ordered_by_importance(summaries)
        if summary.file_role in roles
    ]


def important_dependency_relationships(
    context: ReviewContext | RepositoryContext,
    *,
    limit: int,
) -> list[tuple[str, str]]:
    review_context = as_review_context(context)
    importance_scores = {
        summary.path: summary.importance_score
        for summary in review_context.file_summaries
    }
    relationships = [
        (source, target)
        for source, targets in review_context.dependency_edges.items()
        for target in targets
    ]
    return sorted(
        relationships,
        key=lambda edge: (
            -importance_scores.get(edge[0], 0.0),
            -importance_scores.get(edge[1], 0.0),
            edge,
        ),
    )[:limit]
