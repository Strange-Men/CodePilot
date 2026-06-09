"""Shared constants and helpers for report composition and markdown adaptation."""

from __future__ import annotations

DEFAULT_SECTION_CONTENT = "No critical findings detected from the available repository summaries."


def format_cycle_group(cycle: list[str], limit: int = 6) -> str:
    """Format a dependency cycle into a bounded, human-readable bullet.

    Shows at most *limit* module paths and appends "+N more" for overflow.
    """
    visible = cycle[:limit]
    suffix = f", +{len(cycle) - limit} more" if len(cycle) > limit else ""
    paths = ", ".join(f"`{path}`" for path in visible)
    return f"- Cycle group ({len(cycle)} modules): {paths}{suffix}"
