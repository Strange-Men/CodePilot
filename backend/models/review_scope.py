from __future__ import annotations

from dataclasses import dataclass, field

from backend.models.context import ReviewContext


@dataclass(frozen=True)
class ReviewScope:
    """Optional review focus used by developer workflow integrations."""

    changed_paths: frozenset[str] = field(default_factory=frozenset)
    source: str = "full"
    include_dependency_neighbors: bool = True

    @classmethod
    def for_changed_paths(
        cls,
        paths: set[str] | list[str] | tuple[str, ...],
        *,
        source: str = "diff",
        include_dependency_neighbors: bool = True,
    ) -> ReviewScope:
        return cls(
            changed_paths=frozenset(_normalize_path(path) for path in paths if _normalize_path(path)),
            source=source,
            include_dependency_neighbors=include_dependency_neighbors,
        )

    @property
    def is_diff_mode(self) -> bool:
        return bool(self.changed_paths)

    def candidate_paths(self, context: ReviewContext) -> set[str] | None:
        if not self.changed_paths:
            return None

        known_paths = {summary.path for summary in context.file_summaries}
        candidates = set(self.changed_paths).intersection(known_paths)
        if not self.include_dependency_neighbors:
            return candidates

        for source, targets in context.dependency_edges.items():
            normalized_targets = {_normalize_path(target) for target in targets}
            if source in self.changed_paths:
                candidates.update(path for path in normalized_targets if path in known_paths)
            if self.changed_paths.intersection(normalized_targets):
                candidates.add(source)
        return candidates

    def metadata(self, context: ReviewContext) -> dict[str, object]:
        candidates = self.candidate_paths(context)
        return {
            "review_scope": self.source,
            "changed_files": sorted(self.changed_paths),
            "candidate_files": sorted(candidates or []),
            "include_dependency_neighbors": self.include_dependency_neighbors,
        }


def _normalize_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    for prefix in ("a/", "b/"):
        if normalized.startswith(prefix):
            normalized = normalized.removeprefix(prefix)
    return normalized.lstrip("/")
