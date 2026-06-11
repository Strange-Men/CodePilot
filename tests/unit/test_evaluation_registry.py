from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from evaluation.registry import (
    REPORT_MARKDOWN_MAX_CHARS,
    EvaluationRunRegistry,
    load_dataset_definition,
)


def test_dataset_definition_resolves_versioned_fixture_paths() -> None:
    dataset_path = Path("evaluation/datasets/v3_5_fixtures.json")

    dataset = load_dataset_definition(dataset_path)

    assert dataset.metadata.version == "3.5.0"
    assert dataset.metadata.repo_count == 1
    assert len(dataset.metadata.sha256) == 64
    assert Path(dataset.repos[0]["fixture_path"]).is_dir()
    assert dataset.repos[0]["url"] == "fixture://flask-like-fixture"


def test_run_registry_persists_bounded_safe_repo_metadata(tmp_path: Path) -> None:
    dataset = load_dataset_definition(Path("evaluation/datasets/v3_5_fixtures.json"))
    started = datetime(2026, 6, 11, 12, 0, tzinfo=UTC)
    registry = EvaluationRunRegistry(
        tmp_path,
        dataset.metadata,
        engine="v3_multi_agent",
        mode="mock",
        now=started,
    )
    report = "# Executive Summary\n" + ("x" * (REPORT_MARKDOWN_MAX_CHARS + 100))

    record = registry.add_repo(
        repo_id="fixture",
        repo_name="fixtures/example",
        repo_url="fixture://example",
        started_at=started.isoformat(),
        ended_at=(started + timedelta(seconds=2)).isoformat(),
        duration_seconds=2.0,
        status="completed",
        passed=True,
        report_markdown=report,
        findings=[{"severity": "high"}],
        evidence_refs=[{"evidence_id": "ev_safe"}],
        agent_states=[
            {
                "agent_id": "ArchitectureAgent",
                "status": "completed",
                "findings": [{"severity": "high", "confidence": 0.8}],
                "evidence_ids": ["ev_safe"],
            }
        ],
    )
    registry.finalize(started + timedelta(seconds=3))

    payload = json.loads((registry.output_dir / "run.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "3.5"
    assert payload["duration_seconds"] == 3.0
    assert len(payload["repos"][0]["report_markdown"]) == REPORT_MARKDOWN_MAX_CHARS
    assert record.findings_count == 1
    assert record.evidence_count == 1
    assert record.agent_state_summary[0]["severity_distribution"] == {"high": 1}
    assert (registry.output_dir / record.report_path).read_text(encoding="utf-8") == report


def test_fixture_dataset_runs_without_network_or_credentials(tmp_path: Path) -> None:
    from evaluation.run_eval import run_dataset_eval

    dataset = load_dataset_definition(Path("evaluation/datasets/v3_5_fixtures.json"))

    results = run_dataset_eval(
        dataset.repos,
        tmp_path,
        config={"runner": {"review_engine": "v3_multi_agent"}},
    )

    assert len(results) == 1
    assert results[0].status == "completed"
    assert results[0].passed is True
    assert results[0].has_all_sections is True
