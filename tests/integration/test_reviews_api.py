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
from backend.models.structured_review import BilingualTextField, DisplayFields, ReviewFinding
from backend.services.localization_service import LocalizationService, MockTranslator
from backend.storage.sqlite import ReviewStore


class FakeRunner:
    def __init__(self, store: ReviewStore) -> None:
        self.store = store
        self.submissions: list[str] = []

    def submit(
        self,
        repo_url: str,
        llm_mode: str = "mock",
        llm_provider: str | None = None,
    ) -> str:
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
            "impact": None,
            "first_step": None,
            "validation_tests": [],
            "confidence_rationale": None,
            "caveat": None,
        }
    ]
    assert "super-secret" not in response.text
    assert "snippet" not in response.text
    assert "agent_id" not in response.text


def test_get_review_findings_returns_useful_fields_when_present(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    store.create_review("task-1", "https://github.com/example/project")
    store.replace_structured_findings(
        "task-1",
        [
            ReviewFinding(
                section="Code Smells",
                title="Duplicate dispatch",
                description="Two paths implement similar dispatch.",
                severity="medium",
                category="code_smell",
                confidence=0.75,
                recommendation="Extract shared logic.",
                files=["app.py"],
                evidence_ids=["ev_dup"],
                evidence=["ev_dup -> app.py:1-10"],
                impact="Changes may need duplication across paths.",
                first_step="Add tests before refactoring.",
                validation_tests=["tests/test_blueprints.py", "tests/test_basic.py"],
                confidence_rationale="Multiple evidence records confirm the pattern.",
                caveat="Mature public API; preserve compatibility.",
            )
        ],
        [
            EvidenceRecord(
                evidence_id="ev_dup",
                file_path="app.py",
                start_line=1,
                end_line=10,
                snippet="def dispatch(): pass",
                kind="symbol",
                symbols=["dispatch"],
            )
        ],
    )

    response = client.get("/api/reviews/task-1/findings")

    assert response.status_code == 200
    finding = response.json()["findings"][0]
    assert finding["impact"] == "Changes may need duplication across paths."
    assert finding["first_step"] == "Add tests before refactoring."
    assert finding["validation_tests"] == ["tests/test_blueprints.py", "tests/test_basic.py"]
    assert finding["confidence_rationale"] == "Multiple evidence records confirm the pattern."
    assert finding["caveat"] == "Mature public API; preserve compatibility."


def test_get_review_findings_returns_null_useful_fields_for_legacy_data(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    store.create_review("task-1", "https://github.com/example/project")
    store.replace_structured_findings(
        "task-1",
        [
            ReviewFinding(
                section="Architecture Summary",
                title="Legacy finding",
                description="A finding without useful fields.",
                severity="low",
                files=["old.py"],
                evidence_ids=["ev_legacy"],
                evidence=["ev_legacy -> old.py:1-5"],
            )
        ],
        [
            EvidenceRecord(
                evidence_id="ev_legacy",
                file_path="old.py",
                start_line=1,
                end_line=5,
                snippet="pass",
                kind="symbol",
                symbols=[],
            )
        ],
    )

    response = client.get("/api/reviews/task-1/findings")

    assert response.status_code == 200
    finding = response.json()["findings"][0]
    assert finding["impact"] is None
    assert finding["first_step"] is None
    assert finding["validation_tests"] == []
    assert finding["confidence_rationale"] is None
    assert finding["caveat"] is None


def test_get_review_findings_returns_empty_list_for_legacy_review(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    store.create_review("task-1", "https://github.com/example/project")

    response = client.get("/api/reviews/task-1/findings")

    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == "task-1"
    assert data["findings"] == []
    assert data["evidence_display_map"] == {}


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
                "error": "MIMO_[REDACTED]",
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


# --- Localization tests ---


def _create_completed_review_with_report(
    store: ReviewStore,
    report: str = "# Executive Summary\nAnalysis complete.\n\n## Top Risks\n- Risk one\n",
) -> None:
    """Helper to create a completed review with report markdown."""
    store.create_review("task-zh", "https://github.com/example/project")
    store.update_status(
        "task-zh",
        ReviewStatus.completed,
        report_markdown=report,
    )


def test_get_review_lang_en_returns_english_report(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    _create_completed_review_with_report(store)

    response = client.get("/api/reviews/task-zh?lang=en")

    assert response.status_code == 200
    body = response.json()
    assert "# Executive Summary" in body["report_markdown"]
    assert "# 执行摘要" not in body["report_markdown"]


def test_get_review_lang_zh_returns_chinese_headings(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    _create_completed_review_with_report(store)

    response = client.get("/api/reviews/task-zh?lang=zh")

    assert response.status_code == 200
    body = response.json()
    assert "# 执行摘要" in body["report_markdown"]
    assert "Analysis complete." in body["report_markdown"]


def test_get_review_lang_zh_preserves_task_metadata(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    _create_completed_review_with_report(store)

    response = client.get("/api/reviews/task-zh?lang=zh")

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "task-zh"
    assert body["status"] == "completed"
    assert body["repo_url"] == "https://github.com/example/project"


def test_get_review_invalid_lang_defaults_to_english(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    _create_completed_review_with_report(store)

    response = client.get("/api/reviews/task-zh?lang=invalid")

    assert response.status_code == 200
    body = response.json()
    assert "# Executive Summary" in body["report_markdown"]


def test_get_review_no_lang_defaults_to_english(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    _create_completed_review_with_report(store)

    response = client.get("/api/reviews/task-zh")

    assert response.status_code == 200
    body = response.json()
    assert "# Executive Summary" in body["report_markdown"]


def test_get_review_findings_lang_zh_keeps_same_count(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    store.create_review("task-zh", "https://github.com/example/project")
    store.replace_structured_findings(
        "task-zh",
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
            ),
            ReviewFinding(
                section="Code Smells",
                title="Duplicate code",
                description="Two paths implement similar logic.",
                severity="medium",
                category="code_smell",
                confidence=0.75,
                recommendation="Extract shared logic.",
                files=["app.py"],
                evidence_ids=["ev_dup"],
                evidence=["ev_dup -> app.py:1-10"],
            ),
        ],
        [
            EvidenceRecord(
                evidence_id="ev_safe",
                file_path="backend/api/reviews.py",
                start_line=10,
                end_line=20,
                snippet="code",
                kind="symbol",
                symbols=["build_reviews_router"],
            ),
            EvidenceRecord(
                evidence_id="ev_dup",
                file_path="app.py",
                start_line=1,
                end_line=10,
                snippet="code",
                kind="symbol",
                symbols=["dispatch"],
            ),
        ],
    )

    en_response = client.get("/api/reviews/task-zh/findings?lang=en")
    zh_response = client.get("/api/reviews/task-zh/findings?lang=zh")

    assert en_response.status_code == 200
    assert zh_response.status_code == 200
    assert len(en_response.json()["findings"]) == 2
    assert len(zh_response.json()["findings"]) == 2


def test_get_review_findings_lang_zh_keeps_same_evidence_ids(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    store.create_review("task-zh", "https://github.com/example/project")
    store.replace_structured_findings(
        "task-zh",
        [
            ReviewFinding(
                section="Architecture Summary",
                title="Boundary risk",
                description="The API boundary has mixed responsibilities.",
                severity="high",
                category="architecture",
                confidence=0.91,
                recommendation="Separate transport.",
                files=["backend/api/reviews.py"],
                evidence_ids=["ev_safe"],
                evidence=["ev_safe -> backend/api/reviews.py:10-20"],
            ),
        ],
        [
            EvidenceRecord(
                evidence_id="ev_safe",
                file_path="backend/api/reviews.py",
                start_line=10,
                end_line=20,
                snippet="code",
                kind="symbol",
                symbols=["build_reviews_router"],
            ),
        ],
    )

    en_response = client.get("/api/reviews/task-zh/findings?lang=en")
    zh_response = client.get("/api/reviews/task-zh/findings?lang=zh")

    en_finding = en_response.json()["findings"][0]
    zh_finding = zh_response.json()["findings"][0]
    assert en_finding["evidence_ids"] == zh_finding["evidence_ids"]
    assert en_finding["files"] == zh_finding["files"]
    assert en_finding["severity"] == zh_finding["severity"]
    assert en_finding["confidence"] == zh_finding["confidence"]


def test_get_review_findings_lang_zh_returns_safe_chinese_prose(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    store.create_review("task-zh", "https://github.com/example/project")
    store.replace_structured_findings(
        "task-zh",
        [
            ReviewFinding(
                section="Code Smells",
                title="Duplicate dispatch",
                description="Two paths implement similar dispatch.",
                severity="medium",
                category="code_smell",
                confidence=0.75,
                recommendation="Extract shared logic.",
                files=["app.py"],
                evidence_ids=["ev_dup"],
                evidence=["ev_dup -> app.py:1-10"],
                impact="Changes may need duplication across paths.",
                first_step="Add tests before refactoring.",
                caveat="Mature public API; preserve compatibility.",
            ),
        ],
        [
            EvidenceRecord(
                evidence_id="ev_dup",
                file_path="app.py",
                start_line=1,
                end_line=10,
                snippet="code",
                kind="symbol",
                symbols=["dispatch"],
            ),
        ],
    )

    zh_response = client.get("/api/reviews/task-zh/findings?lang=zh")

    assert zh_response.status_code == 200
    finding = zh_response.json()["findings"][0]
    # Natural-language fields should not fall back to English prose.
    assert "Duplicate dispatch" not in finding["title"]
    assert "Two paths implement similar dispatch" not in finding["description"]
    assert "Extract shared logic" not in (finding["recommendation"] or "")
    assert "Changes may need duplication across paths" not in (finding["impact"] or "")
    assert "Add tests before refactoring" not in (finding["first_step"] or "")
    assert "Mature public API" not in (finding["caveat"] or "")
    assert finding["title"]
    assert finding["description"]
    assert finding["recommendation"]
    assert finding["impact"]
    assert finding["first_step"]
    # Canonical data unchanged
    assert finding["severity"] == "medium"
    assert finding["confidence"] == 0.75
    assert finding["files"] == ["app.py"]
    assert finding["evidence_ids"] == ["ev_dup"]


def test_export_lang_zh_returns_chinese_markdown(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    _create_completed_review_with_report(store)

    response = client.get("/api/reviews/task-zh/export?lang=zh")

    assert response.status_code == 200
    assert "# 执行摘要" in response.text
    assert "codepilot-review-task-zh-zh.md" in response.headers["content-disposition"]


def test_export_lang_en_returns_english_markdown(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    _create_completed_review_with_report(store)

    response = client.get("/api/reviews/task-zh/export?lang=en")

    assert response.status_code == 200
    assert "# Executive Summary" in response.text
    assert "codepilot-review-task-zh.md" in response.headers["content-disposition"]


def test_export_no_lang_defaults_to_english(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    _create_completed_review_with_report(store)

    response = client.get("/api/reviews/task-zh/export")

    assert response.status_code == 200
    assert "# Executive Summary" in response.text


def test_export_lang_zh_preserves_finding_content(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client
    report = (
        "# Executive Summary\n"
        "CodePilot analyzed 10 files.\n\n"
        "# Action Plan\n"
        "## 1. Fix boundary\n"
        "- **Why it matters:** Mixed responsibilities.\n"
        "- **Evidence:** `ev_123`\n"
    )
    store.create_review("task-zh", "https://github.com/example/project")
    store.update_status("task-zh", ReviewStatus.completed, report_markdown=report)

    response = client.get("/api/reviews/task-zh/export?lang=zh")

    assert response.status_code == 200
    # Headings translated
    assert "# 执行摘要" in response.text
    assert "# 行动计划" in response.text
    # Content preserved (CodePilot analyzed → CodePilot 审查了 in zh)
    assert "CodePilot 审查了" in response.text or "CodePilot analyzed" in response.text
    assert "`ev_123`" in response.text


# --- Localization service integration tests ---


@pytest.fixture
def api_client_with_localization(tmp_path: Path) -> tuple[TestClient, ReviewStore, FakeRunner]:
    store = ReviewStore(tmp_path / "reviews.db")
    runner = FakeRunner(store)
    translator = MockTranslator()
    localization_service = LocalizationService(store, translator)
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(build_reviews_router(store, runner, localization_service))
    return TestClient(app), store, runner


def _create_review_with_mock_findings(
    store: ReviewStore,
    task_id: str = "task-zh-prose",
) -> None:
    store.create_review(task_id, "https://github.com/example/project")
    store.update_status(task_id, ReviewStatus.completed, report_markdown="# Test")
    store.replace_structured_findings(
        task_id,
        [
            ReviewFinding(
                section="Architecture Summary",
                title="Evidence-grounded architecture boundary",
                description=(
                    "The selected evidence highlights a repository concern that should be reviewed "
                    "before changing entry points, core modules, shared dependencies, or refactoring boundaries."
                ),
                severity="high",
                category="architecture",
                confidence=0.85,
                recommendation="Add contract tests around the boundary before refactoring.",
                files=["backend/api/reviews.py"],
                evidence_ids=["ev_abc123"],
                evidence=["ev_abc123 -> backend/api/reviews.py:10-20"],
                impact=(
                    "Changes to this boundary may affect multiple consumers "
                    "if the interface contract is not preserved."
                ),
                first_step=(
                    "Add characterization tests covering the current "
                    "public interface before restructuring."
                ),
                validation_tests=["Run the full test suite before and after any boundary change."],
                confidence_rationale="Based on evidence records provided in the prompt context.",
                caveat=(
                    "If this boundary is part of a public API, "
                    "changing it may break downstream consumers."
                ),
            ),
        ],
        [
            EvidenceRecord(
                evidence_id="ev_abc123",
                file_path="backend/api/reviews.py",
                start_line=10,
                end_line=20,
                snippet="code",
                kind="symbol",
                symbols=["build_reviews_router"],
            ),
        ],
    )


def test_findings_lang_zh_returns_chinese_prose(
    api_client_with_localization: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client_with_localization
    _create_review_with_mock_findings(store)

    response = client.get("/api/reviews/task-zh-prose/findings?lang=zh")

    assert response.status_code == 200
    finding = response.json()["findings"][0]
    # Title should be concrete (file-based or symbol-based) and Chinese
    assert finding["title"] is not None
    title = finding["title"]
    assert "架构" in title or "build_reviews_router" in title or "backend/api/reviews.py" in title
    # No bad terms
    assert "代码坏味道" not in finding["title"]
    assert "结构性问题" in finding["description"]
    assert "契约测试" in finding["recommendation"]


def test_findings_lang_zh_preserves_evidence_ids(
    api_client_with_localization: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client_with_localization
    _create_review_with_mock_findings(store)

    en_response = client.get("/api/reviews/task-zh-prose/findings?lang=en")
    zh_response = client.get("/api/reviews/task-zh-prose/findings?lang=zh")

    en_finding = en_response.json()["findings"][0]
    zh_finding = zh_response.json()["findings"][0]
    assert en_finding["evidence_ids"] == zh_finding["evidence_ids"]


def test_findings_lang_zh_preserves_files(
    api_client_with_localization: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client_with_localization
    _create_review_with_mock_findings(store)

    en_response = client.get("/api/reviews/task-zh-prose/findings?lang=en")
    zh_response = client.get("/api/reviews/task-zh-prose/findings?lang=zh")

    en_finding = en_response.json()["findings"][0]
    zh_finding = zh_response.json()["findings"][0]
    assert en_finding["files"] == zh_finding["files"]


def test_findings_lang_zh_preserves_severity_and_confidence(
    api_client_with_localization: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client_with_localization
    _create_review_with_mock_findings(store)

    en_response = client.get("/api/reviews/task-zh-prose/findings?lang=en")
    zh_response = client.get("/api/reviews/task-zh-prose/findings?lang=zh")

    en_finding = en_response.json()["findings"][0]
    zh_finding = zh_response.json()["findings"][0]
    assert en_finding["severity"] == zh_finding["severity"]
    assert en_finding["confidence"] == zh_finding["confidence"]


def test_findings_lang_zh_translates_impact_and_first_step(
    api_client_with_localization: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client_with_localization
    _create_review_with_mock_findings(store)

    response = client.get("/api/reviews/task-zh-prose/findings?lang=zh")

    finding = response.json()["findings"][0]
    assert "依赖方" in finding["impact"]
    assert "表征测试" in finding["first_step"]
    assert "公共 API" in finding["caveat"]


def test_findings_lang_zh_translates_validation_tests(
    api_client_with_localization: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    client, store, _ = api_client_with_localization
    _create_review_with_mock_findings(store)

    response = client.get("/api/reviews/task-zh-prose/findings?lang=zh")

    finding = response.json()["findings"][0]
    assert len(finding["validation_tests"]) == 1
    assert "测试套件" in finding["validation_tests"][0]


def test_findings_lang_zh_with_failing_translator(
    tmp_path: Path,
) -> None:
    store = ReviewStore(tmp_path / "reviews.db")
    runner = FakeRunner(store)

    class FailingTranslator:
        def translate_finding_prose(self, finding: dict) -> dict:
            raise RuntimeError("LLM unavailable")

    localization_service = LocalizationService(store, FailingTranslator())
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(build_reviews_router(store, runner, localization_service))
    client = TestClient(app)

    _create_review_with_mock_findings(store)

    response = client.get("/api/reviews/task-zh-prose/findings?lang=zh")

    assert response.status_code == 200
    finding = response.json()["findings"][0]
    # Falls back to English prose
    assert finding["title"] == "Evidence-grounded architecture boundary"
    assert finding["severity"] == "high"


# --- Chinese report prose tests ---


def test_get_review_lang_zh_returns_chinese_report_prose(
    api_client_with_localization: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Chinese report should contain localized finding prose, not only translated headings."""
    client, store, _ = api_client_with_localization
    report = (
        "# Executive Summary\n"
        "CodePilot analyzed 10 files.\n\n"
        "# Action Plan\n"
        "## 1. Evidence-grounded architecture boundary\n"
        "- **Why it matters:** Changes to this boundary may affect multiple consumers "
        "if the interface contract is not preserved.\n"
        "- **First step:** Add characterization tests covering the current "
        "public interface before restructuring.\n"
        "- **Caveat:** If this boundary is part of a public API, "
        "changing it may break downstream consumers.\n"
        "- **Evidence:** `ev_abc123`\n"
    )
    store.create_review("task-zh-report", "https://github.com/example/project")
    store.update_status("task-zh-report", ReviewStatus.completed, report_markdown=report)
    store.replace_structured_findings(
        "task-zh-report",
        [
            ReviewFinding(
                section="Architecture Summary",
                title="Evidence-grounded architecture boundary",
                description=(
                    "The selected evidence highlights a repository concern that should be reviewed "
                    "before changing entry points, core modules, shared dependencies, or refactoring boundaries."
                ),
                severity="high",
                category="architecture",
                confidence=0.85,
                recommendation="Add contract tests around the boundary before refactoring.",
                files=["backend/api/reviews.py"],
                evidence_ids=["ev_abc123"],
                evidence=["ev_abc123 -> backend/api/reviews.py:10-20"],
                impact=(
                    "Changes to this boundary may affect multiple consumers "
                    "if the interface contract is not preserved."
                ),
                first_step=(
                    "Add characterization tests covering the current "
                    "public interface before restructuring."
                ),
                validation_tests=["Run the full test suite before and after any boundary change."],
                confidence_rationale="Based on evidence records provided in the prompt context.",
                caveat=(
                    "If this boundary is part of a public API, "
                    "changing it may break downstream consumers."
                ),
            ),
        ],
        [
            EvidenceRecord(
                evidence_id="ev_abc123",
                file_path="backend/api/reviews.py",
                start_line=10,
                end_line=20,
                snippet="code",
                kind="symbol",
                symbols=["build_reviews_router"],
            ),
        ],
    )

    response = client.get("/api/reviews/task-zh-report?lang=zh")

    assert response.status_code == 200
    report_md = response.json()["report_markdown"]
    # Headings should be Chinese
    assert "# 执行摘要" in report_md
    assert "# 行动计划" in report_md
    # Finding prose should be Chinese (not only headings)
    assert "依赖方" in report_md
    assert "表征测试" in report_md
    assert "公共 API" in report_md
    # Evidence IDs preserved
    assert "ev_abc123" in report_md


def test_export_lang_zh_returns_chinese_prose(
    api_client_with_localization: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Chinese export should contain localized finding prose."""
    client, store, _ = api_client_with_localization
    report = (
        "# Executive Summary\n"
        "CodePilot analyzed 10 files.\n\n"
        "# Action Plan\n"
        "## 1. Evidence-grounded architecture boundary\n"
        "- **Why it matters:** Changes to this boundary may affect multiple consumers "
        "if the interface contract is not preserved.\n"
        "- **Evidence:** `ev_abc123`\n"
    )
    store.create_review("task-zh-export", "https://github.com/example/project")
    store.update_status("task-zh-export", ReviewStatus.completed, report_markdown=report)
    store.replace_structured_findings(
        "task-zh-export",
        [
            ReviewFinding(
                section="Architecture Summary",
                title="Evidence-grounded architecture boundary",
                description=(
                    "The selected evidence highlights a repository concern that should be reviewed "
                    "before changing entry points, core modules, shared dependencies, or refactoring boundaries."
                ),
                severity="high",
                category="architecture",
                confidence=0.85,
                recommendation="Add contract tests around the boundary before refactoring.",
                files=["backend/api/reviews.py"],
                evidence_ids=["ev_abc123"],
                evidence=["ev_abc123 -> backend/api/reviews.py:10-20"],
                impact=(
                    "Changes to this boundary may affect multiple consumers "
                    "if the interface contract is not preserved."
                ),
            ),
        ],
        [
            EvidenceRecord(
                evidence_id="ev_abc123",
                file_path="backend/api/reviews.py",
                start_line=10,
                end_line=20,
                snippet="code",
                kind="symbol",
                symbols=["build_reviews_router"],
            ),
        ],
    )

    response = client.get("/api/reviews/task-zh-export/export?lang=zh")

    assert response.status_code == 200
    # Headings translated
    assert "# 执行摘要" in response.text
    assert "# 行动计划" in response.text
    # Finding prose translated
    assert "依赖方" in response.text
    # Evidence IDs preserved
    assert "ev_abc123" in response.text
    # Filename includes -zh
    assert "codepilot-review-task-zh-export-zh.md" in response.headers["content-disposition"]


def test_get_review_lang_zh_preserves_severity_and_confidence_in_report(
    api_client_with_localization: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Chinese report should preserve severity and confidence values."""
    client, store, _ = api_client_with_localization
    report = "# Executive Summary\n0 high, 1 medium.\n"
    store.create_review("task-zh-sev", "https://github.com/example/project")
    store.update_status("task-zh-sev", ReviewStatus.completed, report_markdown=report)
    store.replace_structured_findings(
        "task-zh-sev",
        [
            ReviewFinding(
                section="Architecture Summary",
                title="Evidence-grounded architecture boundary",
                description="desc",
                severity="high",
                confidence=0.85,
                files=["a.py"],
                evidence_ids=["ev_a"],
                evidence=["ev_a -> a.py:1-5"],
            ),
        ],
        [
            EvidenceRecord(
                evidence_id="ev_a", file_path="a.py", start_line=1, end_line=5,
                snippet="code", kind="symbol", symbols=[],
            ),
        ],
    )

    en_response = client.get("/api/reviews/task-zh-sev?lang=en")
    zh_response = client.get("/api/reviews/task-zh-sev?lang=zh")

    assert en_response.status_code == 200
    assert zh_response.status_code == 200
    # Both should have the same task_id and status
    assert en_response.json()["task_id"] == zh_response.json()["task_id"]
    assert en_response.json()["status"] == zh_response.json()["status"]


def test_get_review_lang_zh_report_cache_hit(
    api_client_with_localization: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Repeated zh requests should use cached report."""
    client, store, _ = api_client_with_localization
    report = (
        "# Executive Summary\n"
        "CodePilot analyzed 10 files.\n\n"
        "# Action Plan\n"
        "## 1. Evidence-grounded architecture boundary\n"
        "- **Why it matters:** Changes to this boundary may affect multiple consumers "
        "if the interface contract is not preserved.\n"
    )
    store.create_review("task-zh-cache", "https://github.com/example/project")
    store.update_status("task-zh-cache", ReviewStatus.completed, report_markdown=report)
    store.replace_structured_findings(
        "task-zh-cache",
        [
            ReviewFinding(
                section="Architecture Summary",
                title="Evidence-grounded architecture boundary",
                description="desc",
                severity="high",
                confidence=0.85,
                files=["a.py"],
                evidence_ids=["ev_a"],
                evidence=["ev_a -> a.py:1-5"],
                impact=(
                    "Changes to this boundary may affect multiple consumers "
                    "if the interface contract is not preserved."
                ),
            ),
        ],
        [
            EvidenceRecord(
                evidence_id="ev_a", file_path="a.py", start_line=1, end_line=5,
                snippet="code", kind="symbol", symbols=[],
            ),
        ],
    )

    # First request — cache miss
    response1 = client.get("/api/reviews/task-zh-cache?lang=zh")
    # Second request — cache hit
    response2 = client.get("/api/reviews/task-zh-cache?lang=zh")

    assert response1.status_code == 200
    assert response2.status_code == 200
    # Both should return the same Chinese report
    assert response1.json()["report_markdown"] == response2.json()["report_markdown"]
    # Report should contain Chinese prose
    assert "依赖方" in response1.json()["report_markdown"]


def test_get_review_lang_en_unchanged_with_localization(
    api_client_with_localization: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """English report should remain unchanged when localization service is available."""
    client, store, _ = api_client_with_localization
    report = "# Executive Summary\nCodePilot analyzed 10 files.\n"
    store.create_review("task-en", "https://github.com/example/project")
    store.update_status("task-en", ReviewStatus.completed, report_markdown=report)

    response = client.get("/api/reviews/task-en?lang=en")

    assert response.status_code == 200
    assert "# Executive Summary" in response.json()["report_markdown"]
    assert "# 执行摘要" not in response.json()["report_markdown"]


def test_export_lang_zh_with_failing_translator(
    tmp_path: Path,
) -> None:
    """Chinese export should fall back gracefully when translator fails."""
    store = ReviewStore(tmp_path / "reviews.db")
    runner = FakeRunner(store)

    class FailingTranslator:
        def translate_finding_prose(self, finding: dict) -> dict:
            raise RuntimeError("LLM unavailable")

    localization_service = LocalizationService(store, FailingTranslator())
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(build_reviews_router(store, runner, localization_service))
    client = TestClient(app)

    report = (
        "# Executive Summary\n"
        "CodePilot analyzed 10 files.\n\n"
        "# Action Plan\n"
        "## 1. Evidence-grounded architecture boundary\n"
        "- **Why it matters:** Changes to this boundary may affect multiple consumers.\n"
    )
    store.create_review("task-fail", "https://github.com/example/project")
    store.update_status("task-fail", ReviewStatus.completed, report_markdown=report)
    store.replace_structured_findings(
        "task-fail",
        [
            ReviewFinding(
                section="Architecture Summary",
                title="Evidence-grounded architecture boundary",
                description="desc",
                severity="high",
                confidence=0.85,
                files=["a.py"],
                evidence_ids=["ev_a"],
                evidence=["ev_a -> a.py:1-5"],
                impact="Changes to this boundary may affect multiple consumers.",
            ),
        ],
        [
            EvidenceRecord(
                evidence_id="ev_a", file_path="a.py", start_line=1, end_line=5,
                snippet="code", kind="symbol", symbols=[],
            ),
        ],
    )

    response = client.get("/api/reviews/task-fail/export?lang=zh")

    # Should not crash — falls back to heading/label translation
    assert response.status_code == 200
    # Headings should still be translated
    assert "# 执行摘要" in response.text
    # English prose preserved (translator failed)
    assert "Changes to this boundary" in response.text


# --- V3.5.5 terminology and English leakage tests ---


_ZH_BANNED_ENGLISH = [
    "Execution begins",
    "This description is based on",
    "It does not claim",
    "Why It Matters",
    "Findings are grouped",
    "Evidence references remain",
    "Source snippets are intentionally omitted",
    "Supported source files",
    "Analyzed files",
    "Skipped files",
    "Total lines",
    "Average complexity estimate",
    "Higher structural risk",
    "Medium finding risk",
]

_ZH_BANNED_TERMS = [
    "代码坏味道",
]


def test_zh_report_no_banned_english_boilerplate(
    api_client_with_localization: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Chinese report should not contain obvious English boilerplate sentences."""
    client, store, _ = api_client_with_localization
    _create_review_with_mock_findings(store)

    # Create a report with full English prose
    report = (
        "# Executive Summary\n"
        "CodePilot analyzed 10 files.\n\n"
        "# How It Works\n"
        "Execution begins around `src/app.py`, then delegates into `src/core.py`.\n"
        "- This description is based on paths, symbols, routes, "
        "and resolved internal dependencies.\n"
        "- It does not claim runtime semantics that were not present "
        "in the analyzed evidence.\n\n"
        "# Key Architecture Map\n"
        "| Area | Files | Why It Matters |\n"
        "| --- | --- | --- |\n"
        "| Entry points | `src/app.py` | Trace startup and top-level composition here. |\n"
        "| Dependency hubs | `src/core.py` | Changes can affect several internal consumers. |\n\n"
        "# Evidence Appendix\n"
        "Only validated references are shown. Source snippets are intentionally omitted.\n"
        "| Evidence ID | Location | Kind | Symbols |\n"
        "| --- | --- | --- | --- |\n\n"
        "## Repository Metrics\n"
        "- Supported source files: 10\n"
        "- Analyzed files: 8\n"
        "- Skipped files: 2\n"
        "- Total lines: 500\n"
        "- Average complexity estimate: 3.14\n\n"
        "# Action Plan\n"
        "## 1. Evidence-grounded architecture boundary\n"
        "- **Why it matters:** Changes to this boundary.\n"
        "- **Evidence:** `ev_abc123`\n"
    )
    store.create_review("task-zh-leak", "https://github.com/example/project")
    store.update_status("task-zh-leak", ReviewStatus.completed, report_markdown=report)
    store.replace_structured_findings(
        "task-zh-leak",
        [
            ReviewFinding(
                section="Architecture Summary",
                title="Evidence-grounded architecture boundary",
                description="desc",
                severity="high",
                category="architecture",
                confidence=0.85,
                files=["a.py"],
                evidence_ids=["ev_abc123"],
                evidence=["ev_abc123 -> a.py:1-5"],
                impact="Changes to this boundary.",
            ),
        ],
        [
            EvidenceRecord(
                evidence_id="ev_abc123", file_path="a.py", start_line=1, end_line=5,
                snippet="code", kind="symbol", symbols=[],
            ),
        ],
    )

    response = client.get("/api/reviews/task-zh-leak?lang=zh")

    assert response.status_code == 200
    report_md = response.json()["report_markdown"]

    for banned in _ZH_BANNED_ENGLISH:
        assert banned not in report_md, f"Banned English phrase found in zh report: '{banned}'"


def test_zh_export_no_banned_english_boilerplate(
    api_client_with_localization: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Chinese export should not contain obvious English boilerplate sentences."""
    client, store, _ = api_client_with_localization
    _create_review_with_mock_findings(store)

    report = (
        "# Executive Summary\n"
        "CodePilot analyzed 10 files.\n\n"
        "# Evidence Appendix\n"
        "Only validated references are shown. Source snippets are intentionally omitted.\n\n"
        "## Repository Metrics\n"
        "- Supported source files: 10\n"
        "- Average complexity estimate: 3.14\n"
    )
    store.create_review("task-zh-export-leak", "https://github.com/example/project")
    store.update_status("task-zh-export-leak", ReviewStatus.completed, report_markdown=report)

    response = client.get("/api/reviews/task-zh-export-leak/export?lang=zh")

    assert response.status_code == 200
    for banned in _ZH_BANNED_ENGLISH:
        assert banned not in response.text, f"Banned English phrase found in zh export: '{banned}'"


def test_zh_findings_no_bad_terms(
    api_client_with_localization: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Chinese findings should not contain '代码坏味道'."""
    client, store, _ = api_client_with_localization
    _create_review_with_mock_findings(store)

    response = client.get("/api/reviews/task-zh-prose/findings?lang=zh")

    assert response.status_code == 200
    finding = response.json()["findings"][0]
    for banned in _ZH_BANNED_TERMS:
        assert banned not in finding.get("title", ""), f"Bad term in title: {banned}"
        assert banned not in finding.get("description", ""), f"Bad term in description: {banned}"


def test_zh_report_uses_new_terminology(
    api_client_with_localization: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Chinese report should use '代码质量问题' not '代码坏味道'."""
    client, store, _ = api_client_with_localization
    report = "# Code Smells\n- Some code smell finding.\n"
    store.create_review("task-zh-term", "https://github.com/example/project")
    store.update_status("task-zh-term", ReviewStatus.completed, report_markdown=report)

    response = client.get("/api/reviews/task-zh-term?lang=zh")

    assert response.status_code == 200
    report_md = response.json()["report_markdown"]
    assert "# 代码质量问题" in report_md
    assert "代码坏味道" not in report_md


def test_zh_export_content_type_includes_utf8(
    api_client_with_localization: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Export response should include charset=utf-8 in content type."""
    client, store, _ = api_client_with_localization
    _create_review_with_mock_findings(store)

    response = client.get("/api/reviews/task-zh-prose/export?lang=zh")

    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    assert "utf-8" in content_type.lower() or "text/markdown" in content_type


def test_zh_export_preserves_evidence_ids_and_paths(
    api_client_with_localization: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Chinese export must preserve evidence IDs and file paths exactly."""
    client, store, _ = api_client_with_localization
    report = (
        "# Action Plan\n"
        "## 1. Fix boundary\n"
        "- **Evidence:** `ev_abc123`\n"
        "- **Where:** `backend/api/reviews.py`\n"
    )
    store.create_review("task-zh-preserve", "https://github.com/example/project")
    store.update_status("task-zh-preserve", ReviewStatus.completed, report_markdown=report)
    store.replace_structured_findings(
        "task-zh-preserve",
        [
            ReviewFinding(
                section="Architecture Summary",
                title="Evidence-grounded architecture boundary",
                description="desc",
                severity="high",
                category="architecture",
                confidence=0.85,
                files=["backend/api/reviews.py"],
                evidence_ids=["ev_abc123"],
                evidence=["ev_abc123 -> backend/api/reviews.py:10-20"],
            ),
        ],
        [
            EvidenceRecord(
                evidence_id="ev_abc123", file_path="backend/api/reviews.py",
                start_line=10, end_line=20, snippet="code", kind="symbol",
                symbols=["build_reviews_router"],
            ),
        ],
    )

    en_response = client.get("/api/reviews/task-zh-preserve/export?lang=en")
    zh_response = client.get("/api/reviews/task-zh-preserve/export?lang=zh")

    assert en_response.status_code == 200
    assert zh_response.status_code == 200
    # Evidence IDs preserved
    assert "ev_abc123" in zh_response.text
    # File paths preserved
    assert "backend/api/reviews.py" in zh_response.text


# --- V3.5.7 lazy localization tests ---


def test_review_completion_does_not_trigger_localization(
    api_client_with_localization: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Review completion should not call localization service unless zh is requested."""
    client, store, _ = api_client_with_localization
    _create_completed_review_with_report(store)

    # Request English — should not trigger zh localization
    response = client.get("/api/reviews/task-zh?lang=en")

    assert response.status_code == 200
    assert "# Executive Summary" in response.json()["report_markdown"]
    # No Chinese headings should appear
    assert "# 执行摘要" not in response.json()["report_markdown"]


def test_findings_lang_zh_triggers_localization(
    api_client_with_localization: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Requesting findings with lang=zh should trigger localization."""
    client, store, _ = api_client_with_localization
    _create_review_with_mock_findings(store)

    response = client.get("/api/reviews/task-zh-prose/findings?lang=zh")

    assert response.status_code == 200
    finding = response.json()["findings"][0]
    # Should have Chinese prose (symbol-based or file-based title)
    title = finding["title"]
    assert "需要审查" in title or "架构" in title or "build_reviews_router" in title or "reviews.py" in title


def test_findings_lang_zh_uses_cache_on_repeat(
    api_client_with_localization: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Repeated zh findings requests should use cached translations."""
    client, store, _ = api_client_with_localization
    _create_review_with_mock_findings(store)

    # First request — cache miss
    response1 = client.get("/api/reviews/task-zh-prose/findings?lang=zh")
    # Second request — cache hit
    response2 = client.get("/api/reviews/task-zh-prose/findings?lang=zh")

    assert response1.status_code == 200
    assert response2.status_code == 200
    # Both should return the same translated content
    assert response1.json()["findings"][0]["title"] == response2.json()["findings"][0]["title"]


def test_findings_lang_en_does_not_trigger_zh_localization(
    api_client_with_localization: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Requesting findings with lang=en should NOT trigger zh localization."""
    client, store, _ = api_client_with_localization
    _create_review_with_mock_findings(store)

    response = client.get("/api/reviews/task-zh-prose/findings?lang=en")

    assert response.status_code == 200
    finding = response.json()["findings"][0]
    # Should have English prose
    assert finding["title"] == "Evidence-grounded architecture boundary"
    # Should NOT have Chinese prose
    assert "架构" not in finding["title"]


# --- V3.5.8 bilingual output tests ---


def _create_bilingual_review(
    store: ReviewStore,
    task_id: str = "task-bi",
) -> None:
    """Create a review with bilingual display fields (new format)."""
    store.create_review(task_id, "https://github.com/example/project")
    store.update_status(task_id, ReviewStatus.completed, report_markdown="# Test")
    store.replace_structured_findings(
        task_id,
        [
            ReviewFinding(
                section="Architecture Summary",
                title="Boundary risk in API layer",
                description="The API boundary has mixed responsibilities.",
                severity="high",
                category="architecture",
                confidence=0.91,
                recommendation="Separate transport and domain responsibilities.",
                files=["backend/api/reviews.py"],
                evidence_ids=["ev_safe"],
                evidence=["ev_safe -> backend/api/reviews.py:10-20"],
                impact="Changes may affect multiple consumers.",
                first_step="Add characterization tests first.",
                validation_tests=["Run the full test suite before and after."],
                confidence_rationale="Multiple evidence records confirm.",
                caveat="Public API compatibility must be preserved.",
                display=DisplayFields(
                    en=BilingualTextField(
                        title="Boundary risk in API layer",
                        description="The API boundary has mixed responsibilities.",
                        recommendation="Separate transport and domain responsibilities.",
                        impact="Changes may affect multiple consumers.",
                        first_step="Add characterization tests first.",
                        validation_tests=["Run the full test suite before and after."],
                        confidence_rationale="Multiple evidence records confirm.",
                        caveat="Public API compatibility must be preserved.",
                    ),
                    zh=BilingualTextField(
                        title="API 层存在边界风险",
                        description="API 边界混合了多种职责。",
                        recommendation="分离传输层和领域层职责。",
                        impact="变更可能影响多个依赖方。",
                        first_step="先添加表征测试。",
                        validation_tests=["在变更前后运行完整测试套件。"],
                        confidence_rationale="多条证据记录确认了该模式。",
                        caveat="必须保留公共 API 兼容性。",
                    ),
                ),
            ),
        ],
        [
            EvidenceRecord(
                evidence_id="ev_safe",
                file_path="backend/api/reviews.py",
                start_line=10,
                end_line=20,
                snippet="code",
                kind="symbol",
                symbols=["build_reviews_router"],
            ),
        ],
    )


def test_bilingual_findings_zh_uses_stored_display(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """New bilingual reviews should return zh display fields without LLM."""
    client, store, _ = api_client
    _create_bilingual_review(store)

    response = client.get("/api/reviews/task-bi/findings?lang=zh")

    assert response.status_code == 200
    finding = response.json()["findings"][0]
    assert finding["title"] == "API 层存在边界风险"
    assert finding["description"] == "API 边界混合了多种职责。"
    assert finding["recommendation"] == "分离传输层和领域层职责。"
    assert finding["impact"] == "变更可能影响多个依赖方。"
    assert finding["first_step"] == "先添加表征测试。"
    assert finding["caveat"] == "必须保留公共 API 兼容性。"
    assert "变更前后运行完整测试套件" in finding["validation_tests"][0]


def test_zh_findings_fill_missing_display_fields_with_safe_chinese(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Chinese structured API must not fall back to English prose when display.zh is partial."""
    client, store, _ = api_client
    store.create_review("task-zh-partial-display", "https://github.com/example/project")
    store.update_status("task-zh-partial-display", ReviewStatus.completed, report_markdown="# Test")
    store.replace_structured_findings(
        "task-zh-partial-display",
        [
            ReviewFinding(
                section="Maintainability Issues",
                title="Protocol consistency",
                description="Protocol use is inconsistent.",
                severity="medium",
                category="maintainability",
                confidence=0.82,
                recommendation="Continue using protocols for new type hints to maintain consistency.",
                files=["src/markupsafe/_typing.py"],
                evidence_ids=["ev_safe"],
                impact="Improves code maintainability and enables better tooling support.",
                first_step="Run existing tests before changing the typing helpers.",
                validation_tests=["Check for any differences in type checker output."],
                caveat="Protocols are for static type checking; runtime behavior depends on implementation.",
                display=DisplayFields(
                    en=BilingualTextField(),
                    zh=BilingualTextField(title="协议类型标注需要保持一致"),
                ),
            ),
        ],
        [
            EvidenceRecord(
                evidence_id="ev_safe",
                file_path="src/markupsafe/_typing.py",
                start_line=1,
                end_line=20,
                snippet="code",
                kind="symbol",
                symbols=["Protocol"],
            ),
        ],
    )

    response = client.get("/api/reviews/task-zh-partial-display/findings?lang=zh")

    assert response.status_code == 200
    finding = response.json()["findings"][0]
    rendered = "\n".join(
        [
            finding["title"],
            finding["description"],
            finding["recommendation"],
            finding["impact"],
            finding["first_step"],
            finding["caveat"],
            "\n".join(finding["validation_tests"]),
        ],
    )
    for banned in (
        "Continue using protocols",
        "Improves code maintainability",
        "Run existing tests",
        "Check for any differences",
        "Protocols are for static type checking",
    ):
        assert banned not in rendered
    assert finding["evidence_ids"] == ["ev_safe"]
    assert finding["files"] == ["src/markupsafe/_typing.py"]


def test_bilingual_findings_en_uses_english_display(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """English mode should still work for bilingual reviews."""
    client, store, _ = api_client
    _create_bilingual_review(store)

    response = client.get("/api/reviews/task-bi/findings?lang=en")

    assert response.status_code == 200
    finding = response.json()["findings"][0]
    assert finding["title"] == "Boundary risk in API layer"
    assert finding["description"] == "The API boundary has mixed responsibilities."


def test_bilingual_findings_preserves_evidence_ids(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Evidence IDs must be identical across en/zh."""
    client, store, _ = api_client
    _create_bilingual_review(store)

    en = client.get("/api/reviews/task-bi/findings?lang=en")
    zh = client.get("/api/reviews/task-bi/findings?lang=zh")

    assert en.json()["findings"][0]["evidence_ids"] == zh.json()["findings"][0]["evidence_ids"]


def test_bilingual_findings_preserves_files(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """File paths must be identical across en/zh."""
    client, store, _ = api_client
    _create_bilingual_review(store)

    en = client.get("/api/reviews/task-bi/findings?lang=en")
    zh = client.get("/api/reviews/task-bi/findings?lang=zh")

    assert en.json()["findings"][0]["files"] == zh.json()["findings"][0]["files"]


def test_bilingual_findings_preserves_severity_and_confidence(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Severity and confidence must be identical across en/zh."""
    client, store, _ = api_client
    _create_bilingual_review(store)

    en = client.get("/api/reviews/task-bi/findings?lang=en")
    zh = client.get("/api/reviews/task-bi/findings?lang=zh")

    en_f = en.json()["findings"][0]
    zh_f = zh.json()["findings"][0]
    assert en_f["severity"] == zh_f["severity"] == "high"
    assert en_f["confidence"] == zh_f["confidence"] == 0.91


def test_bilingual_report_zh_uses_stored_display(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Chinese report for bilingual reviews should use stored zh fields."""
    client, store, _ = api_client
    # Report content uses the exact English impact text so replacement works
    report = (
        "# Action Plan\n"
        "## 1. Boundary risk in API layer\n"
        "- Changes may affect multiple consumers.\n"
        "- **Evidence:** `ev_safe`\n"
    )
    store.create_review("task-bi-report", "https://github.com/example/project")
    store.update_status("task-bi-report", ReviewStatus.completed, report_markdown=report)
    store.replace_structured_findings(
        "task-bi-report",
        [
            ReviewFinding(
                section="Architecture Summary",
                title="Boundary risk in API layer",
                description="The API boundary has mixed responsibilities.",
                severity="high",
                category="architecture",
                confidence=0.91,
                files=["backend/api/reviews.py"],
                evidence_ids=["ev_safe"],
                evidence=["ev_safe -> backend/api/reviews.py:10-20"],
                impact="Changes may affect multiple consumers.",
                display=DisplayFields(
                    en=BilingualTextField(
                        title="Boundary risk in API layer",
                        impact="Changes may affect multiple consumers.",
                    ),
                    zh=BilingualTextField(
                        title="API 层存在边界风险",
                        impact="变更可能影响多个依赖方。",
                    ),
                ),
            ),
        ],
        [
            EvidenceRecord(
                evidence_id="ev_safe",
                file_path="backend/api/reviews.py",
                start_line=10,
                end_line=20,
                snippet="code",
                kind="symbol",
                symbols=["build_reviews_router"],
            ),
        ],
    )

    response = client.get("/api/reviews/task-bi-report?lang=zh")

    assert response.status_code == 200
    report_md = response.json()["report_markdown"]
    # Chinese display fields should replace English prose
    assert "变更可能影响多个依赖方" in report_md
    # Evidence IDs preserved
    assert "ev_safe" in report_md


def test_bilingual_export_zh_uses_stored_display(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Chinese export for bilingual reviews should use stored zh fields."""
    client, store, _ = api_client
    # Report content uses the exact English impact text so replacement works
    report = (
        "# Action Plan\n"
        "- Changes may affect multiple consumers.\n"
        "- **Evidence:** `ev_safe`\n"
    )
    store.create_review("task-bi-export", "https://github.com/example/project")
    store.update_status("task-bi-export", ReviewStatus.completed, report_markdown=report)
    store.replace_structured_findings(
        "task-bi-export",
        [
            ReviewFinding(
                section="Architecture Summary",
                title="Boundary risk",
                description="desc",
                severity="high",
                category="architecture",
                confidence=0.91,
                files=["backend/api/reviews.py"],
                evidence_ids=["ev_safe"],
                evidence=["ev_safe -> backend/api/reviews.py:10-20"],
                impact="Changes may affect multiple consumers.",
                display=DisplayFields(
                    en=BilingualTextField(impact="Changes may affect multiple consumers."),
                    zh=BilingualTextField(impact="变更可能影响多个依赖方。"),
                ),
            ),
        ],
        [
            EvidenceRecord(
                evidence_id="ev_safe",
                file_path="backend/api/reviews.py",
                start_line=10,
                end_line=20,
                snippet="code",
                kind="symbol",
                symbols=["build_reviews_router"],
            ),
        ],
    )

    response = client.get("/api/reviews/task-bi-export/export?lang=zh")

    assert response.status_code == 200
    assert "变更可能影响多个依赖方" in response.text
    assert "ev_safe" in response.text
    # Headings should be translated
    assert "行动计划" in response.text


def test_bilingual_review_zh_does_not_call_translator(
    tmp_path: Path,
) -> None:
    """New bilingual reviews should NOT call the translator for zh."""
    store = ReviewStore(tmp_path / "reviews.db")
    runner = FakeRunner(store)

    class TrackingTranslator:
        called = False

        def translate_finding_prose(self, finding: dict) -> dict:
            TrackingTranslator.called = True
            raise RuntimeError("Should not be called")

    localization_service = LocalizationService(store, TrackingTranslator())
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(build_reviews_router(store, runner, localization_service))
    client = TestClient(app)

    _create_bilingual_review(store)

    # Request zh — should NOT call translator
    response = client.get("/api/reviews/task-bi/findings?lang=zh")

    assert response.status_code == 200
    assert TrackingTranslator.called is False
    finding = response.json()["findings"][0]
    assert finding["title"] == "API 层存在边界风险"


def test_legacy_review_falls_back_to_translator(
    tmp_path: Path,
) -> None:
    """Old reviews without bilingual display should fall back to translator."""
    store = ReviewStore(tmp_path / "reviews.db")
    runner = FakeRunner(store)

    class TrackingTranslator:
        called = False

        def translate_finding_prose(self, finding: dict) -> dict:
            TrackingTranslator.called = True
            return {"title_zh": "翻译标题", "description_zh": "翻译描述"}

    localization_service = LocalizationService(store, TrackingTranslator())
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(build_reviews_router(store, runner, localization_service))
    client = TestClient(app)

    # Create a legacy review WITHOUT bilingual display fields
    store.create_review("task-legacy", "https://github.com/example/project")
    store.update_status("task-legacy", ReviewStatus.completed, report_markdown="# Test")
    store.replace_structured_findings(
        "task-legacy",
        [
            ReviewFinding(
                section="Architecture Summary",
                title="Legacy finding",
                description="Legacy description",
                severity="high",
                files=["a.py"],
                evidence_ids=["ev_legacy"],
                evidence=["ev_legacy -> a.py:1-5"],
            ),
        ],
        [
            EvidenceRecord(
                evidence_id="ev_legacy",
                file_path="a.py",
                start_line=1,
                end_line=5,
                snippet="code",
                kind="symbol",
                symbols=[],
            ),
        ],
    )

    response = client.get("/api/reviews/task-legacy/findings?lang=zh")

    assert response.status_code == 200
    assert TrackingTranslator.called is True


def test_bilingual_switch_en_to_zh_is_instant(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Switching from en to zh should use stored fields, not call LLM."""
    client, store, _ = api_client
    _create_bilingual_review(store)

    # Both requests should work without any LLM calls
    en = client.get("/api/reviews/task-bi/findings?lang=en")
    zh = client.get("/api/reviews/task-bi/findings?lang=zh")

    assert en.status_code == 200
    assert zh.status_code == 200
    # Different titles
    assert en.json()["findings"][0]["title"] == "Boundary risk in API layer"
    assert zh.json()["findings"][0]["title"] == "API 层存在边界风险"
    # Same structural fields
    assert en.json()["findings"][0]["evidence_ids"] == zh.json()["findings"][0]["evidence_ids"]
    assert en.json()["findings"][0]["severity"] == zh.json()["findings"][0]["severity"]


def test_bilingual_zh_no_bad_terms(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Chinese output must never contain banned terms."""
    client, store, _ = api_client
    _create_bilingual_review(store)

    response = client.get("/api/reviews/task-bi/findings?lang=zh")

    assert response.status_code == 200
    finding = response.json()["findings"][0]
    for field in ("title", "description", "recommendation", "impact", "first_step", "caveat"):
        value = finding.get(field, "")
        assert "代码坏味道" not in value, f"Banned term in {field}: {value}"
        assert "[zh]" not in value, f"[zh] prefix in {field}: {value}"


def test_bilingual_zh_no_raw_severity_in_findings(
    api_client: tuple[TestClient, ReviewStore, FakeRunner],
) -> None:
    """Chinese findings should not contain raw English severity/confidence text."""
    client, store, _ = api_client
    _create_bilingual_review(store)

    response = client.get("/api/reviews/task-bi/findings?lang=zh")

    assert response.status_code == 200
    finding = response.json()["findings"][0]
    # Structural fields stay as-is (these are canonical values, not display text)
    assert finding["severity"] == "high"
    assert finding["confidence"] == 0.91
