"""Tests for pipeline behavior when all agents fail.

Verifies that when all 4 agents fail, the review status is set to 'failed'
(not 'completed'), agent states are persisted, and the error message contains
agent names.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.core.config import Settings
from backend.models.context import ReviewContext
from backend.models.report_result import ReportResult
from backend.models.review import ReviewStatus
from backend.models.review_state import AgentExecutionState
from backend.tasks.pipeline import ReviewPipeline


def _all_failed_agent_states() -> list[AgentExecutionState]:
    """Create 4 agent states, all failed."""
    return [
        AgentExecutionState(
            agent_id="ArchitectureAgent",
            status="failed",
            error="httpx.ReadTimeout: Read timeout",
            validation_status="failed",
        ),
        AgentExecutionState(
            agent_id="CodeSmellAgent",
            status="failed",
            error="httpx.ReadTimeout: Read timeout",
            validation_status="failed",
        ),
        AgentExecutionState(
            agent_id="MaintainabilityAgent",
            status="failed",
            error="httpx.ReadTimeout: Read timeout",
            validation_status="failed",
        ),
        AgentExecutionState(
            agent_id="RefactorAgent",
            status="failed",
            error="httpx.ReadTimeout: Read timeout",
            validation_status="failed",
        ),
    ]


def _mixed_agent_states() -> list[AgentExecutionState]:
    """Create agent states with some completed and some failed."""
    return [
        AgentExecutionState(
            agent_id="ArchitectureAgent",
            status="completed",
            validation_status="validated",
        ),
        AgentExecutionState(
            agent_id="CodeSmellAgent",
            status="failed",
            error="Parse error",
            validation_status="failed",
        ),
        AgentExecutionState(
            agent_id="MaintainabilityAgent",
            status="completed",
            validation_status="validated",
        ),
        AgentExecutionState(
            agent_id="RefactorAgent",
            status="completed",
            validation_status="validated",
        ),
    ]


def _settings(**overrides: object) -> Settings:
    return Settings(**overrides)


def test_all_agents_failed_sets_review_status_to_failed(tmp_path: Path) -> None:
    """When all 4 agents fail, review status must be 'failed', not 'completed'."""
    store = MagicMock()
    settings = _settings(USE_MOCK_LLM=True)
    pipeline = ReviewPipeline(
        settings=settings,
        store=store,
        llm_client=MagicMock(),
    )

    report_result = ReportResult(
        report="# Fallback report\nAll agents failed.\n",
        export_path=tmp_path / "test.md",
        agent_states=_all_failed_agent_states(),
    )

    with (
        patch.object(pipeline, "_clone_repository", return_value=tmp_path),
        patch.object(pipeline, "_build_manifest", return_value=MagicMock()),
        patch.object(pipeline, "_build_context", return_value=MagicMock(spec=ReviewContext)),
        patch.object(pipeline, "_record_summarized"),
        patch.object(pipeline, "_generate_report", return_value=report_result),
    ):
        pipeline.run("test-task-id", "https://github.com/example/repo")

    # Verify status was set to 'failed', not 'completed'
    store.update_status.assert_called_once()
    call_args = store.update_status.call_args
    assert call_args[0][0] == "test-task-id"
    assert call_args[0][1] == ReviewStatus.failed


def test_all_agents_failed_error_message_contains_agent_names(tmp_path: Path) -> None:
    """The error message must list which agents failed."""
    store = MagicMock()
    settings = _settings(USE_MOCK_LLM=True)
    pipeline = ReviewPipeline(
        settings=settings,
        store=store,
        llm_client=MagicMock(),
    )

    report_result = ReportResult(
        report="# Fallback report\n",
        export_path=tmp_path / "test.md",
        agent_states=_all_failed_agent_states(),
    )

    with (
        patch.object(pipeline, "_clone_repository", return_value=tmp_path),
        patch.object(pipeline, "_build_manifest", return_value=MagicMock()),
        patch.object(pipeline, "_build_context", return_value=MagicMock(spec=ReviewContext)),
        patch.object(pipeline, "_record_summarized"),
        patch.object(pipeline, "_generate_report", return_value=report_result),
    ):
        pipeline.run("test-task-id", "https://github.com/example/repo")

    # Verify error message contains agent names
    call_args = store.update_status.call_args
    error = call_args[1].get("error") or call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("error")
    # The error is passed as keyword arg
    error = call_args.kwargs.get("error", "")
    assert "ArchitectureAgent" in error
    assert "CodeSmellAgent" in error
    assert "MaintainabilityAgent" in error
    assert "RefactorAgent" in error


def test_all_agents_failed_persists_agent_states(tmp_path: Path) -> None:
    """Agent states must be persisted even when all agents fail."""
    store = MagicMock()
    settings = _settings(USE_MOCK_LLM=True)
    pipeline = ReviewPipeline(
        settings=settings,
        store=store,
        llm_client=MagicMock(),
    )

    agent_states = _all_failed_agent_states()
    report_result = ReportResult(
        report="# Fallback report\n",
        export_path=tmp_path / "test.md",
        agent_states=agent_states,
    )

    with (
        patch.object(pipeline, "_clone_repository", return_value=tmp_path),
        patch.object(pipeline, "_build_manifest", return_value=MagicMock()),
        patch.object(pipeline, "_build_context", return_value=MagicMock(spec=ReviewContext)),
        patch.object(pipeline, "_record_summarized"),
        patch.object(pipeline, "_generate_report", return_value=report_result),
    ):
        pipeline.run("test-task-id", "https://github.com/example/repo")

    # Verify agent states were persisted
    store.replace_agent_states.assert_called_once()
    persisted_states = store.replace_agent_states.call_args[0][1]
    assert len(persisted_states) == 4
    assert all(s.status == "failed" for s in persisted_states)


def test_mixed_agent_failure_keeps_completed_status(tmp_path: Path) -> None:
    """When some agents succeed, review status should remain 'completed'."""
    store = MagicMock()
    settings = _settings(USE_MOCK_LLM=True)
    pipeline = ReviewPipeline(
        settings=settings,
        store=store,
        llm_client=MagicMock(),
    )

    report_result = ReportResult(
        report="# Review report\nSome findings.\n",
        export_path=tmp_path / "test.md",
        agent_states=_mixed_agent_states(),
    )

    with (
        patch.object(pipeline, "_clone_repository", return_value=tmp_path),
        patch.object(pipeline, "_build_manifest", return_value=MagicMock()),
        patch.object(pipeline, "_build_context", return_value=MagicMock(spec=ReviewContext)),
        patch.object(pipeline, "_record_summarized"),
        patch.object(pipeline, "_generate_report", return_value=report_result),
    ):
        pipeline.run("test-task-id", "https://github.com/example/repo")

    # Verify status was set to 'completed' (some agents succeeded)
    store.update_status.assert_called_once()
    call_args = store.update_status.call_args
    assert call_args[0][1] == ReviewStatus.completed


def test_empty_agent_states_keeps_completed_status(tmp_path: Path) -> None:
    """When no agent states exist (v2 engine), review status should remain 'completed'."""
    store = MagicMock()
    settings = _settings(USE_MOCK_LLM=True)
    pipeline = ReviewPipeline(
        settings=settings,
        store=store,
        llm_client=MagicMock(),
    )

    report_result = ReportResult(
        report="# Review report\n",
        export_path=tmp_path / "test.md",
        agent_states=[],
    )

    with (
        patch.object(pipeline, "_clone_repository", return_value=tmp_path),
        patch.object(pipeline, "_build_manifest", return_value=MagicMock()),
        patch.object(pipeline, "_build_context", return_value=MagicMock(spec=ReviewContext)),
        patch.object(pipeline, "_record_summarized"),
        patch.object(pipeline, "_generate_report", return_value=report_result),
    ):
        pipeline.run("test-task-id", "https://github.com/example/repo")

    # Verify status was set to 'completed'
    store.update_status.assert_called_once()
    call_args = store.update_status.call_args
    assert call_args[0][1] == ReviewStatus.completed
