"""Evidence display mapping for user-friendly Markdown reports.

Maps raw internal evidence IDs (ev_*) to short user-facing display
references (E1, E2, E3, ...) in first-appearance order within a report.

The raw ev_* IDs remain in the DB and validation logic. Only the
exported Markdown and UI-facing rendering use the short refs.
"""

from __future__ import annotations

import re

from backend.models.context import EvidenceRecord
from backend.models.structured_review import ReviewFinding

# Pattern matching raw evidence IDs
_RAW_EV_PATTERN = re.compile(r"\bev_[0-9a-f]{20}\b")

# Maximum evidence appendix entries
MAX_APPENDIX_ENTRIES = 30

# Maximum snippet lines and characters per entry
MAX_SNIPPET_LINES = 20
MAX_SNIPPET_CHARS = 1600


class EvidenceDisplayMap:
    """Deterministic mapping from raw ev_* IDs to short display refs.

    Usage::

        display_map = EvidenceDisplayMap.from_findings(findings)
        # or
        display_map = EvidenceDisplayMap.from_evidence_ids(["ev_abc...", "ev_def..."])

        display_map.ref("ev_abc...")  # -> "E1"
        display_map.ref("ev_def...")  # -> "E2"
        display_map.ref("ev_unknown") # -> "ev_unknown" (passthrough)
    """

    def __init__(self, ordered_ids: list[str]) -> None:
        self._raw_to_display: dict[str, str] = {}
        for index, raw_id in enumerate(ordered_ids, start=1):
            if raw_id not in self._raw_to_display:
                self._raw_to_display[raw_id] = f"E{index}"

    @classmethod
    def from_findings(cls, findings: list[ReviewFinding]) -> EvidenceDisplayMap:
        """Build mapping from findings in first-appearance order."""
        ordered: list[str] = []
        seen: set[str] = set()
        for finding in findings:
            for eid in finding.evidence_ids:
                if eid not in seen:
                    seen.add(eid)
                    ordered.append(eid)
        return cls(ordered)

    @classmethod
    def from_evidence_ids(cls, evidence_ids: list[str]) -> EvidenceDisplayMap:
        """Build mapping from a flat list of evidence IDs."""
        ordered: list[str] = []
        seen: set[str] = set()
        for eid in evidence_ids:
            if eid not in seen:
                seen.add(eid)
                ordered.append(eid)
        return cls(ordered)

    def ref(self, raw_id: str) -> str:
        """Return the short display ref for a raw evidence ID.

        If the raw ID is not in the mapping, returns it unchanged
        (graceful passthrough for backward compatibility).
        """
        return self._raw_to_display.get(raw_id, raw_id)

    def ref_bracket(self, raw_id: str) -> str:
        """Return the bracketed display ref: [E1]."""
        return f"[{self.ref(raw_id)}]"

    def replace_in_text(self, text: str) -> str:
        """Replace all raw ev_* IDs in text with [E1]/[E2] refs."""
        def _replace(match: re.Match[str]) -> str:
            return self.ref_bracket(match.group(0))
        return _RAW_EV_PATTERN.sub(_replace, text)

    @property
    def all_mapped_ids(self) -> list[str]:
        """Return all raw IDs that have a display mapping."""
        return list(self._raw_to_display.keys())

    def __len__(self) -> int:
        return len(self._raw_to_display)


def format_evidence_ref(display_map: EvidenceDisplayMap, evidence_ids: list[str]) -> str:
    """Format evidence IDs as user-friendly [E1] [E2] references."""
    if not evidence_ids:
        return ""
    return " ".join(display_map.ref_bracket(eid) for eid in evidence_ids)


def format_evidence_ref_comma(display_map: EvidenceDisplayMap, evidence_ids: list[str]) -> str:
    """Format evidence IDs as comma-separated [E1], [E2] references."""
    if not evidence_ids:
        return ""
    return ", ".join(display_map.ref_bracket(eid) for eid in evidence_ids)


def build_evidence_appendix(
    findings: list[ReviewFinding],
    evidence_records: list[EvidenceRecord],
    display_map: EvidenceDisplayMap,
    *,
    lang: str = "en",
    max_entries: int = MAX_APPENDIX_ENTRIES,
) -> str:
    """Build a self-contained evidence appendix for exported Markdown.

    Each entry includes:
    - Display ref (E1/E2/E3)
    - File path and line range
    - Evidence type
    - Symbol names
    - Related finding titles
    - Short code snippet (truncated)
    """
    # Collect used evidence IDs from findings
    used_ids: set[str] = set()
    # Map evidence_id -> list of finding titles
    ev_to_findings: dict[str, list[str]] = {}
    for finding in findings:
        for eid in finding.evidence_ids:
            used_ids.add(eid)
            title = finding.title or finding.description or ""
            if title:
                ev_to_findings.setdefault(eid, []).append(title)

    # Build lookup for evidence records
    record_by_id: dict[str, EvidenceRecord] = {}
    for record in evidence_records:
        if record.evidence_id in used_ids:
            record_by_id[record.evidence_id] = record

    # Order by display map order
    ordered_ids = [eid for eid in display_map.all_mapped_ids if eid in used_ids]

    # Choose labels based on language
    if lang == "zh":
        title = "# 证据附录"
        type_label = "类型"
        symbol_label = "符号"
        related_label = "关联问题"
        desc_label = "说明"
        desc_text = "该证据来自已解析的代码符号或结构化仓库上下文。"
        snippet_missing = "源码片段未持久化，仅保留文件位置和符号信息。"
        omitted_note = "其余证据已省略，可在重新运行审查后查看完整上下文。"
    else:
        title = "# Evidence Appendix"
        type_label = "Type"
        symbol_label = "Symbol"
        related_label = "Related findings"
        desc_label = "Description"
        desc_text = "This evidence was derived from parsed code symbols or structured repository context."
        snippet_missing = "Source snippet was not persisted; only file location and symbol info are available."
        omitted_note = "Remaining evidence entries were omitted. Re-run the review to see full context."

    lines = [title, ""]

    shown = 0
    for eid in ordered_ids:
        if shown >= max_entries:
            remaining = len(ordered_ids) - shown
            lines.append("")
            lines.append(f"*{omitted_note}* ({remaining})")
            break

        display_ref = display_map.ref(eid)
        record = record_by_id.get(eid)

        if record:
            location = f"{record.file_path}:{record.start_line}-{record.end_line}"
            ev_type = record.kind or "source"
            symbols = record.symbols or []
            snippet = record.snippet or ""
        else:
            # Backward compatibility: no record available
            location = "unknown"
            ev_type = "unknown"
            symbols = []
            snippet = ""

        # Header: ## E1 · src/flask/app.py:392-412
        lines.append(f"## {display_ref} · {location}")
        lines.append("")
        lines.append(f"* {type_label}：{ev_type}")

        if symbols:
            lines.append(f"* {symbol_label}：{', '.join(symbols)}")

        # Related findings
        related = ev_to_findings.get(eid, [])
        if related:
            lines.append(f"* {related_label}：{related[0]}")

        lines.append(f"* {desc_label}：{desc_text}")
        lines.append("")

        # Code snippet
        if snippet:
            truncated = _truncate_snippet(snippet)
            lines.append("```")
            lines.append(truncated)
            lines.append("```")
        else:
            lines.append(f"*{snippet_missing}*")

        lines.append("")
        shown += 1

    return "\n".join(lines)


def _truncate_snippet(snippet: str) -> str:
    """Truncate a code snippet to safe limits."""
    lines = snippet.splitlines()
    if len(lines) > MAX_SNIPPET_LINES:
        lines = lines[:MAX_SNIPPET_LINES]
        lines.append("...")
    result = "\n".join(lines)
    if len(result) > MAX_SNIPPET_CHARS:
        result = result[:MAX_SNIPPET_CHARS] + "\n..."
    return result
