from __future__ import annotations

from pathlib import Path

import pytest

import backend.tasks.runner as runner_module
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
    def __init__(self, parser, max_files: int, max_file_size_bytes: int) -> None:
        self.parser = parser
        self.max_files = max_files
        self.max_file_size_bytes = max_file_size_bytes

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
    def __init__(self, llm_client, reports_path: Path, prompt_token_budget: int) -> None:
        self.llm_client = llm_client
        self.reports_path = reports_path
        self.prompt_token_budget = prompt_token_budget

    def generate(self, task_id: str, context: RepositoryContext) -> tuple[str, Path]:
        export_path = self.reports_path / f"{task_id}.md"
        report = "# Architecture Summary\nDone.\n"
        export_path.write_text(report, encoding="utf-8")
        return report, export_path


@pytest.fixture(autouse=True)
def reset_fake_clone_service() -> None:
    FakeCloneService.instances = []
    FakeCloneService.fail_clone = False


@pytest.fixture
def runner_dependencies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Settings, ReviewStore]:
    monkeypatch.setattr(runner_module, "CloneService", FakeCloneService)
    monkeypatch.setattr(runner_module, "RepositoryIndexer", FakeRepositoryIndexer)
    monkeypatch.setattr(runner_module, "ReportGenerator", FakeReportGenerator)
    monkeypatch.setattr(runner_module, "build_llm_client", lambda settings: object())

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

    runner._run("task-1", "https://github.com/pallets/flask")

    row = store.get_review("task-1")
    assert row["status"] == ReviewStatus.completed.value
    assert row["report_markdown"] == "# Architecture Summary\nDone.\n"
    assert Path(row["export_path"]).exists()
    assert FakeCloneService.instances[0].cleaned_task_ids == ["task-1"]


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
