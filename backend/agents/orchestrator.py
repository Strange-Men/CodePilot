from __future__ import annotations

from dataclasses import dataclass, field

from backend.agents.architecture_agent import ArchitectureAgent
from backend.agents.evidence_agent import EvidenceGroundedAgent
from backend.agents.specialized_agents import CodeSmellAgent, MaintainabilityAgent, RefactorAgent
from backend.llm.client import LLMClient
from backend.models.context import ReviewContext
from backend.models.review_state import AgentExecutionState, ReviewState
from backend.models.structured_review import ReviewFinding, StructuredReviewDraft


@dataclass
class AgentRunResult:
    draft: StructuredReviewDraft
    errors: dict[str, str] = field(default_factory=dict)
    agent_states: list[AgentExecutionState] = field(default_factory=list)
    state: ReviewState | None = None


class AgentOrchestrator:
    def __init__(
        self,
        llm_client: LLMClient,
        *,
        model: str = "gpt-4o-mini",
        per_agent_token_budget: int = 2000,
        agent_classes: list[type[EvidenceGroundedAgent]] | None = None,
        candidate_paths: set[str] | None = None,
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

    def review(self, context: ReviewContext, *, task_id: str | None = None) -> AgentRunResult:
        state = self.run(ReviewState(task_id=task_id, context=context))
        return AgentRunResult(
            draft=StructuredReviewDraft(findings=state.validated_findings),
            errors=state.errors,
            agent_states=state.agent_results,
            state=state,
        )

    def run(self, state: ReviewState) -> ReviewState:
        findings: list[ReviewFinding] = []
        for agent_class in self.agent_classes:
            agent = agent_class(
                self.llm_client,
                model=self.model,
                token_budget=self.per_agent_token_budget,
            )
            agent.set_candidate_paths(self.candidate_paths)
            try:
                draft = agent.review(state.context)
                findings.extend(draft.findings)
                state.evidence_bundles[agent.role] = list(agent.last_evidence_bundle)
                state.agent_results.append(self.build_completed_state(agent.role, draft.findings, agent))
            except Exception as exc:
                state.errors[agent.role] = str(exc)
                state.agent_results.append(
                    AgentExecutionState(
                        agent_id=agent.role,
                        status="failed",
                        error=str(exc),
                        validation_status="failed",
                    )
                )
        state.validated_findings = self._deduplicate(findings)
        state.metadata.update(
            {
                "orchestrator": type(self).__name__,
                "agent_count": len(self.agent_classes),
            }
        )
        state.metadata.update(self.build_retrieval_summary_metadata(state.agent_results))
        return state

    @staticmethod
    def build_completed_state(
        agent_id: str,
        findings: list[ReviewFinding],
        agent: EvidenceGroundedAgent,
    ) -> AgentExecutionState:
        cost_tracker = getattr(getattr(agent, "structured_client", None), "cost_tracker", None)
        retrieval_stats = getattr(agent, "last_retrieval_stats", None)
        metadata = retrieval_stats.to_metadata() if retrieval_stats is not None else {}
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
