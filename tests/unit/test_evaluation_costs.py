from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.agents.orchestrator import AgentOrchestrator
from backend.llm.client import MockLLMClient
from evaluation.costs import load_pricing_config, summarize_repo_usage
from evaluation.registry import EvaluationRunRegistry, load_dataset_definition
from evaluation.run_eval import _write_cost_summary


def test_repo_usage_estimates_cost_only_for_exact_configured_model(tmp_path: Path) -> None:
    pricing_path = tmp_path / "pricing.json"
    pricing_path.write_text(
        json.dumps(
            {
                "version": "1",
                "currency": "USD",
                "models": {
                    "example-model": {
                        "prompt_per_million_tokens": 2.0,
                        "completion_per_million_tokens": 4.0,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    pricing = load_pricing_config(pricing_path)
    states = [
        {
            "agent_id": "ArchitectureAgent",
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "llm_calls": 2,
            "metadata": {"duration_seconds": 0.25},
        }
    ]

    known = summarize_repo_usage(
        states,
        runtime_seconds=1.5,
        model="example-model",
        pricing=pricing,
    )
    unknown = summarize_repo_usage(
        states,
        runtime_seconds=1.5,
        model="other-model",
        pricing=pricing,
    )

    assert known.total_tokens == 1500
    assert known.estimated_cost == pytest.approx(0.004)
    assert known.currency == "USD"
    assert known.pricing_known is True
    assert known.agents[0].duration_seconds == 0.25
    assert unknown.estimated_cost is None
    assert unknown.currency is None
    assert unknown.pricing_known is False


def test_agent_orchestrator_records_per_agent_duration(sample_context) -> None:
    state = AgentOrchestrator(MockLLMClient()).review(sample_context.to_review_context())

    assert state.agent_states
    assert all(float(agent.metadata["duration_seconds"]) >= 0 for agent in state.agent_states)


def test_cost_summary_reports_unknown_cost_without_pricing(tmp_path: Path) -> None:
    dataset = load_dataset_definition(Path("evaluation/datasets/v3_5_fixtures.json"))
    registry = EvaluationRunRegistry(
        tmp_path,
        dataset.metadata,
        engine="v3_multi_agent",
        mode="real",
        provider="openai",
        model="unpriced-model",
    )
    usage = summarize_repo_usage(
        [
            {
                "agent_id": "ArchitectureAgent",
                "prompt_tokens": 120,
                "completion_tokens": 30,
                "llm_calls": 1,
                "metadata": {"duration_seconds": 0.2},
            }
        ],
        runtime_seconds=1.0,
        model="unpriced-model",
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
        report_markdown="",
        findings=[],
        evidence_refs=[],
        agent_states=[],
        usage=usage.to_dict(),
    )

    _write_cost_summary(registry)

    payload = json.loads((registry.output_dir / "cost-summary.json").read_text(encoding="utf-8"))
    markdown = (registry.output_dir / "cost-summary.md").read_text(encoding="utf-8")
    assert payload["total_tokens"] == 150
    assert payload["estimated_cost"] is None
    assert payload["priced_repos"] == 0
    assert "Unknown (no matching pricing configured)" in markdown
