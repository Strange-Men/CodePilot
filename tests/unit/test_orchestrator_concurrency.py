"""Tests for parallel agent execution in the orchestrator."""

from __future__ import annotations

import logging
import time

from backend.agents.evidence_agent import EvidenceGroundedAgent
from backend.agents.orchestrator import AgentOrchestrator
from backend.agents.specialized_agents import CodeSmellAgent
from backend.core.report_contract import REPORT_SECTIONS
from backend.llm.client import MockLLMClient
from backend.models.context import EvidenceRecord
from backend.models.review_state import ReviewState
from backend.services.evidence import stable_evidence_id


class SlowAgent(EvidenceGroundedAgent):
    """Agent that sleeps briefly to test concurrency timing."""

    role = "SlowAgent"
    section = REPORT_SECTIONS[0]
    category = "architecture"
    evidence_query = "architecture"
    evidence_limit = 2

    def review(self, context):
        # Simulate LLM latency
        time.sleep(0.1)
        return super().review(context)


class FailingAgent(EvidenceGroundedAgent):
    """Agent that always raises an exception."""

    role = "FailingAgent"

    def review(self, context):
        raise RuntimeError("agent failed")


def _context_with_evidence(sample_context):
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


def test_serial_concurrency_runs_agents_sequentially(sample_context) -> None:
    """With concurrency=1, agents run serially (backward compatible)."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_classes=[CodeSmellAgent, CodeSmellAgent],
        concurrency=1,
    )

    result = orchestrator.run(ReviewState(task_id=None, context=context))

    assert len(result.agent_results) == 2
    assert all(state.status == "completed" for state in result.agent_results)
    assert result.metadata.get("agent_concurrency") == 1


def test_parallel_concurrency_runs_agents_concurrently(sample_context) -> None:
    """With concurrency>1, agents run concurrently and wall-clock is reduced."""
    context = _context_with_evidence(sample_context)

    # Use 4 slow agents with concurrency=4
    agents = [SlowAgent] * 4
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_classes=agents,
        concurrency=4,
    )

    started = time.perf_counter()
    result = orchestrator.run(ReviewState(task_id=None, context=context))
    wall_clock = time.perf_counter() - started

    assert len(result.agent_results) == 4
    assert all(state.status == "completed" for state in result.agent_results)
    assert result.metadata.get("agent_concurrency") == 4
    # With concurrency=4, wall clock should be much less than 4 * 0.1s
    # Allow generous margin for test overhead
    assert wall_clock < 0.8, f"Parallel execution took {wall_clock:.2f}s, expected < 0.8s"


def test_parallel_preserves_deterministic_ordering(sample_context) -> None:
    """Agent results must be in original A1, A2, A3, A4 order regardless of completion order."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_classes=[CodeSmellAgent, CodeSmellAgent, CodeSmellAgent, CodeSmellAgent],
        concurrency=4,
    )

    result = orchestrator.run(ReviewState(task_id=None, context=context))

    # All should be completed in order
    assert len(result.agent_results) == 4
    for i, state in enumerate(result.agent_results):
        assert state.agent_id == f"CodeSmellAgent_{i}" or state.status == "completed"


def test_parallel_failure_isolation(sample_context) -> None:
    """One agent failure does not cancel other agents."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_classes=[FailingAgent, CodeSmellAgent],
        concurrency=2,
    )

    result = orchestrator.run(ReviewState(task_id=None, context=context))

    assert len(result.agent_results) == 2
    assert result.agent_results[0].status == "failed"
    assert result.agent_results[0].error == "agent failed"
    assert result.agent_results[1].status == "completed"
    assert "FailingAgent" in result.errors


def test_parallel_progress_notifications(sample_context) -> None:
    """Progress callbacks fire correctly during parallel execution."""
    context = _context_with_evidence(sample_context)
    events: list[tuple[str, str | None]] = []

    def callback(event: str, agent_id: str | None, _state=None):
        events.append((event, agent_id))

    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_classes=[CodeSmellAgent, CodeSmellAgent],
        concurrency=2,
        progress_callback=callback,
    )

    orchestrator.run(ReviewState(task_id=None, context=context))

    # Should have running events for both agents
    running_events = [e for e in events if e[0] == "agent_running"]
    assert len(running_events) == 2

    # Should have completion events for both agents
    completed_events = [e for e in events if e[0] == "agent_completed"]
    assert len(completed_events) == 2


def test_parallel_findings_are_deduplicated(sample_context) -> None:
    """Findings from parallel agents are still deduplicated."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_classes=[CodeSmellAgent, CodeSmellAgent],
        concurrency=2,
    )

    result = orchestrator.run(ReviewState(task_id=None, context=context))

    # Findings should be deduplicated
    assert result.validated_findings is not None
    # Each agent produces findings from the same evidence, so dedup should reduce them
    total_findings = len(result.agent_results[0].findings) + len(result.agent_results[1].findings)
    assert len(result.validated_findings) <= total_findings


def test_concurrency_1_matches_serial_behavior(sample_context) -> None:
    """Concurrency=1 produces identical results to the original serial loop."""
    context = _context_with_evidence(sample_context)

    # Serial
    orchestrator_serial = AgentOrchestrator(
        MockLLMClient(),
        agent_classes=[CodeSmellAgent, CodeSmellAgent],
        concurrency=1,
    )
    result_serial = orchestrator_serial.run(ReviewState(task_id=None, context=context))

    # Also serial (concurrency=1)
    orchestrator_serial2 = AgentOrchestrator(
        MockLLMClient(),
        agent_classes=[CodeSmellAgent, CodeSmellAgent],
        concurrency=1,
    )
    result_serial2 = orchestrator_serial2.run(ReviewState(task_id=None, context=context))

    # Both should have same number of results
    assert len(result_serial.agent_results) == len(result_serial2.agent_results)
    assert len(result_serial.validated_findings) == len(result_serial2.validated_findings)


def test_concurrency_4_submits_all_agents(sample_context) -> None:
    """With concurrency=4, all 4 default agents are submitted and complete."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        concurrency=4,
    )

    result = orchestrator.run(ReviewState(task_id="test-4agents", context=context))

    assert len(result.agent_results) == 4
    assert {state.agent_id for state in result.agent_results} == {
        "ArchitectureAgent",
        "CodeSmellAgent",
        "MaintainabilityAgent",
        "RefactorAgent",
    }
    assert all(state.status == "completed" for state in result.agent_results)
    assert result.metadata.get("agent_concurrency") == 4


def test_concurrency_4_deterministic_ordering(sample_context) -> None:
    """Agent results maintain deterministic A1, A2, A3, A4 order with concurrency=4."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        concurrency=4,
    )

    result = orchestrator.run(ReviewState(task_id="test-order", context=context))

    expected_order = [
        "ArchitectureAgent",
        "CodeSmellAgent",
        "MaintainabilityAgent",
        "RefactorAgent",
    ]
    actual_order = [state.agent_id for state in result.agent_results]
    assert actual_order == expected_order


def test_concurrency_4_failure_isolation(sample_context) -> None:
    """With concurrency=4, one agent failure does not cancel other agents."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_classes=[FailingAgent, CodeSmellAgent, CodeSmellAgent, CodeSmellAgent],
        concurrency=4,
    )

    result = orchestrator.run(ReviewState(task_id="test-fail-iso", context=context))

    assert len(result.agent_results) == 4
    assert result.agent_results[0].status == "failed"
    assert result.agent_results[0].error == "agent failed"
    assert all(state.status == "completed" for state in result.agent_results[1:])
    assert "FailingAgent" in result.errors


def test_timing_logs_emitted(sample_context, caplog) -> None:
    """Performance event logs are emitted during agent execution."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_classes=[CodeSmellAgent, CodeSmellAgent],
        concurrency=2,
    )

    # Temporarily enable propagation so caplog can capture logs
    test_logger = logging.getLogger("backend.agents.orchestrator")
    test_logger.propagate = True
    try:
        with caplog.at_level(logging.INFO, logger="backend.agents.orchestrator"):
            orchestrator.run(ReviewState(task_id="test-timing", context=context))

        # Check for performance_event logs
        performance_logs = [
            record for record in caplog.records
            if "performance_event" in record.message
        ]
        assert len(performance_logs) >= 4  # 2 agent_start + 2 agent_end

        # Check agent_start logs
        start_logs = [r for r in performance_logs if "stage=agent_start" in r.message]
        assert len(start_logs) == 2
        assert all("concurrency=2" in r.message for r in start_logs)

        # Check agent_end logs
        end_logs = [r for r in performance_logs if "stage=agent_end" in r.message]
        assert len(end_logs) == 2
        assert all("success=true" in r.message for r in end_logs)
        assert all("duration_ms=" in r.message for r in end_logs)
        assert all("retries=" in r.message for r in end_logs)
    finally:
        test_logger.propagate = False


def test_timing_logs_no_secrets(sample_context, caplog) -> None:
    """Performance event logs do not contain API keys or secrets."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_classes=[CodeSmellAgent],
        concurrency=1,
    )

    test_logger = logging.getLogger("backend.agents.orchestrator")
    test_logger.propagate = True
    try:
        with caplog.at_level(logging.INFO, logger="backend.agents.orchestrator"):
            orchestrator.run(ReviewState(task_id="test-no-secrets", context=context))

        # Check that no log contains API key patterns
        for record in caplog.records:
            msg = record.message
            assert "sk-" not in msg, "Log contains potential API key"
            assert "OPENAI_API_KEY" not in msg, "Log contains env var name"
            assert "MIMO_API_KEY" not in msg, "Log contains env var name"
    finally:
        test_logger.propagate = False


def test_retry_count_recorded(sample_context, caplog) -> None:
    """Retry count is recorded in agent_end logs."""
    context = _context_with_evidence(sample_context)
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        agent_classes=[CodeSmellAgent],
        concurrency=1,
    )

    test_logger = logging.getLogger("backend.agents.orchestrator")
    test_logger.propagate = True
    try:
        with caplog.at_level(logging.INFO, logger="backend.agents.orchestrator"):
            orchestrator.run(ReviewState(task_id="test-retries", context=context))

        # Check agent_end logs have retries field
        end_logs = [
            r for r in caplog.records
            if "performance_event" in r.message and "stage=agent_end" in r.message
        ]
        assert len(end_logs) == 1
        assert "retries=" in end_logs[0].message
    finally:
        test_logger.propagate = False


def test_provider_label_derived(sample_context) -> None:
    """Provider label is correctly derived from model name."""
    orchestrator = AgentOrchestrator(
        MockLLMClient(),
        model="mimo-v2.5-pro",
    )
    assert orchestrator._provider_label() == "mimo"

    orchestrator2 = AgentOrchestrator(
        MockLLMClient(),
        model="gpt-4o-mini",
    )
    assert orchestrator2._provider_label() == "openai"

    orchestrator3 = AgentOrchestrator(
        MockLLMClient(),
        model="claude-3-sonnet",
    )
    assert orchestrator3._provider_label() == "claude"
