from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.reviews import build_reviews_router
from backend.models.review import ReviewStatus
from backend.storage.sqlite import ReviewStore


class FakeRunner:
    def __init__(self, store: ReviewStore) -> None:
        self.store = store
        self.submissions: list[str] = []

    def submit(self, repo_url: str) -> str:
        task_id = f"task-{len(self.submissions) + 1}"
        self.submissions.append(repo_url)
        self.store.create_review(task_id, repo_url)
        return task_id


@pytest.fixture
def api_client(tmp_path: Path) -> tuple[TestClient, ReviewStore, FakeRunner]:
    store = ReviewStore(tmp_path / "reviews.db")
    runner = FakeRunner(store)
    app = FastAPI()
    app.include_router(build_reviews_router(store, runner))
    return TestClient(app), store, runner


def test_create_review(api_client: tuple[TestClient, ReviewStore, FakeRunner]) -> None:
    client, store, runner = api_client

    response = client.post("/api/reviews", json={"repo_url": "https://github.com/pallets/flask"})

    assert response.status_code == 200
    assert response.json() == {"task_id": "task-1"}
    assert runner.submissions == ["https://github.com/pallets/flask"]
    assert store.get_review("task-1")["status"] == "pending"


def test_create_review_rejects_invalid_payload(api_client: tuple[TestClient, ReviewStore, FakeRunner]) -> None:
    client, _, _ = api_client

    response = client.post("/api/reviews", json={"repo_url": "not-a-url"})

    assert response.status_code == 422


def test_query_review(api_client: tuple[TestClient, ReviewStore, FakeRunner]) -> None:
    client, store, _ = api_client
    store.create_review("task-1", "https://github.com/pallets/flask")
    store.update_status("task-1", ReviewStatus.parsing)

    response = client.get("/api/reviews/task-1")

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "task-1"
    assert body["repo_url"] == "https://github.com/pallets/flask"
    assert body["status"] == "parsing"


def test_query_invalid_task_id(api_client: tuple[TestClient, ReviewStore, FakeRunner]) -> None:
    client, _, _ = api_client

    response = client.get("/api/reviews/missing")

    assert response.status_code == 404


def test_export_report(api_client: tuple[TestClient, ReviewStore, FakeRunner]) -> None:
    client, store, _ = api_client
    report = "# Architecture Summary\nDone.\n"
    store.create_review("task-1", "https://github.com/pallets/flask")
    store.update_status(
        "task-1",
        ReviewStatus.completed,
        report_markdown=report,
        export_path="reports/task-1.md",
    )

    response = client.get("/api/reviews/task-1/export")

    assert response.status_code == 200
    assert response.text == report
    assert response.headers["content-type"].startswith("text/markdown")
    assert "codepilot-review-task-1.md" in response.headers["content-disposition"]


def test_export_invalid_task_id(api_client: tuple[TestClient, ReviewStore, FakeRunner]) -> None:
    client, _, _ = api_client

    response = client.get("/api/reviews/missing/export")

    assert response.status_code == 404


def test_export_pending_report_returns_conflict(api_client: tuple[TestClient, ReviewStore, FakeRunner]) -> None:
    client, store, _ = api_client
    store.create_review("task-1", "https://github.com/pallets/flask")

    response = client.get("/api/reviews/task-1/export")

    assert response.status_code == 409


def test_failed_review_is_returned_with_error(api_client: tuple[TestClient, ReviewStore, FakeRunner]) -> None:
    client, store, _ = api_client
    store.create_review("task-1", "https://github.com/pallets/flask")
    store.update_status("task-1", ReviewStatus.failed, error="clone failed")

    response = client.get("/api/reviews/task-1")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error"] == "clone failed"
