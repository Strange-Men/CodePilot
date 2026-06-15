from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from backend.agents.architecture_agent import ArchitectureAgent
from backend.agents.evidence_agent import EvidenceGroundedAgent
from backend.agents.specialized_agents import CodeSmellAgent, MaintainabilityAgent, RefactorAgent
from backend.core.logging import get_logger
from backend.llm.client import LLMClient
from backend.models.context import ReviewContext
from backend.models.review_state import AgentExecutionState, ReviewState
from backend.models.structured_review import ReviewFinding, StructuredReviewDraft

logger = get_logger(__name__)


@dataclass
class AgentRunResult:
    draft: StructuredReviewDraft
    errors: dict[str, str] = field(default_factory=dict)
    agent_states: list[AgentExecutionState] = field(default_factory=list)
    state: ReviewState | None = None


AgentProgressCallback = Callable[[str, str | None, AgentExecutionState | None], None]


class AgentOrchestrator:
    def __init__(
        self,
        llm_client: LLMClient,
        *,
        model: str = "gpt-4o-mini",
        per_agent_token_budget: int = 2000,
        agent_classes: list[type[EvidenceGroundedAgent]] | None = None,
        candidate_paths: set[str] | None = None,
        progress_callback: AgentProgressCallback | None = None,
        concurrency: int = 1,
    ) -> None:
        self.llm_client = llm_client
        self.model = model
        self.per_agent_token_budget = per_agent_token_budget
        self.agent_classes = agent_classes or [
            ArchitectureAgent,
            CodeSmellAgent,
            MaintainabilityAgent,
            RefactorAgent,
        ]
        self.candidate_paths = candidate_paths
        self.progress_callback = progress_callback
        self.concurrency = max(1, concurrency)

    def review(self, context: ReviewContext, *, task_id: str | None = None) -> AgentRunResult:
        state = self.run(ReviewState(task_id=task_id, context=context))
        return AgentRunResult(
            draft=StructuredReviewDraft(findings=state.validated_findings),
            errors=state.errors,
            agent_states=state.agent_results,
            state=state,
        )

    def run(self, state: ReviewState) -> ReviewState:
        if self.concurrency <= 1:
            return self._run_serial(state)
        return self._run_parallel(state)

    def _run_serial(self, state: ReviewState) -> ReviewState:
        findings: list[ReviewFinding] = []
        for agent_class in self.agent_classes:
            agent = agent_class(
                self.llm_client,
                model=self.model,
                token_budget=self.per_agent_token_budget,
            )
            agent.set_candidate_paths(self.candidate_paths)
            self._notify_progress("agent_running", agent.role)
            started = time.perf_counter()
            try:
                draft = agent.review(state.context)
                duration_seconds = time.perf_counter() - started
                findings.extend(draft.findings)
                state.evidence_bundles[agent.role] = list(agent.last_evidence_bundle)
                agent_state = self.build_completed_state(
                    agent.role,
                    draft.findings,
                    agent,
                    duration_seconds=duration_seconds,
                )
                state.agent_results.append(agent_state)
                self._notify_progress("agent_completed", agent.role, agent_state)
            except Exception as exc:
                duration_seconds = time.perf_counter() - started
                state.errors[agent.role] = str(exc)
                agent_state = AgentExecutionState(
                    agent_id=agent.role,
                    status="failed",
                    error=str(exc),
                    validation_status="failed",
                    metadata={"duration_seconds": round(duration_seconds, 6)},
                )
                state.agent_results.append(agent_state)
                self._notify_progress("agent_failed", agent.role, agent_state)
        self._finalize_state(state, findings)
        return state

    def _run_parallel(self, state: ReviewState) -> ReviewState:
        """Run agents concurrently using a thread pool.

        Preserves deterministic final ordering (A1, A2, A3, A4),
        per-agent failure isolation, and progress notifications.
        """
        # Prepare agent instances and notify running
        indexed_agents: list[tuple[int, EvidenceGroundedAgent]] = []
        for index, agent_class in enumerate(self.agent_classes):
            agent = agent_class(
                self.llm_client,
                model=self.model,
                token_budget=self.per_agent_token_budget,
            )
            agent.set_candidate_paths(self.candidate_paths)
            indexed_agents.append((index, agent))
            self._notify_progress("agent_running", agent.role)

        # Results indexed by original position
        indexed_results: dict[int, tuple[StructuredReviewDraft | None, AgentExecutionState]] = {}

        def _run_single(
            index: int,
            agent: EvidenceGroundedAgent,
        ) -> tuple[int, StructuredReviewDraft | None, AgentExecutionState]:
            started = time.perf_counter()
            try:
                draft = agent.review(state.context)
                duration_seconds = time.perf_counter() - started
                agent_state = self.build_completed_state(
                    agent.role,
                    draft.findings,
                    agent,
                    duration_seconds=duration_seconds,
                )
                return index, draft, agent_state
            except Exception as exc:
                duration_seconds = time.perf_counter() - started
                agent_state = AgentExecutionState(
                    agent_id=agent.role,
                    status="failed",
                    error=str(exc),
                    validation_status="failed",
                    metadata={"duration_seconds": round(duration_seconds, 6)},
                )
                return index, None, agent_state

        with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
            futures = {
                executor.submit(_run_single, index, agent): index
                for index, agent in indexed_agents
            }
            for future in as_completed(futures):
                index, draft, agent_state = future.result()
                indexed_results[index] = (draft, agent_state)
                agent_id = self.agent_classes[index].role
                if agent_state.status == "completed":
                    self._notify_progress("agent_completed", agent_id, agent_state)
                else:
                    state.errors[agent_id] = agent_state.error or "unknown error"
                    self._notify_progress("agent_failed", agent_id, agent_state)

        # Reassemble in deterministic order
        findings: list[ReviewFinding] = []
        for index in range(len(self.agent_classes)):
            draft, agent_state = indexed_results[index]
            state.agent_results.append(agent_state)
            if draft is not None:
                findings.extend(draft.findings)
                agent = indexed_agents[index][1]
                state.evidence_bundles[agent_state.agent_id] = list(agent.last_evidence_bundle)

        self._finalize_state(state, findings)
        return state

    def _finalize_state(self, state: ReviewState, findings: list[ReviewFinding]) -> None:
        state.validated_findings = self._deduplicate(findings)
        state.metadata.update(
            {
                "orchestrator": type(self).__name__,
                "agent_count": len(self.agent_classes),
                "agent_concurrency": self.concurrency,
            }
        )
        state.metadata.update(self.build_retrieval_summary_metadata(state.agent_results))

    def _notify_progress(
        self,
        event: str,
        agent_id: str | None,
        agent_state: AgentExecutionState | None = None,
    ) -> None:
        if self.progress_callback is not None:
            self.progress_callback(event, agent_id, agent_state)

    @staticmethod
    def build_completed_state(
        agent_id: str,
        findings: list[ReviewFinding],
        agent: EvidenceGroundedAgent,
        *,
        duration_seconds: float | None = None,
    ) -> AgentExecutionState:
        cost_tracker = getattr(getattr(agent, "structured_client", None), "cost_tracker", None)
        retrieval_stats = getattr(agent, "last_retrieval_stats", None)
        metadata = retrieval_stats.to_metadata() if retrieval_stats is not None else {}
        if duration_seconds is not None:
            metadata["duration_seconds"] = round(duration_seconds, 6)
        return AgentExecutionState(
            agent_id=agent_id,
            status="completed",
            findings=findings,
            evidence_ids=[record.evidence_id for record in agent.last_evidence_bundle],
            prompt_tokens=getattr(cost_tracker, "prompt_tokens", None),
            completion_tokens=getattr(cost_tracker, "completion_tokens", None),
            llm_calls=getattr(cost_tracker, "calls", None),
            validation_status="validated",
            metadata=metadata,
        )

    @staticmethod
    def _deduplicate(findings: list[ReviewFinding]) -> list[ReviewFinding]:
        by_key: dict[tuple[str, str, tuple[str, ...]], ReviewFinding] = {}
        for finding in findings:
            key = (
                (finding.category or "").lower(),
                " ".join((finding.title or finding.description).lower().split()),
                tuple(sorted(finding.evidence_ids)),
            )
            existing = by_key.get(key)
            if existing is None or (finding.confidence or 0.0) > (existing.confidence or 0.0):
                by_key[key] = finding
        return list(by_key.values())

    @staticmethod
    def build_retrieval_summary_metadata(
        agent_states: list[AgentExecutionState],
    ) -> dict[str, str | int | float | bool | None]:
        retrieval_states = [
            state
            for state in agent_states
            if "retrieval_latency_ms" in state.metadata
        ]
        if not retrieval_states:
            return {}
        total_latency = sum(float(state.metadata.get("retrieval_latency_ms") or 0.0) for state in retrieval_states)
        average_precision = sum(
            float(state.metadata.get("retrieval_precision_like") or 0.0)
            for state in retrieval_states
        ) / len(retrieval_states)
        average_recall = sum(
            float(state.metadata.get("retrieval_recall_like") or 0.0)
            for state in retrieval_states
        ) / len(retrieval_states)
        average_token_utilization = sum(
            float(state.metadata.get("retrieval_token_utilization") or 0.0)
            for state in retrieval_states
        ) / len(retrieval_states)
        return {
            "retrieval_agents_with_stats": len(retrieval_states),
            "retrieval_total_latency_ms": round(total_latency, 3),
            "retrieval_average_precision_like": round(average_precision, 4),
            "retrieval_average_recall_like": round(average_recall, 4),
            "retrieval_average_token_utilization": round(average_token_utilization, 4),
            "retrieval_large_repo_mode": any(
                bool(state.metadata.get("retrieval_large_repo_mode"))
                for state in retrieval_states
            ),
        }
