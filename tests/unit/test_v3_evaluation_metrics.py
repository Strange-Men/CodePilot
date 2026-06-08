from __future__ import annotations

import pytest

from backend.models.structured_review import ReviewFinding
from evaluation.metrics import (
    compute_agent_metrics,
    compute_finding_quality_metrics,
    compute_hallucination_metrics,
    v3_metrics_to_dict,
)


def finding(**overrides) -> ReviewFinding:
    values = {
        "section": "Architecture Summary",
        "title": "Grounded finding",
        "description": "A specific issue.",
        "severity": "medium",
        "category": "architecture",
        "confidence": 0.8,
        "files": ["app.py"],
        "recommendation": "Add a boundary test.",
        "evidence_ids": ["ev_valid"],
    }
    values.update(overrides)
    return ReviewFinding(**values)


def test_hallucination_metrics_measure_valid_and_unsupported_evidence() -> None:
    metrics = compute_hallucination_metrics(
        [
            finding(evidence_ids=["ev_valid"]),
            finding(evidence_ids=["ev_missing"]),
            finding(evidence_ids=[]),
        ],
        {"ev_valid"},
    )

    assert metrics.evidence_validity == pytest.approx(0.5)
    assert metrics.unsupported_claim_rate == pytest.approx(2 / 3)
    assert metrics.grounding_score == pytest.approx((0.5 + 1 / 3) / 2)


def test_quality_metrics_measure_actionability_specificity_and_confidence() -> None:
    metrics = compute_finding_quality_metrics(
        [
            finding(severity="high", confidence=0.9),
            finding(files=[], recommendation=None, severity="low", confidence=0.3),
        ]
    )

    assert metrics.actionability == pytest.approx(0.5)
    assert metrics.specificity == pytest.approx(0.5)
    assert metrics.average_confidence == pytest.approx(0.6)
    assert metrics.severity_distribution == {"high": 1, "low": 1}


def test_agent_metrics_are_json_serializable() -> None:
    metrics = compute_agent_metrics({"ArchitectureAgent": [finding()]}, {"ev_valid"})

    as_dict = v3_metrics_to_dict(metrics)

    assert as_dict[0]["agent_name"] == "ArchitectureAgent"
    assert as_dict[0]["hallucination"]["grounding_score"] == 1.0
    assert as_dict[0]["quality"]["actionability"] == 1.0
