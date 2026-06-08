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
            try:
                draft = agent.review(state.context)
                findings.extend(draft.findings)
                state.evidence_bundles[agent.role] = list(agent.last_evidence_bundle)
                state.agent_results.append(self._completed_state(agent.role, draft.findings, agent))
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
        return state

    @staticmethod
    def _completed_state(
        agent_id: str,
        findings: list[ReviewFinding],
        agent: EvidenceGroundedAgent,
    ) -> AgentExecutionState:
        cost_tracker = getattr(getattr(agent, "structured_client", None), "cost_tracker", None)
        return AgentExecutionState(
            agent_id=agent_id,
            status="completed",
            findings=findings,
            evidence_ids=[record.evidence_id for record in agent.last_evidence_bundle],
            prompt_tokens=getattr(cost_tracker, "prompt_tokens", None),
            completion_tokens=getattr(cost_tracker, "completion_tokens", None),
            llm_calls=getattr(cost_tracker, "calls", None),
            validation_status="validated",
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
