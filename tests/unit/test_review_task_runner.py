from __future__ import annotations

from pathlib import Path

import pytest

import backend.tasks.pipeline as pipeline_module
from backend.core.config import Settings
from backend.models.review import RepositoryContext, ReviewStatus
from backend.storage.sqlite import ReviewStore
from backend.tasks.runner import ReviewTaskRunner


class CapturingExecutor:
    def __init__(self) -> None:
        self.submissions: list[tuple[object, tuple[object, ...]]] = []

    def submit(self, fn, *args):
        self.submissions.append((fn, args))


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

    def __init__(self, llm_client, reports_path: Path, prompt_token_budget: int) -> None:
        self.llm_client = llm_client
        self.reports_path = reports_path
        self.prompt_token_budget = prompt_token_budget
        self.llm_clients.append(llm_client)

    def generate(self, task_id: str, context: RepositoryContext) -> tuple[str, Path]:
        export_path = self.reports_path / f"{task_id}.md"
        report = "# Architecture Summary\nDone.\n"
        export_path.write_text(report, encoding="utf-8")
        return report, export_path


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
    runner = ReviewTaskRunner(settings, store)
    executor = CapturingExecutor()
    runner.executor = executor

    task_id = runner.submit("https://github.com/pallets/flask")

    row = store.get_review(task_id)
    assert row["status"] == "pending"
    assert row["repo_url"] == "https://github.com/pallets/flask"
    assert executor.submissions == [(runner._run, (task_id, "https://github.com/pallets/flask"))]


def test_run_completes_review_and_exports_report(runner_dependencies: tuple[Settings, ReviewStore]) -> None:
    settings, store = runner_dependencies
    runner = ReviewTaskRunner(settings, store)
    store.create_review("task-1", "https://github.com/pallets/flask")

    result = runner._run("task-1", "https://github.com/pallets/flask")

    row = store.get_review("task-1")
    assert row["status"] == ReviewStatus.completed.value
    assert row["report_markdown"] == "# Architecture Summary\nDone.\n"
    assert Path(row["export_path"]).exists()
    assert FakeCloneService.instances[0].cleaned_task_ids == ["task-1"]
    assert result.total_python_files == 1
    assert result.analyzed_files == 1
    assert result.skipped_files == 0


def test_run_marks_task_failed_when_clone_raises(runner_dependencies: tuple[Settings, ReviewStore]) -> None:
    settings, store = runner_dependencies
    runner = ReviewTaskRunner(settings, store)
    store.create_review("task-1", "https://github.com/pallets/flask")
    FakeCloneService.fail_clone = True

    runner._run("task-1", "https://github.com/pallets/flask")

    row = store.get_review("task-1")
    assert row["status"] == ReviewStatus.failed.value
    assert row["error"] == "clone failed"
    assert FakeCloneService.instances[0].cleaned_task_ids == ["task-1"]


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

    runner._run("task-1", "https://github.com/pallets/flask")

    assert statuses == ["cloning", "parsing", "summarizing", "reviewing", "completed"]


def test_run_uses_parser_registry_for_python_parser(runner_dependencies: tuple[Settings, ReviewStore]) -> None:
    settings, store = runner_dependencies
    parser_registry = FakeParserRegistry()
    llm_client = FakeLLMClient()
    runner = ReviewTaskRunner(settings, store, parser_registry=parser_registry, llm_client=llm_client)
    store.create_review("task-1", "https://github.com/pallets/flask")

    runner._run("task-1", "https://github.com/pallets/flask")

    assert parser_registry.created_languages == ["python"]
    assert FakeRepositoryIndexer.parser_instances == [parser_registry.parser]
    assert FakeReportGenerator.llm_clients == [llm_client]


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

    runner._run("task-1", "https://github.com/expressjs/express")

    assert FakeRepositoryIndexer.parser_instances == [javascript_parser]
