from __future__ import annotations

import json
from pathlib import Path

from backend.reviewers.report_composer import HumanReadableReportComposer
from evaluation.quality_metrics import evaluate_report_quality
from evaluation.registry import EvaluationRunRegistry, load_dataset_definition
from evaluation.report_quality import _quality_sample
from evaluation.run_eval import _write_quality_summary


def test_v3_5_quality_metrics_score_the_v3_4_grounded_sample() -> None:
    context, draft, agent_states, _secret = _quality_sample()
    report = HumanReadableReportComposer().compose(context, draft, agent_states)

    score = evaluate_report_quality(
        report,
        [finding.model_dump(mode="json") for finding in draft.findings],
        [
            {
                "evidence_id": record.evidence_id,
                "file_path": record.file_path,
                "start_line": record.start_line,
                "end_line": record.end_line,
            }
            for record in context.evidence
        ],
        [state.model_dump(mode="json") for state in agent_states],
        tags=["flask-like", "test-heavy"],
    )

    assert score.passed is True
    assert score.aggregate_score == 100.0
    assert {dimension.name for dimension in score.dimensions} == {
        "readability",
        "actionability",
        "grounding",
        "agent_visibility",
        "classification_quality",
    }


def test_quality_metrics_report_deterministic_failed_checks() -> None:
    score = evaluate_report_quality(
        "# Architecture Summary\nA Request and Response utility library.\n",
        [
            {
                "description": "Ungrounded recommendation.",
                "recommendation": "Change it.",
                "files": [],
                "evidence_ids": [],
            }
        ],
        [],
        [],
        tags=["request-response-only"],
    )

    assert score.passed is False
    assert "executive_summary_present" in score.failed_checks
    assert "recommendations_name_files" in score.failed_checks
    assert "findings_include_evidence_ids" in score.failed_checks
    assert "agent_summary_present" in score.failed_checks
    assert score.aggregate_score < 50


def test_generic_request_response_names_do_not_require_framework_classification() -> None:
    context, draft, agent_states, _secret = _quality_sample()
    report = HumanReadableReportComposer().compose(context, draft, agent_states)
    report = report.replace("Python web framework", "Python SDK/client library")

    score = evaluate_report_quality(
        report,
        [finding.model_dump(mode="json") for finding in draft.findings],
        [
            {
                "evidence_id": record.evidence_id,
                "file_path": record.file_path,
                "start_line": record.start_line,
                "end_line": record.end_line,
            }
            for record in context.evidence
        ],
        [state.model_dump(mode="json") for state in agent_states],
        tags=["request-response-only"],
    )

    check = next(item for item in score.checks if item.name == "generic_request_response_not_framework")
    assert check.passed is True


def test_quality_summary_artifacts_are_compact_and_human_readable(tmp_path: Path) -> None:
    dataset = load_dataset_definition(Path("evaluation/datasets/v3_5_fixtures.json"))
    registry = EvaluationRunRegistry(
        tmp_path,
        dataset.metadata,
        engine="v3_multi_agent",
        mode="mock",
    )
    registry.add_repo(
        repo_id="fixture",
        repo_name="fixtures/example",
        repo_url="fixture://example",
        started_at="2026-06-11T12:00:00+00:00",
        ended_at="2026-06-11T12:00:01+00:00",
        duration_seconds=1.0,
        status="completed",
        passed=True,
        report_markdown="# Executive Summary\nDone.\n",
        findings=[],
        evidence_refs=[],
        agent_states=[],
        quality_metrics={
            "aggregate_score": 87.5,
            "passed": False,
            "failed_checks": ["action_plan_present"],
            "dimensions": [{"name": "readability", "score": 80.0}],
            "checks": [],
        },
    )

    _write_quality_summary(registry)

    payload = json.loads((registry.output_dir / "quality-summary.json").read_text(encoding="utf-8"))
    markdown = (registry.output_dir / "quality-summary.md").read_text(encoding="utf-8")
    assert payload["aggregate_score"] == 87.5
    assert payload["repos"][0]["failed_checks"] == ["action_plan_present"]
    assert "87.50/100" in markdown
    assert "action_plan_present" in markdown
