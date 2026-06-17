from evaluation.report_quality import run_report_quality_evaluation


def test_v3_4_deterministic_report_quality_suite_passes() -> None:
    evaluation = run_report_quality_evaluation()

    assert evaluation.passed
    assert evaluation.version == "3.4"
    assert {check.name for check in evaluation.checks} == {
        "flask_not_cli_only",
        "production_recommendations_first",
        "readable_cycle_groups",
        "agent_summary_visible",
        "actionable_recommendations",
        "evidence_grounding",
        "readable_and_bounded",
        "self_contained_evidence_appendix",
    }
    assert all(check.details for check in evaluation.checks)


def test_v3_4_quality_report_is_machine_and_human_readable() -> None:
    evaluation = run_report_quality_evaluation()

    payload = evaluation.to_dict()
    markdown = evaluation.to_markdown()

    assert payload["summary"] == {"passed": 8, "failed": 0, "total": 8}
    assert payload["report_characters"] <= 30_000
    assert "# CodePilot V3.4 Report Quality Evaluation" in markdown
    assert "| flask_not_cli_only | PASS |" in markdown
