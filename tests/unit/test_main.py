from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from backend.core.config import Settings
from backend.main import create_app
from backend.models.review import ReviewStatus
from backend.storage.sqlite import ReviewStore


class LifecycleRunner:
    def __init__(self) -> None:
        self.shutdown_calls = 0

    def submit(
        self,
        repo_url: str,
        llm_mode: str = "mock",
        llm_provider: str | None = None,
    ) -> str:
        return repo_url

    def shutdown(self, wait: bool = True) -> None:
        self.shutdown_calls += 1


def test_app_lifespan_shuts_down_review_runner(tmp_path: Path) -> None:
    settings = Settings(
        database_path=tmp_path / "reviews.db",
        workspace_path=tmp_path / "workspace",
        reports_path=tmp_path / "reports",
    )
    store = ReviewStore(settings.database_path)
    runner = LifecycleRunner()
    app = create_app(settings, store, runner)  # type: ignore[arg-type]

    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}

    assert runner.shutdown_calls == 1


def test_app_startup_recovers_stale_in_progress_reviews(tmp_path: Path) -> None:
    settings = Settings(
        database_path=tmp_path / "reviews.db",
        workspace_path=tmp_path / "workspace",
        reports_path=tmp_path / "reports",
    )
    store = ReviewStore(settings.database_path)
    store.create_review("stale-task", "https://github.com/example/one")
    with store._connect() as conn:
        conn.execute(
            "UPDATE reviews SET status = ?, updated_at = ? WHERE task_id = ?",
            (
                ReviewStatus.reviewing.value,
                datetime(2000, 1, 1, tzinfo=UTC).isoformat(),
                "stale-task",
            ),
        )
        conn.commit()
    runner = LifecycleRunner()
    app = create_app(settings, store, runner)  # type: ignore[arg-type]

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        row = store.get_review("stale-task")
        assert row["status"] == ReviewStatus.failed.value
        assert row["error"] == "Review was interrupted before completion."

    assert runner.shutdown_calls == 1
