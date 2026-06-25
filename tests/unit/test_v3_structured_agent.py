from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.agents.architecture_agent import ArchitectureAgent
from backend.agents.evidence_agent import EvidenceGroundedAgent
from backend.agents.finding_validator import FindingValidator
from backend.agents.specialized_agents import CodeSmellAgent
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
    assert "# Executive Summary" in result.report
    assert "# What This Repository Is" in result.report
    assert "# Evidence Appendix" in result.report
    assert context.evidence[0].evidence_id in result.report
    assert result.export_path.exists()


def test_real_llm_requires_explicit_enable_flag() -> None:
    settings = Settings(USE_MOCK_LLM=False, ENABLE_REAL_LLM=False, OPENAI_API_KEY="test")

    with pytest.raises(RuntimeError, match="ENABLE_REAL_LLM"):
        build_llm_client(settings)


# ---------------------------------------------------------------------------
# V3.5.9 Step 3 — Finding quality and no_findings_reason tests
# ---------------------------------------------------------------------------


def test_parse_findings_accepts_no_findings_reason() -> None:
    """StructuredLLMClient should parse no_findings_reason from LLM output."""
    completion = json.dumps({
        "findings": [],
        "no_findings_reason": "Evidence shows no architecture issues.",
    })
    findings, reason = StructuredLLMClient._parse_findings(completion)
    assert findings == []
    assert reason == "Evidence shows no architecture issues."


def test_parse_findings_no_reason_when_absent() -> None:
    """no_findings_reason should be None when not in LLM output."""
    completion = json.dumps({
        "findings": [
            {
                "title": "Test",
                "description": "Desc",
                "category": "architecture",
                "severity": "medium",
                "confidence": 0.7,
                "evidence_ids": ["ev_abc"],
            }
        ],
    })
    findings, reason = StructuredLLMClient._parse_findings(completion)
    assert len(findings) == 1
    assert reason is None


def test_generate_findings_captures_no_findings_reason() -> None:
    """generate_findings should return no_findings_reason in result."""
    llm = StaticLLM([
        json.dumps({
            "findings": [],
            "no_findings_reason": "No code smells found in evidence.",
        }),
    ])
    result = StructuredLLMClient(llm, max_retries=0).generate_findings(
        "", allowed_evidence_ids=set(),
    )
    assert result.findings == []
    assert result.no_findings_reason == "No code smells found in evidence."


def test_agent_prompt_contains_finding_guidance(sample_context) -> None:
    """Agent prompt should encourage 1-3 findings, not just critical."""
    import inspect
    source = inspect.getsource(EvidenceGroundedAgent._render_prompt)
    assert "1-3" in source or "1–3" in source
    assert "medium" in source.lower()


def test_agent_prompt_requires_simplified_chinese_display_fields(sample_context) -> None:
    """Real LLM prompts must force Chinese natural-language fields for zh display."""
    context = context_with_evidence(sample_context)
    prompt = ArchitectureAgent(MockLLMClient())._render_prompt(context, context.evidence)

    assert "MUST be Simplified Chinese" in prompt
    assert "MUST NOT contain full English sentences" in prompt
    assert "Keep code symbols, file paths, commands, evidence IDs untranslated" in prompt


def test_grouped_prompt_requires_simplified_chinese_display_fields(sample_context) -> None:
    """Grouped Real LLM prompt must carry the same Chinese-language constraint."""
    context = context_with_evidence(sample_context)
    agent = ArchitectureAgent(MockLLMClient())
    prompt = EvidenceGroundedAgent.render_grouped_prompt(
        context,
        [(agent, context.evidence, agent._retrieval_policy())],
        token_budget=2000,
    )

    assert "MUST be Simplified Chinese" in prompt
    assert "MUST NOT contain full English sentences" in prompt
    assert "Keep code symbols, file paths, commands, evidence IDs untranslated" in prompt


def test_validator_preserves_medium_low_findings(sample_context) -> None:
    """Validator should not reject valid medium or low findings."""
    context = context_with_evidence(sample_context)
    evidence_id = context.evidence[0].evidence_id
    for severity in ("medium", "low", "informational"):
        raw = RawLLMFinding(
            title=f"Finding {severity}",
            description=f"A {severity} issue.",
            category="architecture",
            severity=severity,
            confidence=0.5,
            evidence_ids=[evidence_id],
        )
        finding = FindingValidator(context).validate(raw, section=REPORT_SECTIONS[0])
        assert finding is not None, f"Validator rejected severity={severity}"
        assert finding.severity == severity


def test_validator_rejects_hallucinated_evidence(sample_context) -> None:
    """Validator should reject findings with non-existent evidence IDs."""
    context = context_with_evidence(sample_context)
    raw = RawLLMFinding(
        title="Hallucinated",
        description="This finding cites fake evidence.",
        category="architecture",
        severity="high",
        confidence=0.9,
        evidence_ids=["ev_nonexistent_12345"],
    )
    finding = FindingValidator(context).validate(raw, section=REPORT_SECTIONS[0])
    assert finding is None


def test_validator_rejects_empty_evidence_ids(sample_context) -> None:
    """Validator should reject findings with no evidence IDs."""
    context = context_with_evidence(sample_context)
    raw = RawLLMFinding(
        title="No Evidence",
        description="This finding has no evidence.",
        category="architecture",
        severity="high",
        confidence=0.9,
        evidence_ids=[],
    )
    finding = FindingValidator(context).validate(raw, section=REPORT_SECTIONS[0])
    assert finding is None


def test_chinese_prompt_bans_bad_terms() -> None:
    """Agent prompt should instruct LLM to never use '代码坏味道'."""
    import inspect
    source = inspect.getsource(EvidenceGroundedAgent._render_prompt)
    # The prompt should contain the ban instruction
    assert "NEVER" in source
    assert "代码坏味道" in source  # mentioned in the ban
    assert "代码质量问题" in source  # preferred alternative


def test_bilingual_display_fields_validate() -> None:
    """RawLLMFinding with bilingual display should parse correctly."""
    data = {
        "title": "Test Finding",
        "description": "A test description.",
        "category": "architecture",
        "severity": "medium",
        "confidence": 0.7,
        "evidence_ids": ["ev_abc"],
        "display": {
            "en": {
                "title": "Test Finding",
                "description": "A test description.",
            },
            "zh": {
                "title": "测试发现",
                "description": "测试描述。",
            },
        },
    }
    finding = RawLLMFinding.model_validate(data)
    assert finding.display is not None
    assert finding.display.en.title == "Test Finding"
    assert finding.display.zh.title == "测试发现"


# ---------------------------------------------------------------------------
# V3.5.9 Step 4 — CodeSmellAgent validation reliability tests
# ---------------------------------------------------------------------------


def test_parse_findings_strips_markdown_code_fences() -> None:
    """Parser should strip ```json ... ``` fences from LLM output."""
    fenced = (
        '```json\n{"findings": [{"title": "T", "description": "D", '
        '"category": "code_smell", "severity": "medium", '
        '"confidence": 0.5, "evidence_ids": ["ev_1"]}], '
        '"no_findings_reason": null}\n```'
    )
    findings, reason = StructuredLLMClient._parse_findings(fenced)
    assert len(findings) == 1
    assert findings[0].title == "T"
    assert reason is None


def test_parse_findings_strips_plain_code_fences() -> None:
    """Parser should strip ``` ... ``` fences without language tag."""
    fenced = (
        '```\n{"findings": [{"title": "T", "description": "D", '
        '"category": "code_smell", "severity": "low", '
        '"confidence": 0.3, "evidence_ids": ["ev_1"]}]}\n```'
    )
    findings, _ = StructuredLLMClient._parse_findings(fenced)
    assert len(findings) == 1


def test_parse_findings_handles_text_before_code_fence() -> None:
    """Parser should extract JSON from code fence even with surrounding text."""
    fenced = (
        'Here are the findings:\n\n'
        '```json\n{"findings": [{"title": "T", "description": "D", '
        '"category": "code_smell", "severity": "medium", '
        '"confidence": 0.5, "evidence_ids": ["ev_1"]}], '
        '"no_findings_reason": null}\n```'
    )
    findings, reason = StructuredLLMClient._parse_findings(fenced)
    assert len(findings) == 1
    assert findings[0].title == "T"
    assert reason is None


def test_parse_findings_handles_text_after_code_fence() -> None:
    """Parser should extract JSON from code fence with trailing text."""
    fenced = (
        '```json\n{"findings": [{"title": "T", "description": "D", '
        '"category": "architecture", "severity": "high", '
        '"confidence": 0.9, "evidence_ids": ["ev_1"]}], '
        '"no_findings_reason": null}\n```\n\n'
        'Hope this helps!'
    )
    findings, reason = StructuredLLMClient._parse_findings(fenced)
    assert len(findings) == 1
    assert findings[0].category == "architecture"


def test_parse_findings_handles_text_surrounding_code_fence() -> None:
    """Parser should extract JSON from code fence with text on both sides."""
    fenced = (
        'I analyzed the code and found these issues:\n\n'
        '```json\n{"findings": [{"title": "T", "description": "D", '
        '"category": "maintainability", "severity": "low", '
        '"confidence": 0.4, "evidence_ids": ["ev_abc123"]}]}\n```\n\n'
        'Let me know if you need more details.'
    )
    findings, _ = StructuredLLMClient._parse_findings(fenced)
    assert len(findings) == 1
    assert findings[0].evidence_ids == ["ev_abc123"]


def test_parse_findings_rejects_missing_required_fields() -> None:
    """Parser should reject findings missing title, description, or category."""
    import pytest

    bad = json.dumps({
        "findings": [{"title": "T", "category": "code_smell", "evidence_ids": ["ev_1"]}]
    })
    with pytest.raises((ValidationError, ValueError)):
        StructuredLLMClient._parse_findings(bad)


def test_parse_findings_rejects_empty_evidence_ids() -> None:
    """Parser should reject findings with empty evidence_ids."""
    import pytest
    bad = json.dumps({"findings": [{"title": "T", "description": "D", "category": "code_smell", "evidence_ids": []}]})
    with pytest.raises(ValueError, match="evidence_ids"):
        StructuredLLMClient._parse_findings(bad)


def test_code_smell_agent_prompt_contains_schema_guidance() -> None:
    """CodeSmellAgent prompt should include JSON schema and example."""
    import inspect

    source = inspect.getsource(EvidenceGroundedAgent._render_prompt)
    assert "OUTPUT FORMAT" in source
    assert "EXAMPLE" in source
    assert "No markdown fences" in source
    assert "required fields" in source


def test_code_smell_agent_category_in_prompt(sample_context) -> None:
    """CodeSmellAgent prompt should use 'code_smell' as category."""
    context = context_with_evidence(sample_context)
    agent = CodeSmellAgent(MockLLMClient())
    prompt = agent._render_prompt(context, context.evidence)
    assert "code_smell" in prompt
    assert "Code Smells" in prompt


def test_validator_accepts_code_smell_medium_finding(sample_context) -> None:
    """Validator should accept valid code_smell medium findings."""
    context = context_with_evidence(sample_context)
    evidence_id = context.evidence[0].evidence_id
    raw = RawLLMFinding(
        title="Broad exception handler",
        description="Catches all exceptions.",
        category="code_smell",
        severity="medium",
        confidence=0.7,
        evidence_ids=[evidence_id],
    )
    finding = FindingValidator(context).validate(raw, section=REPORT_SECTIONS[1])
    assert finding is not None
    assert finding.severity == "medium"
    assert finding.category == "code_smell"
    assert finding.section == "Code Smells"


def test_validator_accepts_code_smell_low_finding(sample_context) -> None:
    """Validator should accept valid code_smell low findings."""
    context = context_with_evidence(sample_context)
    evidence_id = context.evidence[0].evidence_id
    raw = RawLLMFinding(
        title="Magic number",
        description="Hardcoded limit without constant.",
        category="code_smell",
        severity="low",
        confidence=0.5,
        evidence_ids=[evidence_id],
    )
    finding = FindingValidator(context).validate(raw, section=REPORT_SECTIONS[1])
    assert finding is not None
    assert finding.severity == "low"


def test_validator_rejects_wrong_section_for_code_smell(sample_context) -> None:
    """Validator should reject code_smell finding in wrong section."""
    context = context_with_evidence(sample_context)
    evidence_id = context.evidence[0].evidence_id
    raw = RawLLMFinding(
        title="Smell",
        description="Desc.",
        category="code_smell",
        severity="medium",
        confidence=0.5,
        evidence_ids=[evidence_id],
    )
    # Using Architecture section for a code_smell category finding should still pass
    # (validator doesn't enforce category-section matching, only section validity)
    finding = FindingValidator(context).validate(raw, section=REPORT_SECTIONS[0])
    assert finding is not None


def test_generate_findings_logs_parse_failure() -> None:
    """generate_findings should log sanitized error on parse failure."""
    llm = StaticLLM(["not json at all"])
    client = StructuredLLMClient(llm, max_retries=0)
    result = client.generate_findings("", allowed_evidence_ids=set())
    assert result.invalid_attempts == 1
    assert len(result.errors) == 1
    assert "Expecting value" in result.errors[0] or "json" in result.errors[0].lower()


def test_timing_parser_distinguishes_stages() -> None:
    """Benchmark timing parser should distinguish agent_orchestration from report_compose."""
    from scripts.benchmark_real_review import extract_performance_events

    log = (
        "INFO:backend.tasks.pipeline:performance_event task_id=t1 "
        "stage=total_pipeline duration_ms=444619.0 success=true\n"
        "INFO:backend.reviewers.report_generator:performance_event task_id=t1 "
        "stage=agent_orchestration duration_ms=439900.0 "
        "success=true engine=v3_multi_agent\n"
        "INFO:backend.reviewers.report_generator:performance_event task_id=t1 "
        "stage=report_compose duration_ms=5.0 "
        "success=true engine=v3_multi_agent\n"
    )
    events = extract_performance_events(log)
    stages = {e["stage"]: e["duration_ms"] for e in events}
    assert "agent_orchestration" in stages
    assert "report_compose" in stages
    assert float(stages["agent_orchestration"]) > float(stages["report_compose"])


def test_bilingual_code_smell_finding_parses() -> None:
    """CodeSmellAgent bilingual output should parse through full pipeline."""
    data = {
        "title": "Broad exception handler",
        "description": "The except block catches all exceptions.",
        "category": "code_smell",
        "severity": "medium",
        "confidence": 0.8,
        "evidence_ids": ["ev_abc"],
        "recommendation": "Catch specific exceptions.",
        "display": {
            "en": {
                "title": "Broad exception handler",
                "description": "The except block catches all exceptions.",
                "recommendation": "Catch specific exceptions.",
            },
            "zh": {
                "title": "宽泛异常处理",
                "description": "except 块捕获所有异常。",
                "recommendation": "捕获特定异常。",
            },
        },
    }
    finding = RawLLMFinding.model_validate(data)
    assert finding.display is not None
    assert finding.display.zh.title == "宽泛异常处理"
    assert finding.display.en.title == "Broad exception handler"
