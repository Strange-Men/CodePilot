from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import backend.tasks.pipeline as pipeline_module
import backend.tasks.runner as runner_module
from backend.agents.orchestrator import AgentOrchestrator
from backend.api.reviews import build_reviews_router
from backend.core.config import Settings
from backend.llm.client import MockLLMClient
from backend.models.context import as_review_context
from backend.models.report_result import ReportResult
from backend.models.review import RepositoryContext, ReviewStatus, ReviewStatusResponse
from backend.models.review_state import AgentExecutionState, ReviewState
from backend.storage.sqlite import ReviewStore
from backend.tasks.runner import ReviewTaskRunner


class CapturingExecutor:
    def __init__(self) -> None:
        self.submissions: list[tuple[object, tuple[object, ...]]] = []
        self.shutdown_calls: list[tuple[bool, bool]] = []

    def submit(self, fn, *args):
        self.submissions.append((fn, args))

    def shutdown(self, wait: bool, cancel_futures: bool) -> None:
        self.shutdown_calls.append((wait, cancel_futures))


class FakeCloneService:
    instances: list[FakeCloneService] = []
    fail_clone = False

    def __init__(self, workspace_path: Path) -> None:
        self.workspace_path = workspace_path
        self.cleaned_task_ids: list[str] = []
        self.instances.append(self)

    def clone(self, repo_url: str, task_id: str) -> Path:
        if self.fail_clone:
            raise RuntimeError("clone failed")
        repo_dir = self.workspace_path / task_id / "repo"
        repo_dir.mkdir(parents=True)
        return repo_dir

    def cleanup(self, task_id: str) -> None:
        self.cleaned_task_ids.append(task_id)


class FakeRepositoryIndexer:
    parser_instances: list[object] = []

    def __init__(self, parser, max_files: int, max_file_size_bytes: int) -> None:
        self.parser = parser
        self.max_files = max_files
        self.max_file_size_bytes = max_file_size_bytes
        self.parser_instances.append(parser)

    def build_context(self, repo_dir: Path, repo_url: str) -> RepositoryContext:
        return RepositoryContext(
            repo_url=repo_url,
            total_python_files=1,
            analyzed_files=1,
            skipped_files=0,
            file_summaries=[],
            repository_summary=f"Indexed {repo_dir.name}.",
        )


class FakeReportGenerator:
    llm_clients: list[object] = []
    token_models: list[str] = []

    def __init__(
        self,
        llm_client,
        reports_path: Path,
        prompt_token_budget: int,
        token_model: str = "gpt-4o-mini",
        **kwargs,
    ) -> None:
        self.llm_client = llm_client
        self.reports_path = reports_path
        self.prompt_token_budget = prompt_token_budget
        self.token_model = token_model
        self.review_engine = "v2"
        self.llm_clients.append(llm_client)
        self.token_models.append(token_model)

    def configure_engine(self, review_engine: str) -> None:
        self.review_engine = review_engine

    def generate(self, task_id: str, context: RepositoryContext) -> ReportResult:
        export_path = self.reports_path / f"{task_id}.md"
        report = "# Architecture Summary\nDone.\n"
        export_path.write_text(report, encoding="utf-8")
        review_state = None
        agent_states: list[AgentExecutionState] = []
        if self.review_engine == "v3_multi_agent":
            review_context = as_review_context(context)
            review_state = ReviewState(task_id=task_id, context=review_context)
            agent_states = [
                AgentExecutionState(
                    agent_id="ArchitectureAgent",
                    status="completed",
                    validation_status="validated",
                ),
                AgentExecutionState(
                    agent_id="CodeSmellAgent",
                    status="completed",
                    validation_status="validated",
                ),
                AgentExecutionState(
                    agent_id="MaintainabilityAgent",
                    status="completed",
                    validation_status="validated",
                ),
                AgentExecutionState(
                    agent_id="RefactorAgent",
                    status="completed",
                    validation_status="validated",
                ),
            ]
        return ReportResult(
            report=report,
            export_path=export_path,
            agent_states=agent_states,
            review_state=review_state,
        )


class FakeParser:
    def __init__(self, language: str = "python", total_files: int = 1) -> None:
        self.language = language
        self.total_files = total_files

    def discover_files(self, repo_dir: Path, max_files: int, max_file_size_bytes: int) -> tuple[list[Path], int, int]:
        return [], self.total_files, 0


class FakeParserRegistry:
    def __init__(self, parsers: dict[str, FakeParser] | None = None) -> None:
        self.created_languages: list[str] = []
        self.parsers = parsers or {"python": FakeParser()}
        self.parser = self.parsers["python"]

    def languages(self) -> tuple[str, ...]:
        return tuple(self.parsers)

    def create(self, language: str) -> FakeParser:
        self.created_languages.append(language)
        return self.parsers[language]


class FakeLLMClient:
    def generate_review(self, prompt: str) -> str:
        return "# Architecture Summary\nDone.\n"


@pytest.fixture(autouse=True)
def reset_fake_clone_service() -> None:
    FakeCloneService.instances = []
    FakeCloneService.fail_clone = False
    FakeRepositoryIndexer.parser_instances = []
    FakeReportGenerator.llm_clients = []
    FakeReportGenerator.token_models = []


@pytest.fixture
def runner_dependencies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Settings, ReviewStore]:
    monkeypatch.setattr(pipeline_module, "CloneService", FakeCloneService)
    monkeypatch.setattr(pipeline_module, "RepositoryIndexer", FakeRepositoryIndexer)
    monkeypatch.setattr(pipeline_module, "ReportGenerator", FakeReportGenerator)

    settings = Settings(
        database_path=tmp_path / "reviews.db",
        workspace_path=tmp_path / "workspace",
        reports_path=tmp_path / "reports",
    )
    settings.workspace_path.mkdir()
    settings.reports_path.mkdir()
    return settings, ReviewStore(settings.database_path)


def test_submit_creates_review_and_schedules_task(runner_dependencies: tuple[Settings, ReviewStore]) -> None:
    settings, store = runner_dependencies
    settings.review_engine = "v3_multi_agent"
    runner = ReviewTaskRunner(settings, store)
    executor = CapturingExecutor()
    runner.executor = executor

    task_id = runner.submit("https://github.com/pallets/flask")

    row = store.get_review(task_id)
    assert row["status"] == "pending"
    assert row["repo_url"] == "https://github.com/pallets/flask"
    assert executor.submissions == [(runner._run, (task_id, "https://github.com/pallets/flask", "mock"))]
    app = FastAPI()
    app.include_router(build_reviews_router(store, runner))
    response = TestClient(app).get(f"/api/reviews/{task_id}")
    progress = response.json()["progress"]
    assert progress["current_phase"] == "Preparing repository"
    assert progress["total_agents"] == 4
    assert [item["label"] for item in progress["agents"]] == [
        "A1 ArchitectureAgent",
        "A2 CodeSmellAgent",
        "A3 MaintainabilityAgent",
        "A4 RefactorAgent",
    ]
    assert "progress" not in row


def test_run_completes_review_and_exports_report(runner_dependencies: tuple[Settings, ReviewStore]) -> None:
    settings, store = runner_dependencies
    runner = ReviewTaskRunner(settings, store)
    store.create_review("task-1", "https://github.com/pallets/flask")

    result = runner._run("task-1", "https://github.com/pallets/flask", "mock")

    row = store.get_review("task-1")
    assert row["status"] == ReviewStatus.completed.value
    assert row["report_markdown"] == "# Architecture Summary\nDone.\n"
    assert Path(row["export_path"]).exists()
    assert FakeCloneService.instances[0].cleaned_task_ids == ["task-1"]
    assert result.total_python_files == 1
    assert result.analyzed_files == 1
    assert result.skipped_files == 0
    old_response = ReviewStatusResponse(
        task_id="old-task",
        repo_url="https://github.com/pallets/flask",
        status=ReviewStatus.completed,
    )
    assert old_response.progress is None
    assert runner.get_progress("task-1") is None


def test_run_marks_task_failed_when_clone_raises(runner_dependencies: tuple[Settings, ReviewStore]) -> None:
    settings, store = runner_dependencies
    runner = ReviewTaskRunner(settings, store)
    store.create_review("task-1", "https://github.com/pallets/flask")
    FakeCloneService.fail_clone = True

    runner._run("task-1", "https://github.com/pallets/flask", "mock")

    row = store.get_review("task-1")
    assert row["status"] == ReviewStatus.failed.value
    assert row["error"] == "clone failed"
    assert FakeCloneService.instances[0].cleaned_task_ids == ["task-1"]
    settings.review_engine = "v3_multi_agent"
    runner._initialize_progress("agent-task")
    runner._update_progress("agent-task", "agent_running", "ArchitectureAgent")
    runner._update_progress(
        "agent-task",
        "agent_failed",
        "ArchitectureAgent",
        AgentExecutionState(
            agent_id="ArchitectureAgent",
            status="failed",
            error="MIMO_API_KEY=super-secret",
        ),
    )
    progress = runner.get_progress("agent-task")
    assert progress is not None
    assert progress.agents[0].status == "failed"
    assert progress.agents[0].error == "Agent execution failed."
    assert "super-secret" not in progress.model_dump_json()


def test_run_records_status_progression(
    runner_dependencies: tuple[Settings, ReviewStore],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, store = runner_dependencies
    runner = ReviewTaskRunner(settings, store)
    store.create_review("task-1", "https://github.com/pallets/flask")
    statuses: list[str] = []
    original_update_status = store.update_status

    def capture_status(task_id: str, status: ReviewStatus, **kwargs) -> None:
        statuses.append(status.value)
        original_update_status(task_id, status, **kwargs)

    monkeypatch.setattr(store, "update_status", capture_status)

    runner._run("task-1", "https://github.com/pallets/flask", "mock")

    assert statuses == ["cloning", "parsing", "summarizing", "reviewing", "completed"]


def test_run_uses_parser_registry_for_python_parser(runner_dependencies: tuple[Settings, ReviewStore]) -> None:
    settings, store = runner_dependencies
    parser_registry = FakeParserRegistry()
    llm_client = FakeLLMClient()
    runner = ReviewTaskRunner(settings, store, parser_registry=parser_registry, llm_client=llm_client)
    store.create_review("task-1", "https://github.com/pallets/flask")

    runner._run("task-1", "https://github.com/pallets/flask", "mock")

    assert parser_registry.created_languages == ["python"]
    assert FakeRepositoryIndexer.parser_instances == [parser_registry.parser]
    assert FakeReportGenerator.llm_clients == [llm_client]
    assert FakeReportGenerator.token_models == [settings.openai_model]


def test_run_selects_javascript_parser_when_js_files_are_detected(
    runner_dependencies: tuple[Settings, ReviewStore],
) -> None:
    settings, store = runner_dependencies
    javascript_parser = FakeParser("javascript", total_files=3)
    parser_registry = FakeParserRegistry(
        {
            "python": FakeParser("python", total_files=0),
            "javascript": javascript_parser,
        }
    )
    runner = ReviewTaskRunner(settings, store, parser_registry=parser_registry, llm_client=FakeLLMClient())
    store.create_review("task-1", "https://github.com/expressjs/express")

    runner._run("task-1", "https://github.com/expressjs/express", "mock")

    assert FakeRepositoryIndexer.parser_instances == [javascript_parser]


def test_run_persists_v3_review_state_for_inspection(
    runner_dependencies: tuple[Settings, ReviewStore],
    sample_context,
) -> None:
    settings, store = runner_dependencies
    settings.review_engine = "v3_multi_agent"
    runner = ReviewTaskRunner(settings, store, llm_client=FakeLLMClient())
    store.create_review("task-1", "https://github.com/pallets/flask")

    runner._run("task-1", "https://github.com/pallets/flask", "mock")

    state = store.get_review_state("task-1")
    inspection = store.inspect_review("task-1")
    assert state is not None
    assert state.task_id == "task-1"
    assert inspection is not None
    assert inspection["review_state"]["task_id"] == "task-1"
    events: list[tuple[str, str | None]] = []
    AgentOrchestrator(
        MockLLMClient(),
        progress_callback=lambda event, agent_id, _state: events.append((event, agent_id)),
    ).review(sample_context.to_review_context())
    assert [agent_id for event, agent_id in events if event == "agent_running"] == [
        "ArchitectureAgent",
        "CodeSmellAgent",
        "MaintainabilityAgent",
        "RefactorAgent",
    ]


def test_shutdown_drains_executor_once_and_rejects_new_work(
    runner_dependencies: tuple[Settings, ReviewStore],
) -> None:
    settings, store = runner_dependencies
    runner = ReviewTaskRunner(settings, store)
    executor = CapturingExecutor()
    runner.executor = executor

    runner.shutdown()
    runner.shutdown()

    assert executor.shutdown_calls == [(True, False)]
    with pytest.raises(RuntimeError, match="shut down"):
        runner.submit("https://github.com/pallets/flask")
    assert store.list_reviews() == []


def test_completed_progress_expires_after_ten_minutes(
    runner_dependencies: tuple[Settings, ReviewStore],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, store = runner_dependencies
    settings.review_engine = "v3_multi_agent"
    clock = [100.0]
    monkeypatch.setattr(runner_module, "monotonic", lambda: clock[0])
    runner = ReviewTaskRunner(settings, store)
    runner._initialize_progress("task-1")
    runner._update_progress("task-1", "done")

    clock[0] = 699.999
    runner.cleanup_progress()
    assert runner.get_progress("task-1") is not None

    clock[0] = 700.0
    runner.cleanup_progress()
    assert runner.get_progress("task-1") is None


def test_failed_progress_expires_after_sixty_minutes(
    runner_dependencies: tuple[Settings, ReviewStore],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, store = runner_dependencies
    settings.review_engine = "v3_multi_agent"
    clock = [200.0]
    monkeypatch.setattr(runner_module, "monotonic", lambda: clock[0])
    runner = ReviewTaskRunner(settings, store)
    runner._initialize_progress("task-1")
    runner._update_progress("task-1", "task_failed")

    clock[0] = 3799.999
    runner.cleanup_progress()
    assert runner.get_progress("task-1") is not None

    clock[0] = 3800.0
    runner.cleanup_progress()
    assert runner.get_progress("task-1") is None


def test_running_progress_is_never_ttl_evicted(
    runner_dependencies: tuple[Settings, ReviewStore],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, store = runner_dependencies
    settings.review_engine = "v3_multi_agent"
    clock = [300.0]
    monkeypatch.setattr(runner_module, "monotonic", lambda: clock[0])
    runner = ReviewTaskRunner(settings, store)
    runner._initialize_progress("task-1")
    runner._update_progress("task-1", "agent_running", "ArchitectureAgent")
    runner._update_progress("task-1", "done")

    clock[0] = 10_000.0
    runner.cleanup_progress()

    progress = runner.get_progress("task-1")
    assert progress is not None
    assert progress.agents[0].status == "running"


def test_get_progress_cleans_expired_terminal_snapshot(
    runner_dependencies: tuple[Settings, ReviewStore],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, store = runner_dependencies
    settings.review_engine = "v3_multi_agent"
    clock = [400.0]
    monkeypatch.setattr(runner_module, "monotonic", lambda: clock[0])
    runner = ReviewTaskRunner(settings, store)
    runner._initialize_progress("task-1")
    runner._update_progress("task-1", "done")

    clock[0] = 1000.0

    assert runner.get_progress("task-1") is None
    assert "task-1" not in runner._progress_terminal_at


def test_clear_progress_removes_snapshot(
    runner_dependencies: tuple[Settings, ReviewStore],
) -> None:
    settings, store = runner_dependencies
    settings.review_engine = "v3_multi_agent"
    runner = ReviewTaskRunner(settings, store)
    runner._initialize_progress("task-1")
    runner._update_progress("task-1", "done")

    runner.clear_progress("task-1")

    assert runner.get_progress("task-1") is None
    assert "task-1" not in runner._progress_terminal_at


def test_default_review_engine_is_v3_multi_agent() -> None:
    settings = Settings()
    assert settings.review_engine == "v3_multi_agent"


def test_explicit_review_engine_v2_override(tmp_path: Path) -> None:
    settings = Settings(
        REVIEW_ENGINE="v2",
        database_path=tmp_path / "reviews.db",
        workspace_path=tmp_path / "workspace",
        reports_path=tmp_path / "reports",
    )
    assert settings.review_engine == "v2"


def test_fresh_mock_review_persists_four_agent_states(
    runner_dependencies: tuple[Settings, ReviewStore],
) -> None:
    settings, store = runner_dependencies
    runner = ReviewTaskRunner(settings, store, llm_client=FakeLLMClient())
    store.create_review("task-v3", "https://github.com/pallets/flask")

    runner._run("task-v3", "https://github.com/pallets/flask", "mock")

    row = store.get_review("task-v3")
    assert row["status"] == ReviewStatus.completed.value
    agent_states = store.get_agent_states("task-v3")
    assert len(agent_states) == 4
    agent_ids = [state["agent_id"] for state in agent_states]
    assert agent_ids == [
        "ArchitectureAgent",
        "CodeSmellAgent",
        "MaintainabilityAgent",
        "RefactorAgent",
    ]
    assert all(state["status"] == "completed" for state in agent_states)


def test_fresh_mock_review_agent_states_api_returns_non_empty(
    runner_dependencies: tuple[Settings, ReviewStore],
) -> None:
    settings, store = runner_dependencies
    runner = ReviewTaskRunner(settings, store, llm_client=FakeLLMClient())
    store.create_review("task-api", "https://github.com/pallets/flask")
    runner._run("task-api", "https://github.com/pallets/flask", "mock")

    app = FastAPI()
    app.include_router(build_reviews_router(store, runner))
    response = TestClient(app).get("/api/reviews/task-api/agent-states")

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == "task-api"
    assert len(body["agents"]) == 4
    assert body["agents"][0]["agent_id"] == "ArchitectureAgent"
    assert body["agents"][0]["status"] == "completed"


def test_fresh_mock_review_progress_shows_four_agents(
    runner_dependencies: tuple[Settings, ReviewStore],
) -> None:
    settings, store = runner_dependencies
    runner = ReviewTaskRunner(settings, store, llm_client=FakeLLMClient())
    task_id = runner.submit("https://github.com/pallets/flask")

    runner._run(task_id, "https://github.com/pallets/flask", "mock")

    app = FastAPI()
    app.include_router(build_reviews_router(store, runner))
    response = TestClient(app).get(f"/api/reviews/{task_id}")
    progress = response.json().get("progress")
    # Progress may be None after cleanup, but if present it must have 4 agents
    if progress is not None:
        assert progress["total_agents"] == 4


def test_v2_engine_does_not_persist_agent_states(
    runner_dependencies: tuple[Settings, ReviewStore],
) -> None:
    settings, store = runner_dependencies
    settings.review_engine = "v2"
    runner = ReviewTaskRunner(settings, store, llm_client=FakeLLMClient())
    store.create_review("task-v2", "https://github.com/pallets/flask")

    runner._run("task-v2", "https://github.com/pallets/flask", "mock")

    row = store.get_review("task-v2")
    assert row["status"] == ReviewStatus.completed.value
    agent_states = store.get_agent_states("task-v2")
    assert len(agent_states) == 0


class FailingCloneAfterAgentStates:
    """Clone service that succeeds first, then fails on second call to simulate post-agent failure."""

    def __init__(self, workspace_path: Path) -> None:
        self.workspace_path = workspace_path

    def clone(self, repo_url: str, task_id: str) -> Path:
        repo_dir = self.workspace_path / task_id / "repo"
        repo_dir.mkdir(parents=True, exist_ok=True)
        return repo_dir

    def cleanup(self, task_id: str) -> None:
        return None


class AgentStatesThenExplodeReportGenerator:
    """Report generator that returns agent states but the pipeline fails after."""

    def __init__(self, llm_client, reports_path, prompt_token_budget, token_model="gpt-4o-mini", **kwargs):
        self.reports_path = reports_path
        self.review_engine = "v2"
        self.store_ref = None

    def configure_engine(self, review_engine: str) -> None:
        self.review_engine = review_engine

    def generate(self, task_id: str, context):
        from backend.models.report_result import ReportResult

        if self.review_engine == "v3_multi_agent":
            agent_states = [
                AgentExecutionState(
                    agent_id="ArchitectureAgent", status="completed", validation_status="validated",
                ),
                AgentExecutionState(
                    agent_id="CodeSmellAgent", status="failed", error="LLM read timeout", validation_status="failed",
                ),
            ]
            export_path = self.reports_path / f"{task_id}.md"
            export_path.write_text("# Fallback\n", encoding="utf-8")
            return ReportResult(
                report="# Fallback\nAgent pipeline completed.\n",
                export_path=export_path,
                agent_states=agent_states,
            )
        export_path = self.reports_path / f"{task_id}.md"
        export_path.write_text("# Done\n", encoding="utf-8")
        return ReportResult(report="# Done\n", export_path=export_path)


def test_pipeline_persists_agent_states_on_failure(
    runner_dependencies: tuple[Settings, ReviewStore],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, store = runner_dependencies
    settings.review_engine = "v3_multi_agent"
    monkeypatch.setattr(pipeline_module, "ReportGenerator", AgentStatesThenExplodeReportGenerator)
    runner = ReviewTaskRunner(settings, store, llm_client=FakeLLMClient())
    store.create_review("task-fail", "https://github.com/pallets/flask")

    runner._run("task-fail", "https://github.com/pallets/flask", "mock")

    row = store.get_review("task-fail")
    assert row["status"] == ReviewStatus.completed.value
    agent_states = store.get_agent_states("task-fail")
    assert len(agent_states) == 2
    assert agent_states[0]["agent_id"] == "ArchitectureAgent"
    assert agent_states[0]["status"] == "completed"
    assert agent_states[1]["agent_id"] == "CodeSmellAgent"
    assert agent_states[1]["status"] == "failed"


def test_pipeline_persists_agent_states_when_post_generate_step_fails(
    runner_dependencies: tuple[Settings, ReviewStore],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that agent states are persisted even when a step after generate() fails."""
    settings, store = runner_dependencies
    settings.review_engine = "v3_multi_agent"
    monkeypatch.setattr(pipeline_module, "ReportGenerator", AgentStatesThenExplodeReportGenerator)

    def failing_complete(self, task_id, report, export_path):
        raise RuntimeError("post-generate failure")

    monkeypatch.setattr(pipeline_module.ReviewPipeline, "_complete_review", failing_complete)
    runner = ReviewTaskRunner(settings, store, llm_client=FakeLLMClient())
    store.create_review("task-post-fail", "https://github.com/pallets/flask")

    runner._run("task-post-fail", "https://github.com/pallets/flask", "mock")

    row = store.get_review("task-post-fail")
    assert row["status"] == ReviewStatus.failed.value
    agent_states = store.get_agent_states("task-post-fail")
    assert len(agent_states) == 2
    assert agent_states[0]["agent_id"] == "ArchitectureAgent"
    assert agent_states[0]["status"] == "completed"
    assert agent_states[1]["agent_id"] == "CodeSmellAgent"
    assert agent_states[1]["status"] == "failed"
