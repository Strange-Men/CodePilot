from __future__ import annotations

from collections.abc import Iterable

from backend.models.context import CodeFileSummary, RepositoryContext, ReviewContext, as_review_context


def importance_sort_key(summary: CodeFileSummary) -> tuple[float, str]:
    return -summary.importance_score, summary.path


def ordered_by_importance(summaries: Iterable[CodeFileSummary]) -> list[CodeFileSummary]:
    return sorted(summaries, key=importance_sort_key)


def top_important_files(
    context: ReviewContext | RepositoryContext,
    *,
    limit: int,
) -> list[CodeFileSummary]:
    return ordered_by_importance(as_review_context(context).file_summaries)[:limit]


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
