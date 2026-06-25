from __future__ import annotations

import re

from fastapi import APIRouter, Query, Response

from backend.api.errors import APIError
from backend.models.review import (
    ReviewAgentStateResponse,
    ReviewAgentStatesResponse,
    ReviewCreateRequest,
    ReviewCreateResponse,
    ReviewEvidenceRefResponse,
    ReviewFindingResponse,
    ReviewFindingsResponse,
    ReviewProgressSnapshot,
    ReviewStatus,
    ReviewStatusResponse,
)
from backend.reviewers.localization import Language, normalize_language
from backend.reviewers.localized_report_renderer import (
    render_localized_finding_text,
    render_localized_report,
)
from backend.reviewers.zh_presentation import finalize_zh_report, repair_zh_findings
from backend.reviewers.zh_quality import normalize_zh_text
from backend.services.localization_service import LocalizationService
from backend.storage.sqlite import ReviewStore
from backend.tasks.runner import PLANNED_AGENTS, ReviewTaskRunner


def _has_bilingual_display(finding_row: dict) -> bool:
    """Check if a finding row has bilingual display data for the requested language."""
    display = finding_row.get("display")
    if not display or not isinstance(display, dict):
        return False
    zh = display.get("zh")
    if not zh or not isinstance(zh, dict):
        return False
    # Check if zh has any non-null prose field
    prose_fields = ("title", "description", "recommendation", "impact", "first_step", "confidence_rationale", "caveat")
    return any(zh.get(f) for f in prose_fields)


def _all_findings_bilingual(findings: list[dict]) -> bool:
    """Check if all findings have bilingual display data."""
    if not findings:
        return False
    return all(_has_bilingual_display(f) for f in findings)

_SECRET_PATTERN = re.compile(
    r"(?:api[_-]?key|token|secret|password|authorization|bearer)\s*[=:]\s*\S+",
    re.IGNORECASE,
)


def _sanitize_error(raw: str | None, *, max_len: int = 200) -> str | None:
    """Return a sanitized error string safe for API responses.

    Strips potential secrets (API keys, tokens, bearer values) and truncates.
    Returns None if nothing useful remains after sanitization.
    """
    if not raw:
        return None
    cleaned = _SECRET_PATTERN.sub("[REDACTED]", raw)
    # Also redact bare long hex/base64 tokens (32+ chars of hex or base64)
    cleaned = re.sub(r"\b[A-Za-z0-9+/=_-]{32,}\b", "[REDACTED]", cleaned)
    cleaned = cleaned.strip()
    if not cleaned:
        return "Agent execution failed."
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len] + "…"
    return cleaned


SEVERITY_KEYS = ("critical", "high", "medium", "low")
PLANNED_AGENT_DETAILS = {
    agent_id: (order, label)
    for order, (agent_id, label) in enumerate(PLANNED_AGENTS, start=1)
}


def build_reviews_router(
    store: ReviewStore,
    runner: ReviewTaskRunner,
    localization_service: LocalizationService | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/reviews", tags=["reviews"])

    @router.post("", response_model=ReviewCreateResponse, status_code=202)
    def create_review(payload: ReviewCreateRequest) -> ReviewCreateResponse:
        task_id = runner.submit(
            str(payload.repo_url),
            llm_mode=payload.llm_mode,
            llm_provider=payload.llm_provider,
        )
        return ReviewCreateResponse(
            task_id=task_id,
            llm_mode=payload.llm_mode,
            llm_provider=payload.llm_provider if payload.llm_mode != "mock" else None,
        )

    @router.get("", response_model=list[ReviewStatusResponse])
    def list_reviews(limit: int = Query(default=50, ge=1, le=100)) -> list[ReviewStatusResponse]:
        return [_review_response(row) for row in store.list_reviews(limit)]

    @router.get("/{task_id}", response_model=ReviewStatusResponse)
    def get_review(task_id: str, lang: str = Query(default="en")) -> ReviewStatusResponse:
        normalized_lang = normalize_language(lang)
        row = _get_review_or_404(store, task_id)
        get_progress = getattr(runner, "get_progress", None)
        progress = get_progress(task_id) if callable(get_progress) else None

        report_markdown = row["report_markdown"]
        if report_markdown:
            raw_findings = store.get_structured_findings(task_id)
            from backend.models.structured_review import ReviewFinding as _RF
            from backend.reviewers.evidence_display import EvidenceDisplayMap as _EDM

            _finding_objs = [
                _RF(
                    section=f["section"],
                    description=f["description"],
                    title=f.get("title"),
                    severity=f.get("severity", "informational"),
                    category=f.get("category"),
                    confidence=f.get("confidence"),
                    files=f.get("files", []),
                    recommendation=f.get("recommendation"),
                    evidence_ids=f.get("evidence_ids", []),
                    evidence=f.get("evidence", []),
                    impact=f.get("impact"),
                    first_step=f.get("first_step"),
                    validation_tests=f.get("validation_tests", []),
                    confidence_rationale=f.get("confidence_rationale"),
                    caveat=f.get("caveat"),
                )
                for f in raw_findings
            ]
            _display_map = _EDM.from_findings(_finding_objs)

            if normalized_lang == "zh":
                if _all_findings_bilingual(raw_findings):
                    # New bilingual reviews: render zh report from stored display fields
                    from backend.models.structured_review import DisplayFields, ReviewFinding

                    findings_with_display = []
                    for f in raw_findings:
                        display_data = f.get("display")
                        display = DisplayFields.model_validate(display_data) if display_data else None
                        finding = ReviewFinding(
                            section=f["section"],
                            description=f["description"],
                            title=f.get("title"),
                            severity=f.get("severity", "informational"),
                            category=f.get("category"),
                            confidence=f.get("confidence"),
                            files=f.get("files", []),
                            recommendation=f.get("recommendation"),
                            evidence_ids=f.get("evidence_ids", []),
                            evidence=f.get("evidence", []),
                            impact=f.get("impact"),
                            first_step=f.get("first_step"),
                            validation_tests=f.get("validation_tests", []),
                            confidence_rationale=f.get("confidence_rationale"),
                            caveat=f.get("caveat"),
                            display=display,
                        )
                        findings_with_display.append(finding)
                    # Repair display.zh fields before rendering (centralized zh pipeline)
                    findings_with_display = repair_zh_findings(findings_with_display)
                    from backend.models.structured_review import StructuredReviewDraft

                    draft = StructuredReviewDraft(findings=findings_with_display)
                    report_markdown = render_localized_report(
                        report_markdown, normalized_lang, findings=findings_with_display,
                    )
                    # Replace English finding prose with zh display fields in the report
                    report_markdown = _render_bilingual_report(report_markdown, draft, normalized_lang)
                    # Final quality guard: metadata repair + normalize remaining English leakage
                    report_markdown = finalize_zh_report(report_markdown)
                elif localization_service is not None:
                    # Legacy reviews: use localization service as fallback
                    source_updated_at = row.get("updated_at", "")
                    report_markdown = localization_service.get_localized_report(
                        task_id, normalized_lang, source_updated_at, report_markdown, raw_findings,
                    )
                else:
                    report_markdown = render_localized_report(report_markdown, normalized_lang)
            else:
                # English view: replace raw ev_* with [E1]/[E2]
                report_markdown = _display_map.replace_in_text(report_markdown)

        return _review_response(row, progress=progress, report_markdown=report_markdown)

    @router.get("/{task_id}/findings", response_model=ReviewFindingsResponse)
    def get_review_findings(task_id: str, lang: str = Query(default="en")) -> ReviewFindingsResponse:
        normalized_lang = normalize_language(lang)
        review_row = _get_review_or_404(store, task_id)
        evidence_by_id = {
            row["evidence_id"]: row
            for row in store.get_evidence_refs(task_id)
        }
        raw_findings = store.get_structured_findings(task_id)

        if normalized_lang == "zh":
            if _all_findings_bilingual(raw_findings):
                # New bilingual reviews: use stored display.zh fields directly
                localized_findings = raw_findings
            elif localization_service is not None:
                # Legacy reviews: use localization service as fallback
                source_updated_at = review_row.get("updated_at", "")
                localized_findings = localization_service.get_localized_findings(
                    task_id, normalized_lang, source_updated_at, raw_findings,
                )
            else:
                localized_findings = raw_findings
        else:
            localized_findings = raw_findings

        # Build evidence display map (E1/E2) for frontend
        from backend.models.structured_review import ReviewFinding as _RF2
        from backend.reviewers.evidence_display import EvidenceDisplayMap as _EDM2

        _finding_objs2 = [
            _RF2(
                section=f["section"],
                description=f["description"],
                title=f.get("title"),
                severity=f.get("severity", "informational"),
                category=f.get("category"),
                confidence=f.get("confidence"),
                files=f.get("files", []),
                evidence_ids=f.get("evidence_ids", []),
            )
            for f in raw_findings
        ]
        _display_map2 = _EDM2.from_findings(_finding_objs2)

        return ReviewFindingsResponse(
            task_id=task_id,
            findings=[
                _finding_response(row, evidence_by_id, lang=normalized_lang)
                for row in localized_findings
            ],
            evidence_display_map={raw: _display_map2.ref(raw) for raw in _display_map2.all_mapped_ids},
        )

    @router.get("/{task_id}/agent-states", response_model=ReviewAgentStatesResponse)
    def get_review_agent_states(task_id: str) -> ReviewAgentStatesResponse:
        _get_review_or_404(store, task_id)
        rows = sorted(
            store.get_agent_states(task_id),
            key=lambda row: (
                PLANNED_AGENT_DETAILS.get(row["agent_id"], (len(PLANNED_AGENTS) + 1, ""))[0],
                row["agent_id"],
            ),
        )
        unknown_orders = {
            row["agent_id"]: len(PLANNED_AGENTS) + index
            for index, row in enumerate(
                (row for row in rows if row["agent_id"] not in PLANNED_AGENT_DETAILS),
                start=1,
            )
        }
        return ReviewAgentStatesResponse(
            task_id=task_id,
            agents=[
                _agent_state_response(row, unknown_orders)
                for row in rows
            ],
        )

    @router.get("/{task_id}/export")
    def export_review(task_id: str, lang: str = Query(default="en")) -> Response:
        normalized_lang = normalize_language(lang)
        row = _get_review_or_404(store, task_id)
        if row["status"] != "completed" or not row["report_markdown"]:
            raise APIError(
                409,
                "Review not ready",
                "review_not_ready",
                "The review must complete before its Markdown report can be exported.",
            )
        content = row["report_markdown"]
        # Apply evidence display mapping (E1/E2) for all exports
        raw_findings = store.get_structured_findings(task_id)
        from backend.models.structured_review import ReviewFinding as _RF
        from backend.reviewers.evidence_display import EvidenceDisplayMap as _EDM

        _finding_objs = [
            _RF(
                section=f["section"],
                description=f["description"],
                title=f.get("title"),
                severity=f.get("severity", "informational"),
                category=f.get("category"),
                confidence=f.get("confidence"),
                files=f.get("files", []),
                recommendation=f.get("recommendation"),
                evidence_ids=f.get("evidence_ids", []),
                evidence=f.get("evidence", []),
                impact=f.get("impact"),
                first_step=f.get("first_step"),
                validation_tests=f.get("validation_tests", []),
                confidence_rationale=f.get("confidence_rationale"),
                caveat=f.get("caveat"),
            )
            for f in raw_findings
        ]
        _display_map = _EDM.from_findings(_finding_objs)

        if normalized_lang == "zh":
            if _all_findings_bilingual(raw_findings):
                # New bilingual reviews: render from stored display fields
                from backend.models.structured_review import DisplayFields, ReviewFinding

                findings_with_display = []
                for f in raw_findings:
                    display_data = f.get("display")
                    display = DisplayFields.model_validate(display_data) if display_data else None
                    finding = ReviewFinding(
                        section=f["section"],
                        description=f["description"],
                        title=f.get("title"),
                        severity=f.get("severity", "informational"),
                        category=f.get("category"),
                        confidence=f.get("confidence"),
                        files=f.get("files", []),
                        recommendation=f.get("recommendation"),
                        evidence_ids=f.get("evidence_ids", []),
                        evidence=f.get("evidence", []),
                        impact=f.get("impact"),
                        first_step=f.get("first_step"),
                        validation_tests=f.get("validation_tests", []),
                        confidence_rationale=f.get("confidence_rationale"),
                        caveat=f.get("caveat"),
                        display=display,
                    )
                    findings_with_display.append(finding)
                # Repair display.zh fields before rendering (centralized zh pipeline)
                findings_with_display = repair_zh_findings(findings_with_display)
                from backend.models.structured_review import StructuredReviewDraft

                draft = StructuredReviewDraft(findings=findings_with_display)
                content = render_localized_report(
                    content, normalized_lang, findings=findings_with_display,
                )
                content = _render_bilingual_report(content, draft, normalized_lang)
                # Final quality guard: metadata repair + normalize remaining English leakage
                content = finalize_zh_report(content)
                # Replace raw ev_* IDs with [E1]/[E2] display refs
                content = _display_map.replace_in_text(content)
            elif localization_service is not None:
                source_updated_at = row.get("updated_at", "")
                content = localization_service.get_localized_report(
                    task_id, normalized_lang, source_updated_at, content, raw_findings,
                )
            else:
                content = render_localized_report(content, normalized_lang)
        else:
            # English export: replace raw ev_* with [E1]/[E2]
            content = _display_map.replace_in_text(content)
        suffix = "-zh" if normalized_lang == "zh" else ""
        filename = f"codepilot-review-{task_id}{suffix}.md"
        return Response(
            content=content,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "text/markdown; charset=utf-8",
            },
        )

    @router.delete("/{task_id}", status_code=204)
    def delete_review(task_id: str) -> Response:
        row = _get_review_or_404(store, task_id)
        if row["status"] not in {ReviewStatus.completed.value, ReviewStatus.failed.value}:
            raise _review_in_progress_error()
        try:
            deleted = store.delete_review(task_id)
        except ValueError as exc:
            raise _review_in_progress_error() from exc
        if not deleted:
            _raise_review_not_found(task_id)
        return Response(status_code=204)

    return router


def _get_review_or_404(store: ReviewStore, task_id: str) -> dict:
    row = store.get_review(task_id)
    if not row:
        _raise_review_not_found(task_id)
    return row


def _raise_review_not_found(task_id: str) -> None:
    raise APIError(
        404,
        "Review not found",
        "review_not_found",
        f"No review exists for task '{task_id}'.",
    )


def _review_in_progress_error() -> APIError:
    return APIError(
        409,
        "Review is still in progress",
        "review_in_progress",
        "Only completed or failed reviews can be deleted.",
    )


def _finding_response(
    row: dict,
    evidence_by_id: dict[str, dict],
    lang: Language = "en",
) -> ReviewFindingResponse:
    evidence_refs = [
        _evidence_ref_response(evidence_by_id[evidence_id])
        for evidence_id in row["evidence_ids"]
        if evidence_id in evidence_by_id
    ]
    title = row["title"] or row["description"]
    description = row["description"]
    recommendation = row["recommendation"]
    impact = row.get("impact")
    first_step = row.get("first_step")
    caveat = row.get("caveat")
    confidence_rationale = row.get("confidence_rationale")
    validation_tests = row.get("validation_tests") or []

    # Check for bilingual display fields (new reviews)
    display = row.get("display")
    if lang == "zh" and display and isinstance(display, dict):
        zh = display.get("zh")
        if zh and isinstance(zh, dict):
            title = normalize_zh_text(zh.get("title") or title)
            description = normalize_zh_text(zh.get("description") or description)
            recommendation = normalize_zh_text(zh.get("recommendation") or recommendation)
            impact = normalize_zh_text(zh.get("impact") or impact)
            first_step = normalize_zh_text(zh.get("first_step") or first_step)
            caveat = normalize_zh_text(zh.get("caveat") or caveat)
            confidence_rationale = normalize_zh_text(zh.get("confidence_rationale") or confidence_rationale)
            zh_tests = zh.get("validation_tests")
            if isinstance(zh_tests, list) and zh_tests:
                validation_tests = [normalize_zh_text(t) for t in zh_tests]
    elif lang == "zh":
        # Legacy fallback: use *_zh keys from localization service
        def _zh_legacy(field: str, fallback: str | None, default: str = "") -> str:
            raw = row.get(f"{field}_zh") or render_localized_finding_text(fallback, lang)
            return normalize_zh_text(raw or default)

        title = _zh_legacy("title", title, title)
        description = _zh_legacy("description", description, description)
        recommendation = _zh_legacy("recommendation", recommendation)
        impact = _zh_legacy("impact", impact)
        first_step = _zh_legacy("first_step", first_step)
        caveat = _zh_legacy("caveat", caveat)
        confidence_rationale = normalize_zh_text(
            row.get("confidence_rationale_zh") or confidence_rationale or "",
        )
        zh_tests = row.get("validation_tests_zh")
        if isinstance(zh_tests, list) and len(zh_tests) == len(validation_tests):
            validation_tests = [normalize_zh_text(t) for t in zh_tests]

    return ReviewFindingResponse(
        finding_id=str(row["id"]),
        finding_index=row["finding_index"],
        section=row["section"],
        title=title,
        description=description,
        severity=row["severity"],
        category=row["category"],
        confidence=row["confidence"] if row["confidence"] is not None else 0.0,
        recommendation=recommendation,
        files=row["files"],
        evidence_ids=row["evidence_ids"],
        evidence_refs=evidence_refs,
        validation_status=row["validation_status"],
        impact=impact,
        first_step=first_step,
        validation_tests=validation_tests,
        confidence_rationale=confidence_rationale,
        caveat=caveat,
    )


def _evidence_ref_response(row: dict) -> ReviewEvidenceRefResponse:
    symbols = row.get("symbols") or []
    return ReviewEvidenceRefResponse(
        evidence_id=row["evidence_id"],
        file_path=row.get("file_path"),
        symbol_name=symbols[0] if symbols else None,
        start_line=row["start_line"],
        end_line=row["end_line"],
    )


def _agent_state_response(
    row: dict,
    unknown_orders: dict[str, int],
) -> ReviewAgentStateResponse:
    agent_id = row["agent_id"]
    planned_details = PLANNED_AGENT_DETAILS.get(agent_id)
    if planned_details is None:
        order = unknown_orders[agent_id]
        label = f"A{order} {agent_id}"
    else:
        order, label = planned_details
    findings = row["findings"]
    severity_mix = {severity: 0 for severity in SEVERITY_KEYS}
    confidences: list[float] = []
    evidence_ids = set(row["evidence_ids"])
    for finding in findings:
        severity = str(finding.get("severity") or "").lower()
        if severity in severity_mix:
            severity_mix[severity] += 1
        confidence = finding.get("confidence")
        if isinstance(confidence, int | float) and not isinstance(confidence, bool):
            confidences.append(float(confidence))
        evidence_ids.update(finding.get("evidence_ids") or [])
    return ReviewAgentStateResponse(
        order=order,
        agent_id=agent_id,
        label=label,
        status=row["status"],
        findings_count=len(findings),
        evidence_count=len(evidence_ids),
        severity_mix=severity_mix,
        average_confidence=round(sum(confidences) / len(confidences), 2) if confidences else None,
        error=_sanitize_error(row.get("error")),
    )


def _review_response(
    row: dict,
    progress: ReviewProgressSnapshot | None = None,
    report_markdown: str | None = None,
) -> ReviewStatusResponse:
    return ReviewStatusResponse(
        task_id=row["task_id"],
        repo_url=row["repo_url"],
        status=row["status"],
        error=row["error"],
        report_markdown=report_markdown if report_markdown is not None else row["report_markdown"],
        export_path=row["export_path"],
        progress=progress,
    )


def _render_bilingual_report(
    report_markdown: str,
    draft: object,
    lang: str,
) -> str:
    """Replace English finding prose in the report with bilingual display fields.

    Uses longest-first replacement to avoid partial matches.
    Only replaces prose content; structural elements (headings, tables, evidence IDs)
    are already translated by render_localized_report.
    """
    replacements: dict[str, str] = {}
    for finding in draft.findings:
        # Build replacement pairs for each prose field
        fields = [
            ("title", finding.title),
            ("description", finding.description),
            ("recommendation", finding.recommendation),
            ("impact", finding.impact),
            ("first_step", finding.first_step),
            ("confidence_rationale", finding.confidence_rationale),
            ("caveat", finding.caveat),
        ]
        for field_name, en_value in fields:
            if not en_value:
                continue
            zh_value = finding._display_field(field_name, lang)
            if zh_value and zh_value != en_value:
                replacements[en_value] = zh_value

        # Handle validation_tests
        en_tests = finding.validation_tests
        zh_tests = finding._display_validation_tests(lang)
        if en_tests and zh_tests and len(en_tests) == len(zh_tests):
            for en_test, zh_test in zip(en_tests, zh_tests, strict=False):
                if en_test and zh_test and en_test != zh_test:
                    replacements[en_test] = zh_test

    # Apply replacements longest-first to avoid partial matches
    for en, zh in sorted(replacements.items(), key=lambda x: -len(x[0])):
        report_markdown = report_markdown.replace(en, zh)

    return report_markdown
