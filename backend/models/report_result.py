from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from backend.models.review_state import AgentExecutionState, ReviewState
from backend.models.structured_review import StructuredReviewDraft


@dataclass(frozen=True)
class ReportResult:
    """Explicit return type for ReportGenerator.generate().

    Carries the report markdown, export path, and optional V3 review artifacts.
    Replaces the previous tuple[str, Path] return with getattr()-based side-channel
    attributes for structured draft, agent states, and review state.
    """

    report: str
    export_path: Path
    structured_draft: StructuredReviewDraft | None = None
    agent_states: list[AgentExecutionState] = field(default_factory=list)
    review_state: ReviewState | None = None
