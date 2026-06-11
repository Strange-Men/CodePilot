from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from evaluation.comparison import (
    compare_run_directories,
    find_previous_comparable_run,
)
from evaluation.registry import EvaluationRunRegistry, load_dataset_definition
from evaluation.run_eval import main


def test_fixture_runs_persist_complete_artifacts_and_optional_comparison(tmp_path: Path) -> None:
    output_dir = tmp_path / "runs"
    dataset = Path("evaluation/datasets/v3_5_fixtures.json")
    common = [
        "--dataset",
        str(dataset),
        "--output-dir",
        str(output_dir),
        "--max-repos",
        "1",
    ]

    first_exit = main([*common, "--work-dir", str(tmp_path / "work-1")])
    second_exit = main(
        [
            *common,
            "--work-dir",
            str(tmp_path / "work-2"),
            "--compare-previous",
        ]
    )

    assert first_exit == 0
    assert second_exit == 0
    run_dirs = sorted(output_dir.iterdir())
    assert len(run_dirs) == 2
    latest = max(
        run_dirs,
        key=lambda path: json.loads((path / "run.json").read_text(encoding="utf-8"))["ended_at"],
    )
    assert (latest / "summary.json").exists()
    assert (latest / "summary.md").exists()
    assert (latest / "quality-summary.json").exists()
    assert (latest / "cost-summary.json").exists()
    assert (latest / "comparison.json").exists()
    assert (latest / "comparison.md").exists()
    assert (latest / "repos" / "flask-like-fixture" / "result.json").exists()
    assert (latest / "repos" / "flask-like-fixture" / "report.md").exists()

    summary = json.loads((latest / "summary.json").read_text(encoding="utf-8"))
    result = json.loads(
        (latest / "repos" / "flask-like-fixture" / "result.json").read_text(encoding="utf-8")
    )
    assert summary["total_repos"] == 1
    assert summary["repo_results"][0]["report_markdown"]
    assert len(summary["repo_results"][0]["report_markdown"]) <= 5000
    assert result["quality_metrics"]["aggregate_score"] == 100.0
    assert result["usage"]["duration_seconds"] > 0


def test_comparison_filters_metadata_and_reports_deterministic_deltas(tmp_path: Path) -> None:
    dataset = load_dataset_definition(Path("evaluation/datasets/v3_5_fixtures.json"))
    started = datetime(2026, 6, 11, 12, 0, tzinfo=UTC)
    previous = _registry_with_repo(
        tmp_path,
        dataset,
        started,
        model="example-model",
        score=80.0,
        failed_checks=["old_check"],
        cost=0.01,
        duration=2.0,
    )
    _registry_with_repo(
        tmp_path,
        dataset,
        started + timedelta(minutes=1),
        model="different-model",
        score=99.0,
        failed_checks=[],
        cost=0.02,
        duration=1.0,
    )
    current = _registry_with_repo(
        tmp_path,
        dataset,
        started + timedelta(minutes=2),
        model="example-model",
        score=90.0,
        failed_checks=["new_check"],
        cost=0.015,
        duration=1.5,
    )

    selected = find_previous_comparable_run(tmp_path, current.output_dir)
    comparison = compare_run_directories(current.output_dir, selected)
    payload = comparison.to_dict()

    assert selected == previous.output_dir
    assert payload["aggregate"]["average_quality_score_delta"] == 10.0
    assert payload["aggregate"]["estimated_cost_delta"] == 0.005
    assert payload["aggregate"]["duration_seconds_delta"] == -0.5
    assert payload["repos"][0]["failed_checks_added"] == ["new_check"]
    assert payload["repos"][0]["failed_checks_resolved"] == ["old_check"]


def _registry_with_repo(
    output_dir: Path,
    dataset,
    started: datetime,
    *,
    model: str,
    score: float,
    failed_checks: list[str],
    cost: float,
    duration: float,
) -> EvaluationRunRegistry:
    registry = EvaluationRunRegistry(
        output_dir,
        dataset.metadata,
        engine="v3_multi_agent",
        mode="real",
        provider="openai",
        model=model,
        now=started,
    )
    registry.add_repo(
        repo_id="fixture",
        repo_name="fixtures/example",
        repo_url="fixture://example",
        started_at=started.isoformat(),
        ended_at=(started + timedelta(seconds=duration)).isoformat(),
        duration_seconds=duration,
        status="completed",
        passed=not failed_checks,
        report_markdown="# Executive Summary\nDone.\n",
        findings=[],
        evidence_refs=[],
        agent_states=[],
        quality_metrics={
            "aggregate_score": score,
            "passed": not failed_checks,
            "failed_checks": failed_checks,
            "dimensions": [],
            "checks": [],
        },
        usage={
            "model": model,
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
            "llm_calls": 1,
            "duration_seconds": duration,
            "estimated_cost": cost,
            "currency": "USD",
            "pricing_known": True,
            "agents": [],
        },
    )
    registry.finalize(started + timedelta(seconds=duration))
    return registry
