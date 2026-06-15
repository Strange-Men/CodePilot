from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.errors import install_error_handlers
from backend.api.reviews import build_reviews_router
from backend.models.context import EvidenceRecord
from backend.models.review import ReviewStatus
from backend.models.review_state import AgentExecutionState
from backend.models.structured_review import ReviewFinding
from backend.storage.sqlite import ReviewStore


class FakeRunner:
    def __init__(self, store: ReviewStore) -> None:
        self.store = store
        self.submissions: list[str] = []

    def submit(self, repo_url: str, llm_mode: str = "mock") -> str:
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

    assert response.status_code == 202
    body = response.json()
    assert body["task_id"] == "task-1"
    assert body["llm_mode"] == "mock"
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

    assert response.status_code == 202
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


def test_get_review_findings_returns_structured_findings_and_evidence_refs(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    store.create_review("task-1", "https://github.com/example/project")
    store.replace_structured_findings(
        "task-1",
        [
            ReviewFinding(
                section="Architecture Summary",
                title="Boundary risk",
                description="The API boundary has mixed responsibilities.",
                severity="high",
                category="architecture",
                confidence=0.91,
                recommendation="Separate transport and domain responsibilities.",
                files=["backend/api/reviews.py"],
                evidence_ids=["ev_safe"],
                evidence=["ev_safe -> backend/api/reviews.py:10-20"],
            )
        ],
        [
            EvidenceRecord(
                evidence_id="ev_safe",
                file_path="backend/api/reviews.py",
                start_line=10,
                end_line=20,
                snippet="API_TOKEN=super-secret",
                kind="symbol",
                symbols=["build_reviews_router"],
            )
        ],
    )

    response = client.get("/api/reviews/task-1/findings")

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "task-1"
    assert body["findings"] == [
        {
            "finding_id": "1",
            "finding_index": 0,
            "section": "Architecture Summary",
            "title": "Boundary risk",
            "description": "The API boundary has mixed responsibilities.",
            "severity": "high",
            "category": "architecture",
            "confidence": 0.91,
            "recommendation": "Separate transport and domain responsibilities.",
            "files": ["backend/api/reviews.py"],
            "evidence_ids": ["ev_safe"],
            "evidence_refs": [
                {
                    "evidence_id": "ev_safe",
                    "file_path": "backend/api/reviews.py",
                    "symbol_name": "build_reviews_router",
                    "start_line": 10,
                    "end_line": 20,
                }
            ],
            "validation_status": "validated",
        }
    ]
    assert "super-secret" not in response.text
    assert "snippet" not in response.text
    assert "agent_id" not in response.text


def test_get_review_findings_returns_empty_list_for_legacy_review(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    store.create_review("task-1", "https://github.com/example/project")

    response = client.get("/api/reviews/task-1/findings")

    assert response.status_code == 200
    assert response.json() == {"task_id": "task-1", "findings": []}


def test_get_review_findings_returns_404_for_missing_review(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, _, _ = api_client

    response = client.get("/api/reviews/missing/findings")

    assert response.status_code == 404
    assert response.json()["code"] == "review_not_found"


def test_get_review_agent_states_returns_computed_summary_fields(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    store.create_review("task-1", "https://github.com/example/project")
    store.replace_agent_states(
        "task-1",
        [
            AgentExecutionState(
                agent_id="ArchitectureAgent",
                status="completed",
                findings=[
                    ReviewFinding(
                        section="Architecture Summary",
                        description="High-confidence boundary issue.",
                        severity="high",
                        confidence=0.9,
                        evidence_ids=["ev_1"],
                    ),
                    ReviewFinding(
                        section="Architecture Summary",
                        description="Medium-confidence coupling issue.",
                        severity="medium",
                        confidence=0.8,
                        evidence_ids=["ev_2"],
                    ),
                    ReviewFinding(
                        section="Architecture Summary",
                        description="Second medium-confidence issue.",
                        severity="medium",
                        confidence=0.82,
                        evidence_ids=["ev_3"],
                    ),
                ],
                evidence_ids=["ev_1", "ev_4"],
            ),
            AgentExecutionState(
                agent_id="CodeSmellAgent",
                status="failed",
                error="MIMO_API_KEY=super-secret",
                validation_status="failed",
            ),
        ],
    )

    response = client.get("/api/reviews/task-1/agent-states")

    assert response.status_code == 200
    assert response.json() == {
        "task_id": "task-1",
        "agents": [
            {
                "order": 1,
                "agent_id": "ArchitectureAgent",
                "label": "A1 ArchitectureAgent",
                "status": "completed",
                "findings_count": 3,
                "evidence_count": 4,
                "severity_mix": {
                    "critical": 0,
                    "high": 1,
                    "medium": 2,
                    "low": 0,
                },
                "average_confidence": 0.84,
                "error": None,
            },
            {
                "order": 2,
                "agent_id": "CodeSmellAgent",
                "label": "A2 CodeSmellAgent",
                "status": "failed",
                "findings_count": 0,
                "evidence_count": 0,
                "severity_mix": {
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0,
                },
                "average_confidence": None,
                "error": "Agent execution failed.",
            },
        ],
    }
    assert "super-secret" not in response.text


def test_get_review_agent_states_returns_empty_list_for_legacy_review(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    store.create_review("task-1", "https://github.com/example/project")

    response = client.get("/api/reviews/task-1/agent-states")

    assert response.status_code == 200
    assert response.json() == {"task_id": "task-1", "agents": []}


def test_get_review_agent_states_returns_four_agents_for_v3_review(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    store.create_review("task-v3", "https://github.com/example/project")
    store.replace_agent_states(
        "task-v3",
        [
            AgentExecutionState(agent_id="ArchitectureAgent", status="completed", validation_status="validated"),
            AgentExecutionState(agent_id="CodeSmellAgent", status="completed", validation_status="validated"),
            AgentExecutionState(agent_id="MaintainabilityAgent", status="completed", validation_status="validated"),
            AgentExecutionState(agent_id="RefactorAgent", status="completed", validation_status="validated"),
        ],
    )

    response = client.get("/api/reviews/task-v3/agent-states")

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "task-v3"
    assert len(body["agents"]) == 4
    assert [agent["agent_id"] for agent in body["agents"]] == [
        "ArchitectureAgent",
        "CodeSmellAgent",
        "MaintainabilityAgent",
        "RefactorAgent",
    ]
    assert all(agent["status"] == "completed" for agent in body["agents"])


def test_get_review_agent_states_returns_404_for_missing_review(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, _, _ = api_client

    response = client.get("/api/reviews/missing/agent-states")

    assert response.status_code == 404
    assert response.json()["code"] == "review_not_found"


def test_delete_completed_review_returns_204(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    store.create_review("task-1", "https://github.com/example/project")
    store.update_status("task-1", ReviewStatus.completed, report_markdown="# Complete")

    response = client.delete("/api/reviews/task-1")

    assert response.status_code == 204
    assert response.content == b""
    assert store.get_review("task-1") is None


def test_delete_failed_review_returns_204(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    store.create_review("task-1", "https://github.com/example/project")
    store.update_status("task-1", ReviewStatus.failed, error="Review failed.")

    response = client.delete("/api/reviews/task-1")

    assert response.status_code == 204
    assert response.content == b""
    assert store.get_review("task-1") is None


@pytest.mark.parametrize(
    "status",
    [
        ReviewStatus.pending,
        ReviewStatus.cloning,
        ReviewStatus.parsing,
        ReviewStatus.summarizing,
        ReviewStatus.reviewing,
    ],
)
def test_delete_active_review_returns_conflict(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
    status: ReviewStatus,
) -> None:
    client, store, _ = api_client
    store.create_review("task-1", "https://github.com/example/project")
    store.update_status("task-1", status)

    response = client.delete("/api/reviews/task-1")

    assert response.status_code == 409
    assert response.json() == {
        "error": "Review is still in progress",
        "code": "review_in_progress",
        "detail": "Only completed or failed reviews can be deleted.",
    }
    assert store.get_review("task-1") is not None


def test_delete_missing_review_returns_404(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, _, _ = api_client

    response = client.delete("/api/reviews/missing")

    assert response.status_code == 404
    assert response.json()["code"] == "review_not_found"
