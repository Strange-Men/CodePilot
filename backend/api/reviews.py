from __future__ import annotations

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
from backend.storage.sqlite import ReviewStore
from backend.tasks.runner import PLANNED_AGENTS, ReviewTaskRunner

SEVERITY_KEYS = ("critical", "high", "medium", "low")
PLANNED_AGENT_DETAILS = {
    agent_id: (order, label)
    for order, (agent_id, label) in enumerate(PLANNED_AGENTS, start=1)
}


def build_reviews_router(store: ReviewStore, runner: ReviewTaskRunner) -> APIRouter:
    router = APIRouter(prefix="/api/reviews", tags=["reviews"])

    @router.post("", response_model=ReviewCreateResponse, status_code=202)
    def create_review(payload: ReviewCreateRequest) -> ReviewCreateResponse:
        task_id = runner.submit(str(payload.repo_url), llm_mode=payload.llm_mode)
        return ReviewCreateResponse(task_id=task_id, llm_mode=payload.llm_mode)

    @router.get("", response_model=list[ReviewStatusResponse])
    def list_reviews(limit: int = Query(default=50, ge=1, le=100)) -> list[ReviewStatusResponse]:
        return [_review_response(row) for row in store.list_reviews(limit)]

    @router.get("/{task_id}", response_model=ReviewStatusResponse)
    def get_review(task_id: str) -> ReviewStatusResponse:
        row = _get_review_or_404(store, task_id)
        get_progress = getattr(runner, "get_progress", None)
        progress = get_progress(task_id) if callable(get_progress) else None
        return _review_response(row, progress=progress)

    @router.get("/{task_id}/findings", response_model=ReviewFindingsResponse)
    def get_review_findings(task_id: str) -> ReviewFindingsResponse:
        _get_review_or_404(store, task_id)
        evidence_by_id = {
            row["evidence_id"]: row
            for row in store.get_evidence_refs(task_id)
        }
        return ReviewFindingsResponse(
            task_id=task_id,
            findings=[
                _finding_response(row, evidence_by_id)
                for row in store.get_structured_findings(task_id)
            ],
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
    def export_review(task_id: str) -> Response:
        row = _get_review_or_404(store, task_id)
        if row["status"] != "completed" or not row["report_markdown"]:
            raise APIError(
                409,
                "Review not ready",
                "review_not_ready",
                "The review must complete before its Markdown report can be exported.",
            )
        return Response(
            content=row["report_markdown"],
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="codepilot-review-{task_id}.md"'},
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
) -> ReviewFindingResponse:
    evidence_refs = [
        _evidence_ref_response(evidence_by_id[evidence_id])
        for evidence_id in row["evidence_ids"]
        if evidence_id in evidence_by_id
    ]
    return ReviewFindingResponse(
        finding_id=str(row["id"]),
        finding_index=row["finding_index"],
        section=row["section"],
        title=row["title"] or row["description"],
        description=row["description"],
        severity=row["severity"],
        category=row["category"],
        confidence=row["confidence"] if row["confidence"] is not None else 0.0,
        recommendation=row["recommendation"],
        files=row["files"],
        evidence_ids=row["evidence_ids"],
        evidence_refs=evidence_refs,
        validation_status=row["validation_status"],
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
        if isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
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
        error="Agent execution failed." if row.get("error") else None,
    )


def _review_response(
    row: dict,
    progress: ReviewProgressSnapshot | None = None,
) -> ReviewStatusResponse:
    return ReviewStatusResponse(
        task_id=row["task_id"],
        repo_url=row["repo_url"],
        status=row["status"],
        error=row["error"],
        report_markdown=row["report_markdown"],
        export_path=row["export_path"],
        progress=progress,
    )
