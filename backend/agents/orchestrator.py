from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from backend.agents.architecture_agent import ArchitectureAgent
from backend.agents.evidence_agent import EvidenceGroundedAgent
from backend.agents.finding_validator import FindingValidator
from backend.agents.specialized_agents import CodeSmellAgent, MaintainabilityAgent, RefactorAgent
from backend.core.logging import get_logger
from backend.llm.client import LLMClient
from backend.llm.structured import GroupedAgentOutput, StructuredLLMClient
from backend.models.context import ReviewContext
from backend.models.review_state import AgentExecutionState, ReviewState
from backend.models.structured_review import ReviewFinding, StructuredReviewDraft
from backend.services.evidence import EvidenceRetriever

logger = get_logger(__name__)


@dataclass
class AgentRunResult:
    draft: StructuredReviewDraft
    errors: dict[str, str] = field(default_factory=dict)
    agent_states: list[AgentExecutionState] = field(default_factory=list)
    state: ReviewState | None = None


AgentProgressCallback = Callable[[str, str | None, AgentExecutionState | None], None]


class AgentOrchestrator:
    # Grouped mode group definitions
    _GROUP_1 = (ArchitectureAgent, MaintainabilityAgent)
    _GROUP_2 = (CodeSmellAgent, RefactorAgent)
    # Deterministic agent ordering for grouped mode output
    _DETERMINISTIC_ORDER = [
        "ArchitectureAgent",
        "CodeSmellAgent",
        "MaintainabilityAgent",
        "RefactorAgent",
    ]

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
        agent_mode: str = "separate",
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
        mode = agent_mode.strip().lower()
        if mode not in ("separate", "grouped"):
            logger.warning(
                "invalid_agent_mode value=%s falling_back=separate",
                agent_mode,
            )
            mode = "separate"
        self.agent_mode = mode

    def review(self, context: ReviewContext, *, task_id: str | None = None) -> AgentRunResult:
        state = self.run(ReviewState(task_id=task_id, context=context))
        return AgentRunResult(
            draft=StructuredReviewDraft(findings=state.validated_findings),
            errors=state.errors,
            agent_states=state.agent_results,
            state=state,
        )

    def run(self, state: ReviewState) -> ReviewState:
        if self.agent_mode == "grouped":
            return self._run_grouped(state)
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
            logger.info(
                "performance_event task_id=%s stage=agent_start agent=%s concurrency=%d",
                state.task_id or "none", agent.role, self.concurrency,
            )
            self._notify_progress("agent_running", agent.role)
            started = time.perf_counter()
            try:
                draft = agent.review(state.context)
                duration_seconds = time.perf_counter() - started
                duration_ms = round(duration_seconds * 1000, 1)
                findings.extend(draft.findings)
                state.evidence_bundles[agent.role] = list(agent.last_evidence_bundle)
                agent_state = self.build_completed_state(
                    agent.role,
                    draft.findings,
                    agent,
                    duration_seconds=duration_seconds,
                )
                state.agent_results.append(agent_state)
                cost_tracker = getattr(getattr(agent, "structured_client", None), "cost_tracker", None)
                retries = getattr(cost_tracker, "calls", 0) - 1 if cost_tracker else 0
                logger.info(
                    "performance_event task_id=%s stage=agent_end agent=%s "
                    "duration_ms=%s success=true retries=%d provider=%s model=%s",
                    state.task_id or "none", agent.role, duration_ms, retries,
                    self._provider_label(), self.model,
                )
                self._notify_progress("agent_completed", agent.role, agent_state)
            except Exception as exc:
                duration_seconds = time.perf_counter() - started
                duration_ms = round(duration_seconds * 1000, 1)
                state.errors[agent.role] = str(exc)
                agent_state = AgentExecutionState(
                    agent_id=agent.role,
                    status="failed",
                    error=str(exc),
                    validation_status="failed",
                    metadata={"duration_seconds": round(duration_seconds, 6)},
                )
                state.agent_results.append(agent_state)
                logger.info(
                    "performance_event task_id=%s stage=agent_end agent=%s "
                    "duration_ms=%s success=false retries=0 provider=%s model=%s",
                    state.task_id or "none", agent.role, duration_ms,
                    self._provider_label(), self.model,
                )
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
            logger.info(
                "performance_event task_id=%s stage=agent_start agent=%s concurrency=%d",
                state.task_id or "none", agent.role, self.concurrency,
            )
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
                duration_ms = round(duration_seconds * 1000, 1)
                agent_state = self.build_completed_state(
                    agent.role,
                    draft.findings,
                    agent,
                    duration_seconds=duration_seconds,
                )
                cost_tracker = getattr(getattr(agent, "structured_client", None), "cost_tracker", None)
                retries = getattr(cost_tracker, "calls", 0) - 1 if cost_tracker else 0
                logger.info(
                    "performance_event task_id=%s stage=agent_end agent=%s "
                    "duration_ms=%s success=true retries=%d provider=%s model=%s",
                    state.task_id or "none", agent.role, duration_ms, retries,
                    self._provider_label(), self.model,
                )
                return index, draft, agent_state
            except Exception as exc:
                duration_seconds = time.perf_counter() - started
                duration_ms = round(duration_seconds * 1000, 1)
                agent_state = AgentExecutionState(
                    agent_id=agent.role,
                    status="failed",
                    error=str(exc),
                    validation_status="failed",
                    metadata={"duration_seconds": round(duration_seconds, 6)},
                )
                logger.info(
                    "performance_event task_id=%s stage=agent_end agent=%s "
                    "duration_ms=%s success=false retries=0 provider=%s model=%s",
                    state.task_id or "none", agent.role, duration_ms,
                    self._provider_label(), self.model,
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

    def _run_grouped(self, state: ReviewState) -> ReviewState:
        """Run agents in grouped mode: 2 physical LLM calls, 4 logical agent outputs.

        Group 1: ArchitectureAgent + MaintainabilityAgent
        Group 2: CodeSmellAgent + RefactorAgent
        Both groups run concurrently. Each logical agent is validated independently.
        """
        groups = [
            ("group_1", list(self._GROUP_1)),
            ("group_2", list(self._GROUP_2)),
        ]

        # Prepare all agent instances and notify running
        all_agents: dict[str, EvidenceGroundedAgent] = {}
        for agent_class in self.agent_classes:
            agent = agent_class(
                self.llm_client,
                model=self.model,
                token_budget=self.per_agent_token_budget,
            )
            agent.set_candidate_paths(self.candidate_paths)
            all_agents[agent.role] = agent
            logger.info(
                "performance_event task_id=%s stage=agent_start agent=%s concurrency=%d",
                state.task_id or "none", agent.role, self.concurrency,
            )
            self._notify_progress("agent_running", agent.role)

        # Type alias for per-agent result tuple
        _AgentResultTuple = tuple[
            list[ReviewFinding], AgentExecutionState, EvidenceGroundedAgent,
        ]

        def _run_group(
            group_id: str,
            agent_classes: list[type[EvidenceGroundedAgent]],
        ) -> tuple[str, dict[str, _AgentResultTuple], dict[str, str]]:
            """Execute one grouped LLM call and return per-agent results."""
            group_start = time.perf_counter()
            task_id = state.task_id or "none"
            agent_roles = [cls.role for cls in agent_classes]
            logger.info(
                "performance_event task_id=%s stage=grouped_call_start "
                "group_id=%s logical_agents=%s concurrency=%d",
                task_id, group_id, ",".join(agent_roles), self.concurrency,
            )

            errors: dict[str, str] = {}
            per_agent_results: dict[str, tuple[list[ReviewFinding], AgentExecutionState, EvidenceGroundedAgent]] = {}

            # Retrieve evidence per agent
            agents_with_evidence: list[tuple[EvidenceGroundedAgent, list, object]] = []
            agent_evidence_ids: dict[str, set[str]] = {}
            for cls in agent_classes:
                agent = all_agents[cls.role]
                retrieval_policy = agent._retrieval_policy()
                retrieval = EvidenceRetriever(state.context).retrieve_with_policy(
                    retrieval_policy,
                    candidate_paths=self.candidate_paths,
                )
                evidence_bundle = retrieval.records
                agent.last_evidence_bundle = evidence_bundle
                agent.last_retrieval_stats = retrieval.stats
                agent_evidence_ids[cls.role] = {r.evidence_id for r in evidence_bundle}
                agents_with_evidence.append((agent, evidence_bundle, retrieval_policy))

            # Check if all agents have empty evidence
            if all(not bundle for _, bundle, _ in agents_with_evidence):
                for cls in agent_classes:
                    agent = all_agents[cls.role]
                    duration = time.perf_counter() - group_start
                    agent_state = AgentExecutionState(
                        agent_id=cls.role,
                        status="completed",
                        findings=[],
                        evidence_ids=[],
                        validation_status="validated",
                        metadata={
                            "duration_seconds": round(duration, 6),
                            "no_findings_reason": "No evidence available.",
                            "group_id": group_id,
                            "call_mode": "grouped",
                        },
                    )
                    per_agent_results[cls.role] = ([], agent_state, agent)
                grouped_duration = time.perf_counter() - group_start
                logger.info(
                    "performance_event task_id=%s stage=grouped_call_end "
                    "group_id=%s duration_ms=%s success=true retries=0 "
                    "provider=%s model=%s",
                    task_id, group_id, round(grouped_duration * 1000, 1),
                    self._provider_label(), self.model,
                )
                return group_id, per_agent_results, errors

            # Render grouped prompt and call LLM
            prompt = EvidenceGroundedAgent.render_grouped_prompt(
                state.context, agents_with_evidence, self.per_agent_token_budget * len(agent_classes),
            )
            structured_client = StructuredLLMClient(
                self.llm_client, model=self.model,
            )

            try:
                result = structured_client.generate_grouped_findings(
                    prompt, agent_evidence_ids=agent_evidence_ids,
                )
            except Exception as exc:
                grouped_duration = time.perf_counter() - group_start
                logger.info(
                    "performance_event task_id=%s stage=grouped_call_end "
                    "group_id=%s duration_ms=%s success=false retries=0 "
                    "provider=%s model=%s",
                    task_id, group_id, round(grouped_duration * 1000, 1),
                    self._provider_label(), self.model,
                )
                # All agents in this group failed
                for cls in agent_classes:
                    agent = all_agents[cls.role]
                    errors[cls.role] = str(exc)
                    agent_state = AgentExecutionState(
                        agent_id=cls.role,
                        status="failed",
                        error=str(exc),
                        validation_status="failed",
                        metadata={
                            "duration_seconds": round(grouped_duration, 6),
                            "group_id": group_id,
                            "call_mode": "grouped",
                        },
                    )
                    per_agent_results[cls.role] = ([], agent_state, agent)
                return group_id, per_agent_results, errors

            grouped_duration = time.perf_counter() - group_start
            retries = result.invalid_attempts
            logger.info(
                "performance_event task_id=%s stage=grouped_call_end "
                "group_id=%s duration_ms=%s success=true retries=%d "
                "provider=%s model=%s",
                task_id, group_id, round(grouped_duration * 1000, 1),
                retries, self._provider_label(), self.model,
            )

            # Parse and validate per logical agent
            validator = FindingValidator(state.context)
            for cls in agent_classes:
                agent = all_agents[cls.role]
                agent_output: GroupedAgentOutput | None = result.agent_outputs.get(cls.role)

                if agent_output is None:
                    logger.info(
                        "performance_event task_id=%s stage=logical_agent_parse "
                        "agent=%s raw_finding_count=0 parse_success=false error=missing_output",
                        task_id, cls.role,
                    )
                    agent_state = AgentExecutionState(
                        agent_id=cls.role,
                        status="failed",
                        error=f"Agent '{cls.role}' missing from grouped response.",
                        validation_status="failed",
                        metadata={
                            "duration_seconds": round(time.perf_counter() - group_start, 6),
                            "group_id": group_id,
                            "call_mode": "grouped",
                        },
                    )
                    per_agent_results[cls.role] = ([], agent_state, agent)
                    errors[cls.role] = f"Agent '{cls.role}' missing from grouped response."
                    continue

                if agent_output.parse_error:
                    logger.info(
                        "performance_event task_id=%s stage=logical_agent_parse "
                        "agent=%s raw_finding_count=%d parse_success=false error=%s",
                        task_id, cls.role, len(agent_output.findings),
                        agent_output.parse_error[:200],
                    )
                    agent_state = AgentExecutionState(
                        agent_id=cls.role,
                        status="failed",
                        error=agent_output.parse_error,
                        validation_status="failed",
                        metadata={
                            "duration_seconds": round(time.perf_counter() - group_start, 6),
                            "group_id": group_id,
                            "call_mode": "grouped",
                            "no_findings_reason": agent_output.no_findings_reason,
                        },
                    )
                    per_agent_results[cls.role] = ([], agent_state, agent)
                    errors[cls.role] = agent_output.parse_error
                    continue

                raw_count = len(agent_output.findings)
                logger.info(
                    "performance_event task_id=%s stage=logical_agent_parse "
                    "agent=%s raw_finding_count=%d parse_success=true",
                    task_id, cls.role, raw_count,
                )

                # Validate findings for this logical agent
                validated_findings: list[ReviewFinding] = []
                for raw_finding in agent_output.findings:
                    validated = validator.validate(raw_finding, section=cls.section)
                    if validated is not None:
                        validated_findings.append(validated)

                dropped_count = raw_count - len(validated_findings)
                logger.info(
                    "performance_event task_id=%s stage=logical_agent_validation "
                    "agent=%s validated_count=%d dropped_count=%d no_findings_reason=%s",
                    task_id, cls.role, len(validated_findings), dropped_count,
                    agent_output.no_findings_reason or "none",
                )

                # Build AgentExecutionState for this logical agent
                cost_tracker = getattr(structured_client, "cost_tracker", None)
                retrieval_stats = getattr(agent, "last_retrieval_stats", None)
                metadata: dict[str, str | int | float | bool | None] = (
                    retrieval_stats.to_metadata() if retrieval_stats is not None else {}
                )
                metadata["duration_seconds"] = round(time.perf_counter() - group_start, 6)
                metadata["group_id"] = group_id
                metadata["call_mode"] = "grouped"
                metadata["validated_finding_count"] = len(validated_findings)
                if agent_output.no_findings_reason:
                    metadata["no_findings_reason"] = agent_output.no_findings_reason

                agent_state = AgentExecutionState(
                    agent_id=cls.role,
                    status="completed",
                    findings=validated_findings,
                    evidence_ids=list(agent_evidence_ids[cls.role]),
                    prompt_tokens=getattr(cost_tracker, "prompt_tokens", None),
                    completion_tokens=getattr(cost_tracker, "completion_tokens", None),
                    llm_calls=getattr(cost_tracker, "calls", None),
                    validation_status="validated",
                    metadata=metadata,
                )
                per_agent_results[cls.role] = (validated_findings, agent_state, agent)

            return group_id, per_agent_results, errors

        # Run both groups concurrently
        group_errors: dict[str, str] = {}
        all_per_agent: dict[str, tuple[list[ReviewFinding], AgentExecutionState, EvidenceGroundedAgent]] = {}

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {
                executor.submit(_run_group, group_id, group_classes): group_id
                for group_id, group_classes in groups
            }
            for future in as_completed(futures):
                group_id, per_agent_results, errors = future.result()
                all_per_agent.update(per_agent_results)
                group_errors.update(errors)

        # Reassemble in deterministic order
        findings: list[ReviewFinding] = []
        for agent_role in self._DETERMINISTIC_ORDER:
            if agent_role in all_per_agent:
                agent_findings, agent_state, agent = all_per_agent[agent_role]
                state.agent_results.append(agent_state)
                findings.extend(agent_findings)
                state.evidence_bundles[agent_role] = list(agent.last_evidence_bundle)
                if agent_role in group_errors:
                    state.errors[agent_role] = group_errors[agent_role]
                    self._notify_progress("agent_failed", agent_role, agent_state)
                else:
                    self._notify_progress("agent_completed", agent_role, agent_state)

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

    def _provider_label(self) -> str:
        """Derive a safe provider label from model name for logging."""
        model = self.model.lower()
        if "mimo" in model or "xiaomi" in model:
            return "mimo"
        if "gpt" in model or "openai" in model:
            return "openai"
        return model.split("-")[0] if model else "unknown"

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
        no_reason = getattr(agent, "last_no_findings_reason", None)
        if no_reason:
            metadata["no_findings_reason"] = no_reason
        metadata["validated_finding_count"] = len(findings)
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
