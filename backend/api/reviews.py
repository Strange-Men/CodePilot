from __future__ import annotations

from fastapi import APIRouter, Query, Response

from backend.api.errors import APIError
from backend.models.review import ReviewCreateRequest, ReviewCreateResponse, ReviewStatusResponse
from backend.storage.sqlite import ReviewStore
from backend.tasks.runner import ReviewTaskRunner


def build_reviews_router(store: ReviewStore, runner: ReviewTaskRunner) -> APIRouter:
    router = APIRouter(prefix="/api/reviews", tags=["reviews"])

    @router.post("", response_model=ReviewCreateResponse)
    def create_review(payload: ReviewCreateRequest) -> ReviewCreateResponse:
        task_id = runner.submit(str(payload.repo_url), llm_mode=payload.llm_mode)
        return ReviewCreateResponse(task_id=task_id, llm_mode=payload.llm_mode)

    @router.get("", response_model=list[ReviewStatusResponse])
    def list_reviews(limit: int = Query(default=50, ge=1, le=100)) -> list[ReviewStatusResponse]:
        return [_review_response(row) for row in store.list_reviews(limit)]

    @router.get("/{task_id}", response_model=ReviewStatusResponse)
    def get_review(task_id: str) -> ReviewStatusResponse:
        row = store.get_review(task_id)
        if not row:
            raise APIError(
                404,
                "Review not found",
                "review_not_found",
                f"No review exists for task '{task_id}'.",
            )
        return _review_response(row)

    @router.get("/{task_id}/export")
    def export_review(task_id: str) -> Response:
        row = store.get_review(task_id)
        if not row:
            raise APIError(
                404,
                "Review not found",
                "review_not_found",
                f"No review exists for task '{task_id}'.",
            )
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

    return router


def _review_response(row: dict) -> ReviewStatusResponse:
    return ReviewStatusResponse(
        task_id=row["task_id"],
        repo_url=row["repo_url"],
        status=row["status"],
        error=row["error"],
        report_markdown=row["report_markdown"],
        export_path=row["export_path"],
    )
