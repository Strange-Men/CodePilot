from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend import cli
from backend.core.config import Settings
from backend.mcp_server import CodePilotMCPTools
from backend.models.context import EvidenceRecord
from backend.models.review import ReviewStatus
from backend.models.structured_review import ReviewFinding
from backend.storage.sqlite import ReviewStore
from backend.workflows.integration import ReviewWorkflow
from backend.workflows.scope import parse_unified_diff_paths


class FakePipeline:
    instances: list[FakePipeline] = []

    def __init__(self, settings, store, llm_client, review_scope=None, **_kwargs) -> None:
        self.settings = settings
        self.store = store
        self.llm_client = llm_client
        self.review_scope = review_scope
        self.instances.append(self)

    def run(self, task_id: str, repo_url: str):
        export_path = self.settings.reports_path / f"{task_id}.md"
        export_path.parent.mkdir(parents=True, exist_ok=True)
        scope_lines = ""
        if self.review_scope is not None:
            scope_lines = "\n\n# Diff Review Scope\n- Source: diff\n"
        report = (
            "# Architecture Summary\nDone.\n\n"
            "# Code Smells\nDone.\n\n"
            "# Maintainability\nDone.\n\n"
            "# Refactoring Opportunities\nDone.\n"
        )
        export_path.write_text(report + scope_lines, encoding="utf-8")
        finding = ReviewFinding(
            section="Code Smells",
            title="Scoped finding",
            description="A persisted structured finding.",
            severity="medium",
            evidence_ids=["ev_safe"],
            evidence=["ev_safe -> app.py:1-2"],
        )
        evidence = EvidenceRecord(
            evidence_id="ev_safe",
            file_path="app.py",
            start_line=1,
            end_line=2,
            snippet="secret = 'do-not-persist'",
            symbols=["create_app"],
        )
        self.store.replace_structured_findings(task_id, [finding], [evidence])
        self.store.update_status(
            task_id,
            ReviewStatus.completed,
            report_markdown=report + scope_lines,
            export_path=str(export_path),
        )


@pytest.fixture
def workflow_settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "reviews.db",
        workspace_path=tmp_path / "workspace",
        reports_path=tmp_path / "reports",
    )
    settings.workspace_path.mkdir()
    settings.reports_path.mkdir()
    return settings


@pytest.fixture(autouse=True)
def patch_workflow_dependencies(monkeypatch: pytest.MonkeyPatch, workflow_settings: Settings) -> None:
    FakePipeline.instances = []
    monkeypatch.setattr("backend.workflows.integration.ReviewPipeline", FakePipeline)
    monkeypatch.setattr("backend.workflows.integration.build_llm_client", lambda _settings: object())
    monkeypatch.setattr("backend.workflows.integration.get_settings", lambda: workflow_settings)


def test_cli_review_writes_markdown_and_json(tmp_path: Path) -> None:
    markdown_path = tmp_path / "review.md"
    json_path = tmp_path / "summary.json"

    exit_code = cli.main(
        [
            "review",
            "https://github.com/example/repo",
            "--engine",
            "v3_multi_agent",
            "--output",
            str(markdown_path),
            "--json-output",
            str(json_path),
            "--mock-llm",
        ]
    )

    summary = json.loads(json_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert markdown_path.exists()
    assert summary["review"]["status"] == "completed"
    assert summary["structured_findings"][0]["evidence_ids"] == ["ev_safe"]
    assert "do-not-persist" not in json.dumps(summary)
    assert FakePipeline.instances[0].settings.review_engine == "v3_multi_agent"
    assert FakePipeline.instances[0].settings.use_mock_llm is True


def test_ci_mode_is_non_blocking_by_default_and_configurable(tmp_path: Path) -> None:
    default_exit = cli.main(
        [
            "ci",
            "https://github.com/example/repo",
            "--json-output",
            str(tmp_path / "ci-default.json"),
        ]
    )
    strict_exit = cli.main(
        [
            "ci",
            "https://github.com/example/repo",
            "--json-output",
            str(tmp_path / "ci-strict.json"),
            "--fail-on",
            "medium",
        ]
    )

    assert default_exit == 0
    assert strict_exit == 1


def test_diff_mode_parses_fixture_diff_and_defaults_to_v3_multi_agent(tmp_path: Path) -> None:
    diff_path = tmp_path / "change.diff"
    diff_path.write_text(
        "\n".join(
            [
                "diff --git a/app.py b/app.py",
                "--- a/app.py",
                "+++ b/app.py",
                "@@ -1 +1 @@",
                "-old",
                "+new",
            ]
        ),
        encoding="utf-8",
    )
    json_path = tmp_path / "diff-summary.json"

    exit_code = cli.main(
        [
            "diff",
            "https://github.com/example/repo",
            "--diff-file",
            str(diff_path),
            "--json-output",
            str(json_path),
        ]
    )

    summary = json.loads(json_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert parse_unified_diff_paths(diff_path.read_text(encoding="utf-8")) == {"app.py"}
    assert FakePipeline.instances[-1].settings.review_engine == "v3_multi_agent"
    assert FakePipeline.instances[-1].review_scope.changed_paths == frozenset({"app.py"})
    assert summary["workflow_scope"]["changed_files"] == ["app.py"]


def test_mcp_tools_wrap_workflow_without_exposing_raw_evidence(workflow_settings: Settings) -> None:
    workflow = ReviewWorkflow(workflow_settings, ReviewStore(workflow_settings.database_path))
    tools = CodePilotMCPTools(workflow)

    result = tools.analyze_repository(
        "https://github.com/example/repo",
        changed_files=["app.py"],
    )

    assert result["review"]["status"] == "completed"
    assert tools.get_review_status(result["task_id"])["found"] is True
    assert tools.get_review_findings(result["task_id"])[0]["evidence_ids"] == ["ev_safe"]
    assert tools.get_review_evidence(result["task_id"])[0]["file_path"] == "app.py"
    assert "do-not-persist" not in json.dumps(tools.get_review_report(result["task_id"]))
