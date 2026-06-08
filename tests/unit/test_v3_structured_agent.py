from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.agents.architecture_agent import ArchitectureAgent
from backend.agents.finding_validator import FindingValidator
from backend.core.config import Settings
from backend.core.report_contract import REPORT_SECTIONS
from backend.llm.client import MockLLMClient, build_llm_client
from backend.llm.structured import StructuredLLMClient
from backend.models.context import EvidenceRecord
from backend.models.structured_review import RawLLMFinding
from backend.reviewers.markdown_adapter import MarkdownReviewAdapter
from backend.reviewers.report_generator import ReportGenerator
from backend.services.evidence import stable_evidence_id


class StaticLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = 0

    def generate_review(self, prompt: str) -> str:
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


def context_with_evidence(sample_context):
    context = sample_context.to_review_context()
    evidence_id = stable_evidence_id("app.py", 1, 2, "def create_app():\n    return App()")
    context.evidence = [
        EvidenceRecord(
            evidence_id=evidence_id,
            file_path="app.py",
            start_line=1,
            end_line=2,
            snippet="def create_app():\n    return App()",
            kind="symbol",
            symbols=["create_app"],
        )
    ]
    context.file_summaries[0].evidence_ids = [evidence_id]
    return context


def test_structured_llm_retries_invalid_output_and_filters_evidence() -> None:
    allowed = stable_evidence_id("app.py", 1, 1, "def run(): pass")
    blocked = stable_evidence_id("other.py", 1, 1, "def other(): pass")
    llm = StaticLLM(
        [
            "not json",
            json.dumps(
                {
                    "findings": [
                        {
                            "title": "Boundary",
                            "description": "Architecture evidence exists.",
                            "category": "architecture",
                            "severity": "medium",
                            "confidence": 0.8,
                            "recommendation": "Add contract tests.",
                            "evidence_ids": [allowed, blocked],
                        }
                    ]
                }
            ),
        ]
    )

    result = StructuredLLMClient(llm, max_retries=1).generate_findings("", allowed_evidence_ids={allowed})

    assert llm.calls == 2
    assert result.invalid_attempts == 1
    assert result.findings[0].evidence_ids == [allowed]


def test_finding_validator_resolves_files_from_evidence_only(sample_context) -> None:
    context = context_with_evidence(sample_context)
    evidence_id = context.evidence[0].evidence_id
    raw = RawLLMFinding(
        title="Boundary",
        description="Do not trust raw file fields.",
        category="architecture",
        severity="medium",
        confidence=0.7,
        recommendation="Use the resolved evidence.",
        evidence_ids=[evidence_id],
    )

    finding = FindingValidator(context).validate(raw, section=REPORT_SECTIONS[0])

    assert finding is not None
    assert finding.files == ["app.py"]
    assert finding.evidence_ids == [evidence_id]
    assert "app.py:1-2" in finding.evidence[0]


def test_architecture_agent_uses_mock_structured_findings(sample_context) -> None:
    context = context_with_evidence(sample_context)

    draft = ArchitectureAgent(MockLLMClient()).review(context)

    assert len(draft.findings) == 1
    assert draft.findings[0].section == REPORT_SECTIONS[0]
    assert draft.findings[0].evidence_ids == [context.evidence[0].evidence_id]


def test_v3_single_agent_report_preserves_four_sections(sample_context, tmp_path: Path) -> None:
    context = context_with_evidence(sample_context)
    generator = ReportGenerator(MockLLMClient(), tmp_path, 8000)
    generator.configure_engine("v3_single_agent")

    result = generator.generate("task-v3", context)

    sections = MarkdownReviewAdapter.extract_sections(result.report)
    assert list(sections) == REPORT_SECTIONS
    assert context.evidence[0].evidence_id in result.report
    assert result.export_path.exists()


def test_real_llm_requires_explicit_enable_flag() -> None:
    settings = Settings(USE_MOCK_LLM=False, ENABLE_REAL_LLM=False, OPENAI_API_KEY="test")

    with pytest.raises(RuntimeError, match="ENABLE_REAL_LLM"):
        build_llm_client(settings)
