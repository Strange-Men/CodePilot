from __future__ import annotations

from backend.models.context import EvidenceRecord
from backend.models.review_state import AgentExecutionState, ReviewState
from backend.models.structured_review import ReviewFinding


def test_review_state_safe_snapshot_excludes_evidence_snippets(sample_context) -> None:
    context = sample_context.to_review_context()
    context.evidence = [
        EvidenceRecord(
            evidence_id="ev_safe",
            file_path="app.py",
            start_line=1,
            end_line=2,
            snippet="password=super-secret",
            kind="symbol",
            symbols=["create_app"],
        )
    ]
    finding = ReviewFinding(
        section="Architecture Summary",
        description="Validated finding.",
        evidence_ids=["ev_safe"],
    )
    state = ReviewState(
        task_id="task-1",
        context=context,
        evidence_bundles={"ArchitectureAgent": context.evidence},
        agent_results=[
            AgentExecutionState(
                agent_id="ArchitectureAgent",
                status="completed",
                findings=[finding],
                evidence_ids=["ev_safe"],
            )
        ],
        validated_findings=[finding],
    )

    snapshot = state.safe_snapshot()
    payload = snapshot.model_dump_json()
    assert snapshot.evidence_index[0].evidence_id == "ev_safe"
    assert snapshot.evidence_bundles == {"ArchitectureAgent": ["ev_safe"]}
    assert "snippet" not in payload
    assert "super-secret" not in payload
