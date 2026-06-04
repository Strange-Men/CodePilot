from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from backend.models.review import ReviewCreateRequest, ReviewCreateResponse, ReviewStatusResponse
from backend.storage.sqlite import ReviewStore
from backend.tasks.runner import ReviewTaskRunner


def build_reviews_router(store: ReviewStore, runner: ReviewTaskRunner) -> APIRouter:
    router = APIRouter(prefix="/api/reviews", tags=["reviews"])

    @router.post("", response_model=ReviewCreateResponse)
    def create_review(payload: ReviewCreateRequest) -> ReviewCreateResponse:
        task_id = runner.submit(str(payload.repo_url))
        return ReviewCreateResponse(task_id=task_id)

    @router.get("/{task_id}", response_model=ReviewStatusResponse)
    def get_review(task_id: str) -> ReviewStatusResponse:
        row = store.get_review(task_id)
        if not row:
            raise HTTPException(status_code=404, detail="Review task not found")
        return ReviewStatusResponse(
            task_id=row["task_id"],
            repo_url=row["repo_url"],
            status=row["status"],
            error=row["error"],
            report_markdown=row["report_markdown"],
            export_path=row["export_path"],
        )

    @router.get("/{task_id}/export")
    def export_review(task_id: str) -> Response:
        row = store.get_review(task_id)
        if not row:
            raise HTTPException(status_code=404, detail="Review task not found")
        if row["status"] != "completed" or not row["report_markdown"]:
            raise HTTPException(status_code=409, detail="Review report is not ready")
        return Response(
            content=row["report_markdown"],
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="codepilot-review-{task_id}.md"'},
        )

    return router

