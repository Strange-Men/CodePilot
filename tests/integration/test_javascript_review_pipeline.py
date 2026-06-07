from __future__ import annotations

from pathlib import Path

from backend.core.config import Settings
from backend.llm.client import REPORT_SECTIONS, MockLLMClient
from backend.models.review import ReviewStatus
from backend.storage.sqlite import ReviewStore
from backend.tasks.pipeline import ReviewPipeline


class LocalJavaScriptCloneService:
    def __init__(self, workspace_path: Path) -> None:
        self.workspace_path = workspace_path

    def clone(self, repo_url: str, task_id: str) -> Path:
        repo_dir = self.workspace_path / task_id / "repo"
        source_dir = repo_dir / "src"
        source_dir.mkdir(parents=True)
        (source_dir / "index.js").write_text(
            "import express from 'express';\n"
            "export class AppServer {}\n"
            "export const createServer = () => express();\n",
            encoding="utf-8",
        )
        return repo_dir

    def cleanup(self, task_id: str) -> None:
        return None


def test_javascript_repository_report_uses_javascript_language(tmp_path: Path) -> None:
    repo_url = "https://github.com/expressjs/express"
    settings = Settings(
        database_path=tmp_path / "reviews.db",
        workspace_path=tmp_path / "workspace",
        reports_path=tmp_path / "reports",
        use_mock_llm=True,
    )
    settings.workspace_path.mkdir()
    settings.reports_path.mkdir()
    store = ReviewStore(settings.database_path)
    store.create_review("task-js", repo_url)
    pipeline = ReviewPipeline(
        settings,
        store,
        MockLLMClient(),
        clone_service_factory=LocalJavaScriptCloneService,
    )

    result = pipeline.run("task-js", repo_url)

    row = store.get_review("task-js")
    assert row["status"] == ReviewStatus.completed.value
    assert result.total_python_files == 1
    assert result.analyzed_files == 1
    assert result.skipped_files == 0
    assert all(f"# {section}" in row["report_markdown"] for section in REPORT_SECTIONS)
    assert "# Repository Metrics" in row["report_markdown"]
    assert "- Total lines: 3" in row["report_markdown"]
    assert "| src/index.js | 3 | 0 | 0.90 |" in row["report_markdown"]
    assert "JavaScript application" in row["report_markdown"]
    assert "Python application" not in row["report_markdown"]
