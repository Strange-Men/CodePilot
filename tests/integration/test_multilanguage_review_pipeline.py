from __future__ import annotations

from pathlib import Path

from backend.core.config import Settings
from backend.llm.client import MockLLMClient
from backend.models.review import ReviewStatus
from backend.storage.sqlite import ReviewStore
from backend.tasks.pipeline import ReviewPipeline


class LocalMixedCloneService:
    def __init__(self, workspace_path: Path) -> None:
        self.workspace_path = workspace_path

    def clone(self, repo_url: str, task_id: str) -> Path:
        repo_dir = self.workspace_path / task_id / "repo"
        (repo_dir / "backend").mkdir(parents=True)
        (repo_dir / "frontend").mkdir()
        (repo_dir / "backend" / "app.py").write_text(
            "from backend.service import run\n\n"
            "def main():\n"
            "    return run()\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n",
            encoding="utf-8",
        )
        (repo_dir / "backend" / "service.py").write_text(
            "def run():\n    return 'ok'\n",
            encoding="utf-8",
        )
        (repo_dir / "frontend" / "app.ts").write_text(
            "import { render } from './view';\nexport const start = () => render();\n",
            encoding="utf-8",
        )
        (repo_dir / "frontend" / "view.ts").write_text(
            "export function render() { return 'ready'; }\n",
            encoding="utf-8",
        )
        (repo_dir / "frontend" / "legacy.js").write_text(
            "export const legacy = () => true;\n",
            encoding="utf-8",
        )
        return repo_dir

    def cleanup(self, task_id: str) -> None:
        return None


def test_mixed_repository_runs_all_matching_parsers_and_merges_report(tmp_path: Path) -> None:
    repo_url = "https://github.com/example/fullstack"
    settings = Settings(
        database_path=tmp_path / "reviews.db",
        workspace_path=tmp_path / "workspace",
        reports_path=tmp_path / "reports",
        use_mock_llm=True,
    )
    settings.workspace_path.mkdir()
    settings.reports_path.mkdir()
    store = ReviewStore(settings.database_path)
    store.create_review("task-mixed", repo_url)
    pipeline = ReviewPipeline(
        settings,
        store,
        MockLLMClient(),
        clone_service_factory=LocalMixedCloneService,
    )

    result = pipeline.run("task-mixed", repo_url)

    row = store.get_review("task-mixed")
    report = row["report_markdown"]
    assert row["status"] == ReviewStatus.completed.value
    assert result.total_python_files == 5
    assert result.analyzed_files == 5
    assert "Python + JavaScript + TypeScript" in report
    assert "Full-stack mixed-language application" in report
    assert "backend/app.py" in report
    assert "frontend/app.ts" in report
    assert "# Repository Insights" in report
    assert "## Onboarding Guide" in report
    assert "## Risk Hotspots" in report
