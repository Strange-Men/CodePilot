from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.errors import install_error_handlers
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
    install_error_handlers(app)
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
    assert response.json()["code"] == "validation_error"


def test_create_review_rejects_non_github_url_with_structured_error(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, _, runner = api_client

    response = client.post("/api/reviews", json={"repo_url": "https://gitlab.com/example/project"})

    assert response.status_code == 422
    assert response.json() == {
        "error": "Invalid request",
        "code": "validation_error",
        "detail": (
            "repo_url: Value error, Use an HTTPS GitHub repository URL such as "
            "https://github.com/owner/repository"
        ),
    }
    assert runner.submissions == []


def test_create_review_accepts_canonical_github_url(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, _, runner = api_client

    response = client.post("/api/reviews", json={"repo_url": "https://github.com/example/project.git"})

    assert response.status_code == 200
    assert runner.submissions == ["https://github.com/example/project.git"]


@pytest.mark.parametrize(
    "repo_url",
    [
        "http://github.com/example/project",
        "https://github.com/example/project/issues",
        "https://github.com/example/project?tab=readme",
        "https://github.com.evil.example/example/project",
    ],
)
def test_create_review_rejects_noncanonical_github_urls(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
    repo_url: str,
) -> None:
    client, _, runner = api_client

    response = client.post("/api/reviews", json={"repo_url": repo_url})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert runner.submissions == []


def test_list_reviews_returns_newest_first(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    store.create_review("task-1", "https://github.com/example/one")
    store.create_review("task-2", "https://github.com/example/two")
    store.update_status("task-2", ReviewStatus.completed, report_markdown="# Architecture Summary\nDone.")

    response = client.get("/api/reviews")

    assert response.status_code == 200
    assert [row["task_id"] for row in response.json()] == ["task-2", "task-1"]
    assert response.json()[0]["report_markdown"] == "# Architecture Summary\nDone."


def test_list_reviews_respects_limit(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    store.create_review("task-1", "https://github.com/example/one")
    store.create_review("task-2", "https://github.com/example/two")

    response = client.get("/api/reviews?limit=1")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_reviews_rejects_invalid_limit_with_structured_error(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, _, _ = api_client

    response = client.get("/api/reviews?limit=0")

    assert response.status_code == 422
    assert response.json()["error"] == "Invalid request"
    assert response.json()["code"] == "validation_error"


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
    assert response.json() == {
        "error": "Review not found",
        "code": "review_not_found",
        "detail": "No review exists for task 'missing'.",
    }


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
    assert response.json()["code"] == "review_not_ready"


def test_failed_review_is_returned_with_error(api_client: tuple[TestClient, ReviewStore, FakeRunner]) -> None:
    client, store, _ = api_client
    store.create_review("task-1", "https://github.com/pallets/flask")
    store.update_status("task-1", ReviewStatus.failed, error="clone failed")

    response = client.get("/api/reviews/task-1")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error"] == "clone failed"
