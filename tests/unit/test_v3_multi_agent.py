from __future__ import annotations

from pathlib import Path

from backend.agents.evidence_agent import EvidenceGroundedAgent
from backend.agents.orchestrator import AgentOrchestrator
from backend.agents.specialized_agents import CodeSmellAgent
from backend.core.report_contract import REPORT_SECTIONS
from backend.llm.client import MockLLMClient
from backend.models.context import EvidenceRecord
from backend.models.structured_review import ReviewFinding
from backend.reviewers.markdown_adapter import MarkdownReviewAdapter
from backend.reviewers.report_generator import ReportGenerator
from backend.services.evidence import stable_evidence_id


class FailingAgent(EvidenceGroundedAgent):
    role = "FailingAgent"

    def review(self, context):
        raise RuntimeError("agent failed")


def context_with_two_evidence_records(sample_context):
    context = sample_context.to_review_context()
    first = stable_evidence_id("app.py", 1, 2, "def create_app():\n    return App()")
    second = stable_evidence_id("services/review.py", 1, 2, "def review():\n    pass")
    context.evidence = [
        EvidenceRecord(
            evidence_id=first,
            file_path="app.py",
            start_line=1,
            end_line=2,
            snippet="def create_app():\n    return App()",
            kind="symbol",
            symbols=["create_app"],
        ),
        EvidenceRecord(
            evidence_id=second,
            file_path="services/review.py",
            start_line=1,
            end_line=2,
            snippet="def review():\n    pass",
            kind="symbol",
            symbols=["review"],
        ),
    ]
    return context


def test_orchestrator_isolates_agent_failures(sample_context) -> None:
    context = context_with_two_evidence_records(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_classes=[FailingAgent, CodeSmellAgent],
    )

    result = orchestrator.review(context)

    assert result.errors == {"FailingAgent": "agent failed"}
    assert len(result.draft.findings) == 1
    assert result.draft.findings[0].section == REPORT_SECTIONS[1]
    assert [(state.agent_id, state.status) for state in result.agent_states] == [
        ("FailingAgent", "failed"),
        ("CodeSmellAgent", "completed"),
    ]
    assert result.agent_states[0].validation_status == "failed"
    assert result.agent_states[1].validation_status == "validated"


def test_dedup_keeps_unrelated_findings_with_same_title() -> None:
    first = ReviewFinding(
        section=REPORT_SECTIONS[1],
        title="Shared title",
        description="First",
        category="code_smell",
        confidence=0.4,
        evidence_ids=["ev_first"],
    )
    stronger_duplicate = first.model_copy(update={"confidence": 0.9})
    unrelated = first.model_copy(update={"description": "Second", "evidence_ids": ["ev_second"]})

    deduplicated = AgentOrchestrator._deduplicate([first, stronger_duplicate, unrelated])

    assert len(deduplicated) == 2
    assert deduplicated[0].confidence == 0.9
    assert {finding.evidence_ids[0] for finding in deduplicated} == {"ev_first", "ev_second"}


def test_multi_agent_mock_generates_one_grounded_finding_per_section(sample_context) -> None:
    context = context_with_two_evidence_records(sample_context)

    result = AgentOrchestrator(MockLLMClient()).review(context)

    assert not result.errors
    assert result.state is not None
    assert result.state.task_id is None
    assert {finding.section for finding in result.draft.findings} == set(REPORT_SECTIONS)
    assert result.state.validated_findings == result.draft.findings
    assert all(finding.evidence_ids for finding in result.draft.findings)
    assert {state.agent_id for state in result.agent_states} == {
        "ArchitectureAgent",
        "CodeSmellAgent",
        "MaintainabilityAgent",
        "RefactorAgent",
    }
    assert all(state.status == "completed" for state in result.agent_states)
    assert all(state.evidence_ids for state in result.agent_states)


def test_v3_multi_agent_report_preserves_contract_and_evidence(sample_context, tmp_path: Path) -> None:
    context = context_with_two_evidence_records(sample_context)
    generator = ReportGenerator(MockLLMClient(), tmp_path, 8000)
    generator.configure_engine("v3_multi_agent")

    result = generator.generate("task-multi", context)

    assert list(MarkdownReviewAdapter.extract_sections(result.report)) == REPORT_SECTIONS
    assert all(section in result.report for section in REPORT_SECTIONS)
    assert "# Executive Summary" in result.report
    assert "# Action Plan" in result.report
    assert "# Evidence Appendix" in result.report
    assert context.evidence[0].evidence_id in result.report
    assert result.export_path.exists()
