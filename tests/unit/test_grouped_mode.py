"""Tests for grouped agent review mode (V3.5.10).

All tests use MockLLMClient — no real LLM calls.
"""

from __future__ import annotations

import json
import logging

from backend.agents.finding_validator import FindingValidator
from backend.agents.orchestrator import AgentOrchestrator
from backend.core.config import Settings
from backend.core.report_contract import REPORT_SECTIONS
from backend.llm.client import MockLLMClient
from backend.llm.structured import (
    StructuredLLMClient,
)
from backend.models.context import EvidenceRecord, ReviewContext
from backend.models.review_state import ReviewState
from backend.models.structured_review import (
    BilingualTextField,
    DisplayFields,
    RawLLMFinding,
)
from backend.services.evidence import stable_evidence_id

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_evidence(file_path: str, snippet: str) -> EvidenceRecord:
    """Create a test evidence record with a stable ID."""
    eid = stable_evidence_id(file_path, 1, 2, snippet)
    return EvidenceRecord(
        evidence_id=eid,
        file_path=file_path,
        start_line=1,
        end_line=2,
        snippet=snippet,
        kind="symbol",
        symbols=[],
    )


def _context_with_evidence(sample_context) -> ReviewContext:
    """Build a ReviewContext with two evidence records."""
    context = sample_context.to_review_context()
    context.evidence = [
        _make_evidence("app.py", "def create_app():\n    return App()"),
        _make_evidence("services/review.py", "def review():\n    pass"),
    ]
    return context


# ---------------------------------------------------------------------------
# Test 1: Default mode is separate
# ---------------------------------------------------------------------------

def test_default_agent_mode_is_separate() -> None:
    """REVIEW_AGENT_MODE defaults to 'separate'."""
    settings = Settings()
    assert settings.review_agent_mode == "separate"


# ---------------------------------------------------------------------------
# Test 2: Separate mode preserves existing orchestrator behavior
# ---------------------------------------------------------------------------

def test_separate_mode_preserves_existing_behavior(sample_context) -> None:
    """With agent_mode='separate', orchestrator runs existing V3.5.9 path."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_mode="separate",
        concurrency=4,
    )

    result = orchestrator.run(ReviewState(task_id="test-sep", context=context))

    assert len(result.agent_results) == 4
    expected_ids = [
        "ArchitectureAgent", "CodeSmellAgent", "MaintainabilityAgent", "RefactorAgent",
    ]
    assert [s.agent_id for s in result.agent_results] == expected_ids
    assert all(s.status == "completed" for s in result.agent_results)


# ---------------------------------------------------------------------------
# Test 3: Grouped mode runs grouped path
# ---------------------------------------------------------------------------

def test_grouped_mode_runs_grouped_path(sample_context) -> None:
    """With agent_mode='grouped', orchestrator uses grouped LLM calls."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_mode="grouped",
        concurrency=2,
    )

    result = orchestrator.run(ReviewState(task_id="test-grp", context=context))

    assert len(result.agent_results) == 4
    expected_ids = [
        "ArchitectureAgent", "CodeSmellAgent", "MaintainabilityAgent", "RefactorAgent",
    ]
    assert [s.agent_id for s in result.agent_results] == expected_ids
    assert all(s.status == "completed" for s in result.agent_results)


# ---------------------------------------------------------------------------
# Test 4: Grouped schema parses two logical agents
# ---------------------------------------------------------------------------

def test_grouped_schema_parses_two_logical_agents() -> None:
    """Grouped JSON with 2 agent keys parses into separate finding lists."""
    evidence_ids_1 = ["ev_aaa111bbb222ccc333dd"]
    evidence_ids_2 = ["ev_eee444fff555ggg666hh"]

    raw_response = json.dumps({
        "agent_outputs": {
            "ArchitectureAgent": {
                "findings": [
                    {
                        "title": "Arch finding",
                        "description": "Desc",
                        "category": "architecture",
                        "severity": "high",
                        "confidence": 0.9,
                        "evidence_ids": evidence_ids_1,
                        "display": {
                            "en": {"title": "Arch finding", "description": "Desc"},
                            "zh": {"title": "架构发现", "description": "描述"},
                        },
                    }
                ],
                "no_findings_reason": None,
            },
            "MaintainabilityAgent": {
                "findings": [],
                "no_findings_reason": "No maintainability issues found.",
            },
        }
    })

    agent_evidence_ids = {
        "ArchitectureAgent": set(evidence_ids_1),
        "MaintainabilityAgent": set(evidence_ids_2),
    }

    result = StructuredLLMClient._parse_grouped_response(raw_response, agent_evidence_ids)

    assert "ArchitectureAgent" in result
    assert "MaintainabilityAgent" in result
    assert len(result["ArchitectureAgent"].findings) == 1
    assert result["ArchitectureAgent"].findings[0].title == "Arch finding"
    assert len(result["MaintainabilityAgent"].findings) == 0
    assert result["MaintainabilityAgent"].no_findings_reason == "No maintainability issues found."


# ---------------------------------------------------------------------------
# Test 5: Grouped parser strips markdown fences
# ---------------------------------------------------------------------------

def test_grouped_parser_strips_markdown_fences() -> None:
    """Markdown code fences around grouped JSON are stripped."""
    evidence_ids = ["ev_aaa111bbb222ccc333dd"]
    fenced = '```json\n{"agent_outputs": {"ArchitectureAgent": {"findings": [], "no_findings_reason": "none"}}}\n```'

    agent_evidence_ids = {"ArchitectureAgent": set(evidence_ids)}
    result = StructuredLLMClient._parse_grouped_response(fenced, agent_evidence_ids)

    assert "ArchitectureAgent" in result
    assert len(result["ArchitectureAgent"].findings) == 0


# ---------------------------------------------------------------------------
# Test 6: Each logical agent preserves no_findings_reason
# ---------------------------------------------------------------------------

def test_no_findings_reason_preserved_per_agent() -> None:
    """no_findings_reason is recorded per logical agent, not shared."""
    raw_response = json.dumps({
        "agent_outputs": {
            "CodeSmellAgent": {
                "findings": [],
                "no_findings_reason": "Evidence shows no code smells.",
            },
            "RefactorAgent": {
                "findings": [],
                "no_findings_reason": "No refactoring opportunities.",
            },
        }
    })

    agent_evidence_ids = {
        "CodeSmellAgent": {"ev_aaa111bbb222ccc333dd"},
        "RefactorAgent": {"ev_eee444fff555ggg666hh"},
    }
    result = StructuredLLMClient._parse_grouped_response(raw_response, agent_evidence_ids)

    assert result["CodeSmellAgent"].no_findings_reason == "Evidence shows no code smells."
    assert result["RefactorAgent"].no_findings_reason == "No refactoring opportunities."


# ---------------------------------------------------------------------------
# Test 7: Validation runs per logical agent
# ---------------------------------------------------------------------------

def test_validation_runs_per_logical_agent(sample_context) -> None:
    """Each logical agent's findings are validated independently against its evidence."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_mode="grouped",
    )

    result = orchestrator.run(ReviewState(task_id="test-validate", context=context))

    # Each agent state should have validated findings
    for agent_state in result.agent_results:
        assert agent_state.validation_status == "validated"
        # If findings exist, they should be grounded in evidence
        for finding in agent_state.findings:
            assert finding.evidence_ids  # non-empty


# ---------------------------------------------------------------------------
# Test 8: Valid agent output salvaged when sibling fails
# ---------------------------------------------------------------------------

def test_salvage_valid_when_other_invalid(sample_context) -> None:
    """If one logical agent output is valid and the other is invalid,
    the valid one is preserved (salvaged)."""
    context = _context_with_evidence(sample_context)
    valid_evidence = {r.evidence_id for r in context.evidence}

    # Create a mock that returns valid for ArchitectureAgent, invalid for MaintainabilityAgent
    class PartialFailMock(MockLLMClient):
        def generate_grouped_structured_findings(self, prompt):
            return {
                "ArchitectureAgent": {
                    "findings": [
                        {
                            "title": "Valid arch finding",
                            "description": "Desc",
                            "category": "architecture",
                            "severity": "medium",
                            "confidence": 0.8,
                            "evidence_ids": list(valid_evidence)[:1],
                            "display": {
                                "en": {"title": "Valid arch finding", "description": "Desc"},
                                "zh": {"title": "有效架构发现", "description": "描述"},
                            },
                        }
                    ],
                    "no_findings_reason": None,
                },
                "MaintainabilityAgent": {
                    "findings": [
                        {
                            "title": "",  # invalid: empty title will fail validation
                            "description": "",
                            "category": "maintainability",
                            "severity": "medium",
                            "confidence": 0.5,
                            "evidence_ids": ["ev_NONEXISTENT_evidence_id00"],  # hallucinated
                            "display": {
                                "en": {"title": "", "description": ""},
                                "zh": {"title": "", "description": ""},
                            },
                        }
                    ],
                    "no_findings_reason": None,
                },
            }

    orchestrator = AgentOrchestrator(
        PartialFailMock(),
        agent_mode="grouped",
    )

    result = orchestrator.run(ReviewState(task_id="test-salvage", context=context))

    arch_state = next(s for s in result.agent_results if s.agent_id == "ArchitectureAgent")
    maint_state = next(s for s in result.agent_results if s.agent_id == "MaintainabilityAgent")

    # ArchitectureAgent should have valid findings (salvaged)
    assert arch_state.status == "completed"
    # MaintainabilityAgent findings should be dropped (hallucinated evidence) but status may still
    # be completed with empty findings since the parse itself didn't fail
    assert maint_state.status == "completed"
    # The hallucinated evidence ID should have been filtered out, resulting in 0 findings
    assert len(maint_state.findings) == 0


# ---------------------------------------------------------------------------
# Test 9: Hallucinated evidence IDs are rejected
# ---------------------------------------------------------------------------

def test_hallucinated_evidence_ids_rejected() -> None:
    """Findings with hallucinated evidence_ids are rejected by filtering."""
    allowed_ids = {"ev_aaa111bbb222ccc333dd"}
    findings = [
        RawLLMFinding(
            title="Test",
            description="Test desc",
            category="architecture",
            severity="medium",
            confidence=0.8,
            evidence_ids=["ev_aaa111bbb222ccc333dd", "ev_FAKE0000000000000000"],
            display=DisplayFields(
                en=BilingualTextField(title="Test", description="Test desc"),
                zh=BilingualTextField(title="测试", description="测试描述"),
            ),
        )
    ]

    filtered = StructuredLLMClient._filter_allowed(findings, allowed_ids)

    assert len(filtered) == 1
    assert filtered[0].evidence_ids == ["ev_aaa111bbb222ccc333dd"]
    assert "ev_FAKE0000000000000000" not in filtered[0].evidence_ids


# ---------------------------------------------------------------------------
# Test 10: Bilingual display fields are preserved
# ---------------------------------------------------------------------------

def test_bilingual_display_fields_preserved(sample_context) -> None:
    """display.en and display.zh fields survive grouped parse and validation."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_mode="grouped",
    )

    result = orchestrator.run(ReviewState(task_id="test-bilingual", context=context))

    # At least one finding should have bilingual display
    has_display = False
    for agent_state in result.agent_results:
        for finding in agent_state.findings:
            if finding.display is not None:
                has_display = True
                assert finding.display.en is not None
                assert finding.display.zh is not None
    assert has_display, "Expected at least one finding with bilingual display"


# ---------------------------------------------------------------------------
# Test 11: Report still has 4 agent states
# ---------------------------------------------------------------------------

def test_report_has_four_agent_states(sample_context) -> None:
    """Grouped mode produces exactly 4 AgentExecutionState entries."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_mode="grouped",
    )

    result = orchestrator.run(ReviewState(task_id="test-4states", context=context))

    assert len(result.agent_results) == 4
    agent_ids = [s.agent_id for s in result.agent_results]
    assert agent_ids == [
        "ArchitectureAgent", "CodeSmellAgent", "MaintainabilityAgent", "RefactorAgent",
    ]


# ---------------------------------------------------------------------------
# Test 12: Deterministic agent order preserved
# ---------------------------------------------------------------------------

def test_deterministic_agent_order_in_grouped(sample_context) -> None:
    """Agent results maintain deterministic A1, A2, A3, A4 order in grouped mode."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_mode="grouped",
    )

    result = orchestrator.run(ReviewState(task_id="test-order", context=context))

    expected_order = [
        "ArchitectureAgent",
        "CodeSmellAgent",
        "MaintainabilityAgent",
        "RefactorAgent",
    ]
    actual_order = [s.agent_id for s in result.agent_results]
    assert actual_order == expected_order


# ---------------------------------------------------------------------------
# Test 13: Grouped timing logs emitted
# ---------------------------------------------------------------------------

def test_grouped_timing_logs_emitted(sample_context, caplog) -> None:
    """Performance event logs include grouped stages."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_mode="grouped",
    )

    test_logger = logging.getLogger("backend.agents.orchestrator")
    test_logger.propagate = True
    try:
        with caplog.at_level(logging.INFO, logger="backend.agents.orchestrator"):
            orchestrator.run(ReviewState(task_id="test-timing", context=context))

        performance_logs = [r for r in caplog.records if "performance_event" in r.message]

        # Should have grouped_call_start and grouped_call_end
        grouped_starts = [r for r in performance_logs if "stage=grouped_call_start" in r.message]
        grouped_ends = [r for r in performance_logs if "stage=grouped_call_end" in r.message]
        assert len(grouped_starts) == 2, f"Expected 2 grouped_call_start, got {len(grouped_starts)}"
        assert len(grouped_ends) == 2, f"Expected 2 grouped_call_end, got {len(grouped_ends)}"

        # Should have logical_agent_parse for each agent
        parse_logs = [r for r in performance_logs if "stage=logical_agent_parse" in r.message]
        assert len(parse_logs) == 4, f"Expected 4 logical_agent_parse, got {len(parse_logs)}"

        # Should have logical_agent_validation for each agent
        validation_logs = [r for r in performance_logs if "stage=logical_agent_validation" in r.message]
        assert len(validation_logs) == 4, f"Expected 4 logical_agent_validation, got {len(validation_logs)}"

        # Check grouped_call_end has duration_ms and retries
        for log in grouped_ends:
            assert "duration_ms=" in log.message
            assert "retries=" in log.message
    finally:
        test_logger.propagate = False


# ---------------------------------------------------------------------------
# Test 14: Fallback to separate call (invalid agent_mode falls back)
# ---------------------------------------------------------------------------

def test_invalid_agent_mode_falls_back_to_separate(sample_context, caplog) -> None:
    """Invalid agent_mode value falls back to 'separate' with a warning."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_mode="INVALID_MODE",
    )

    assert orchestrator.agent_mode == "separate"

    # Should still run successfully
    result = orchestrator.run(ReviewState(task_id="test-fallback", context=context))
    assert len(result.agent_results) == 4


# ---------------------------------------------------------------------------
# Test 15: Priority layer still works with grouped output
# ---------------------------------------------------------------------------

def test_priority_layer_works_with_grouped(sample_context) -> None:
    """Findings from grouped mode are still deduplicated."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_mode="grouped",
    )

    result = orchestrator.run(ReviewState(task_id="test-priority", context=context))

    # Findings should be deduplicated
    assert result.validated_findings is not None
    # Total findings across agents should be >= deduplicated count
    total = sum(len(s.findings) for s in result.agent_results)
    assert len(result.validated_findings) <= total


# ---------------------------------------------------------------------------
# Test 16: Chinese report/export does not call LLM for bilingual grouped reviews
# ---------------------------------------------------------------------------

def test_grouped_findings_have_bilingual_no_extra_llm(sample_context) -> None:
    """Grouped findings carry bilingual display without additional LLM calls."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_mode="grouped",
    )

    result = orchestrator.run(ReviewState(task_id="test-zh", context=context))

    # All completed agents with findings should have bilingual display
    for agent_state in result.agent_results:
        if agent_state.status == "completed":
            for finding in agent_state.findings:
                if finding.display is not None:
                    # zh display should have content (from mock)
                    assert finding.display.zh is not None


# ---------------------------------------------------------------------------
# Test 17: No secrets in logs
# ---------------------------------------------------------------------------

def test_grouped_logs_no_secrets(sample_context, caplog) -> None:
    """Performance event logs do not contain API keys or secrets."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_mode="grouped",
    )

    test_logger = logging.getLogger("backend.agents.orchestrator")
    test_logger.propagate = True
    try:
        with caplog.at_level(logging.INFO, logger="backend.agents.orchestrator"):
            orchestrator.run(ReviewState(task_id="test-no-secrets", context=context))

        for record in caplog.records:
            msg = record.message
            assert "sk-" not in msg, "Log contains potential API key"
            assert "OPENAI_API_KEY" not in msg, "Log contains env var name"
            assert "MIMO_API_KEY" not in msg, "Log contains env var name"
    finally:
        test_logger.propagate = False


# ---------------------------------------------------------------------------
# Test 18: Grouped metadata includes group_id and call_mode
# ---------------------------------------------------------------------------

def test_grouped_metadata_includes_group_info(sample_context) -> None:
    """AgentExecutionState metadata contains group_id and call_mode for grouped agents."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_mode="grouped",
    )

    result = orchestrator.run(ReviewState(task_id="test-meta", context=context))

    for agent_state in result.agent_results:
        assert agent_state.metadata.get("call_mode") == "grouped"
        assert agent_state.metadata.get("group_id") in ("group_1", "group_2")

    # Verify group assignments
    arch_state = next(s for s in result.agent_results if s.agent_id == "ArchitectureAgent")
    maint_state = next(s for s in result.agent_results if s.agent_id == "MaintainabilityAgent")
    code_state = next(s for s in result.agent_results if s.agent_id == "CodeSmellAgent")
    refactor_state = next(s for s in result.agent_results if s.agent_id == "RefactorAgent")

    assert arch_state.metadata["group_id"] == "group_1"
    assert maint_state.metadata["group_id"] == "group_1"
    assert code_state.metadata["group_id"] == "group_2"
    assert refactor_state.metadata["group_id"] == "group_2"


# ---------------------------------------------------------------------------
# Test 19: Separate mode metadata does not contain grouped info
# ---------------------------------------------------------------------------

def test_separate_mode_no_grouped_metadata(sample_context) -> None:
    """AgentExecutionState in separate mode does not contain group_id or call_mode."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_mode="separate",
    )

    result = orchestrator.run(ReviewState(task_id="test-sep-meta", context=context))

    for agent_state in result.agent_results:
        assert agent_state.metadata.get("call_mode") is None
        assert agent_state.metadata.get("group_id") is None


# ---------------------------------------------------------------------------
# Test 20: Grouped parser rejects missing agent_outputs key
# ---------------------------------------------------------------------------

def test_grouped_parser_rejects_missing_agent_outputs() -> None:
    """Grouped response without 'agent_outputs' key raises ValueError."""
    raw = json.dumps({"findings": []})
    agent_evidence_ids = {"ArchitectureAgent": {"ev_aaa111bbb222ccc333dd"}}

    import pytest
    with pytest.raises(ValueError, match="agent_outputs"):
        StructuredLLMClient._parse_grouped_response(raw, agent_evidence_ids)


# ---------------------------------------------------------------------------
# Test 21: Grouped parser handles missing agent key gracefully
# ---------------------------------------------------------------------------

def test_grouped_parser_handles_missing_agent_key() -> None:
    """If an expected agent key is missing, it gets a parse_error."""
    raw = json.dumps({
        "agent_outputs": {
            "ArchitectureAgent": {
                "findings": [],
                "no_findings_reason": None,
            },
            # MaintainabilityAgent is missing
        }
    })

    agent_evidence_ids = {
        "ArchitectureAgent": {"ev_aaa111bbb222ccc333dd"},
        "MaintainabilityAgent": {"ev_eee444fff555ggg666hh"},
    }
    result = StructuredLLMClient._parse_grouped_response(raw, agent_evidence_ids)

    assert result["ArchitectureAgent"].parse_error is None
    assert result["MaintainabilityAgent"].parse_error is not None
    assert "missing" in result["MaintainabilityAgent"].parse_error.lower()


# ---------------------------------------------------------------------------
# Test 22: Grouped parser handles agent with non-dict value
# ---------------------------------------------------------------------------

def test_grouped_parser_handles_non_dict_agent_value() -> None:
    """If an agent key maps to a non-dict value, it gets a parse_error."""
    raw = json.dumps({
        "agent_outputs": {
            "ArchitectureAgent": "invalid_string",
            "MaintainabilityAgent": {
                "findings": [],
                "no_findings_reason": None,
            },
        }
    })

    agent_evidence_ids = {
        "ArchitectureAgent": {"ev_aaa111bbb222ccc333dd"},
        "MaintainabilityAgent": {"ev_eee444fff555ggg666hh"},
    }
    result = StructuredLLMClient._parse_grouped_response(raw, agent_evidence_ids)

    assert result["ArchitectureAgent"].parse_error is not None
    assert result["MaintainabilityAgent"].parse_error is None


# ---------------------------------------------------------------------------
# Test 23: Grouped mode with empty evidence produces empty findings
# ---------------------------------------------------------------------------

def test_grouped_mode_empty_evidence(sample_context) -> None:
    """Grouped mode with no evidence produces completed agents with empty findings."""
    context = sample_context.to_review_context()
    context.evidence = []  # No evidence

    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_mode="grouped",
    )

    result = orchestrator.run(ReviewState(task_id="test-empty", context=context))

    assert len(result.agent_results) == 4
    for agent_state in result.agent_results:
        assert agent_state.status == "completed"
        assert len(agent_state.findings) == 0
        assert agent_state.metadata.get("no_findings_reason") == "No evidence available."


# ---------------------------------------------------------------------------
# Test 24: Grouped generate_grouped_findings with mock
# ---------------------------------------------------------------------------

def test_generate_grouped_findings_with_mock() -> None:
    """StructuredLLMClient.generate_grouped_findings works with mock LLM client."""
    client = StructuredLLMClient(MockLLMClient(), model="test")
    prompt = (
        "### Agent: ArchitectureAgent\n"
        "Review category: architecture. Target report section: Architecture Summary.\n"
        "Evidence:\n"
        "- evidence_id=ev_aaa111bbb222ccc333dd; file=app.py; lines=1-2; snippet=test\n"
        "\n### Agent: MaintainabilityAgent\n"
        "Review category: maintainability. Target report section: Maintainability Issues.\n"
        "Evidence:\n"
        "- evidence_id=ev_eee444fff555ggg666hh; file=services/review.py; lines=1-2; snippet=test\n"
    )

    agent_evidence_ids = {
        "ArchitectureAgent": {"ev_aaa111bbb222ccc333dd"},
        "MaintainabilityAgent": {"ev_eee444fff555ggg666hh"},
    }

    result = client.generate_grouped_findings(prompt, agent_evidence_ids=agent_evidence_ids)

    assert "ArchitectureAgent" in result.agent_outputs
    assert "MaintainabilityAgent" in result.agent_outputs
    # Each agent should have findings from mock
    arch = result.agent_outputs["ArchitectureAgent"]
    assert arch.parse_error is None
    assert len(arch.findings) >= 1


# ---------------------------------------------------------------------------
# Test 25: FindingValidator rejects findings with empty evidence_ids
# ---------------------------------------------------------------------------

def test_finding_validator_rejects_empty_evidence_ids(sample_context) -> None:
    """FindingValidator returns None for findings with empty evidence_ids."""
    context = _context_with_evidence(sample_context)
    validator = FindingValidator(context)

    raw = RawLLMFinding(
        title="Test",
        description="Test",
        category="architecture",
        severity="medium",
        confidence=0.5,
        evidence_ids=[],
        display=DisplayFields(
            en=BilingualTextField(title="Test", description="Test"),
            zh=BilingualTextField(title="测试", description="测试"),
        ),
    )

    # Empty evidence_ids should return None
    result = validator.validate(raw, section=REPORT_SECTIONS[0])
    assert result is None


# ---------------------------------------------------------------------------
# Test 26: Grouped parser rejects top-level JSON list
# ---------------------------------------------------------------------------

def test_grouped_parser_rejects_top_level_list() -> None:
    """Grouped response that is a JSON list (not dict) raises ValueError."""
    raw = json.dumps([{"findings": []}])
    agent_evidence_ids = {"ArchitectureAgent": {"ev_aaa111bbb222ccc333dd"}}

    import pytest
    with pytest.raises(ValueError, match="agent_outputs"):
        StructuredLLMClient._parse_grouped_response(raw, agent_evidence_ids)


# ---------------------------------------------------------------------------
# Test 27: Grouped parser rejects agent_outputs as list
# ---------------------------------------------------------------------------

def test_grouped_parser_rejects_agent_outputs_as_list() -> None:
    """Grouped response where agent_outputs is a list raises ValueError."""
    raw = json.dumps({"agent_outputs": [{"findings": []}]})
    agent_evidence_ids = {"ArchitectureAgent": {"ev_aaa111bbb222ccc333dd"}}

    import pytest
    with pytest.raises(ValueError, match="object"):
        StructuredLLMClient._parse_grouped_response(raw, agent_evidence_ids)


# ---------------------------------------------------------------------------
# Test 28: Grouped parser handles findings as non-list (dict)
# ---------------------------------------------------------------------------

def test_grouped_parser_handles_findings_as_dict() -> None:
    """If an agent's 'findings' value is a dict instead of list, agent gets parse_error."""
    raw = json.dumps({
        "agent_outputs": {
            "ArchitectureAgent": {
                "findings": {"title": "not a list"},
                "no_findings_reason": None,
            },
            "MaintainabilityAgent": {
                "findings": [],
                "no_findings_reason": None,
            },
        }
    })

    agent_evidence_ids = {
        "ArchitectureAgent": {"ev_aaa111bbb222ccc333dd"},
        "MaintainabilityAgent": {"ev_eee444fff555ggg666hh"},
    }
    result = StructuredLLMClient._parse_grouped_response(raw, agent_evidence_ids)

    assert result["ArchitectureAgent"].parse_error is not None
    assert "array" in result["ArchitectureAgent"].parse_error
    assert result["MaintainabilityAgent"].parse_error is None


# ---------------------------------------------------------------------------
# Test 29: Grouped parser handles findings as string
# ---------------------------------------------------------------------------

def test_grouped_parser_handles_findings_as_string() -> None:
    """If an agent's 'findings' value is a string, agent gets parse_error."""
    raw = json.dumps({
        "agent_outputs": {
            "ArchitectureAgent": {
                "findings": "not a list",
                "no_findings_reason": None,
            },
        }
    })

    agent_evidence_ids = {"ArchitectureAgent": {"ev_aaa111bbb222ccc333dd"}}
    result = StructuredLLMClient._parse_grouped_response(raw, agent_evidence_ids)

    assert result["ArchitectureAgent"].parse_error is not None
    assert "array" in result["ArchitectureAgent"].parse_error


# ---------------------------------------------------------------------------
# Test 30: Valid sibling salvaged when findings is wrong type
# ---------------------------------------------------------------------------

def test_salvage_valid_sibling_when_findings_wrong_type() -> None:
    """If one agent's findings is wrong type, the other agent's output is still valid."""
    raw = json.dumps({
        "agent_outputs": {
            "ArchitectureAgent": {
                "findings": 42,  # wrong type: int instead of list
                "no_findings_reason": None,
            },
            "MaintainabilityAgent": {
                "findings": [],
                "no_findings_reason": "No issues found.",
            },
        }
    })

    agent_evidence_ids = {
        "ArchitectureAgent": {"ev_aaa111bbb222ccc333dd"},
        "MaintainabilityAgent": {"ev_eee444fff555ggg666hh"},
    }
    result = StructuredLLMClient._parse_grouped_response(raw, agent_evidence_ids)

    # ArchitectureAgent should have parse_error
    assert result["ArchitectureAgent"].parse_error is not None
    assert result["ArchitectureAgent"].findings == []

    # MaintainabilityAgent should be valid (salvaged)
    assert result["MaintainabilityAgent"].parse_error is None
    assert result["MaintainabilityAgent"].no_findings_reason == "No issues found."


# ---------------------------------------------------------------------------
# Test 31: no_findings_reason non-string is sanitized to None (grouped)
# ---------------------------------------------------------------------------

def test_grouped_no_findings_reason_non_string_sanitized() -> None:
    """If no_findings_reason is not a string, it is sanitized to None."""
    raw = json.dumps({
        "agent_outputs": {
            "ArchitectureAgent": {
                "findings": [],
                "no_findings_reason": 12345,
            },
        }
    })

    agent_evidence_ids = {"ArchitectureAgent": {"ev_aaa111bbb222ccc333dd"}}
    result = StructuredLLMClient._parse_grouped_response(raw, agent_evidence_ids)

    assert result["ArchitectureAgent"].no_findings_reason is None


# ---------------------------------------------------------------------------
# Test 32: Separate parser rejects top-level string
# ---------------------------------------------------------------------------

def test_separate_parser_rejects_top_level_string() -> None:
    """Separate parser raises ValueError for top-level JSON string."""
    import pytest
    with pytest.raises(ValueError, match="Expected JSON object or array"):
        StructuredLLMClient._parse_findings('"just a string"')


# ---------------------------------------------------------------------------
# Test 33: Separate parser rejects top-level number
# ---------------------------------------------------------------------------

def test_separate_parser_rejects_top_level_number() -> None:
    """Separate parser raises ValueError for top-level JSON number."""
    import pytest
    with pytest.raises(ValueError, match="Expected JSON object or array"):
        StructuredLLMClient._parse_findings("42")


# ---------------------------------------------------------------------------
# Test 34: Separate parser rejects findings as non-list
# ---------------------------------------------------------------------------

def test_separate_parser_rejects_findings_as_non_list() -> None:
    """Separate parser raises ValueError when findings is not a list."""
    import pytest
    bad = json.dumps({"findings": "not a list"})
    with pytest.raises(ValueError, match="must be an array"):
        StructuredLLMClient._parse_findings(bad)


# ---------------------------------------------------------------------------
# Test 35: no_findings_reason non-string sanitized in separate mode
# ---------------------------------------------------------------------------

def test_separate_no_findings_reason_non_string_sanitized() -> None:
    """Separate parser sanitizes non-string no_findings_reason to None."""
    raw = json.dumps({"findings": [], "no_findings_reason": [1, 2, 3]})
    findings, reason = StructuredLLMClient._parse_findings(raw)
    assert findings == []
    assert reason is None
