from __future__ import annotations

import time
from pathlib import Path

from backend.agents.architecture_agent import ArchitectureAgent
from backend.agents.orchestrator import AgentOrchestrator
from backend.llm.client import LLMClient
from backend.models.context import RepositoryContext, ReviewContext, as_review_context
from backend.models.report_result import ReportResult
from backend.models.review_scope import ReviewScope
from backend.models.review_state import AgentExecutionState, ReviewState
from backend.models.structured_review import StructuredReviewDraft
from backend.prompts import PromptRenderer
from backend.reviewers.markdown_adapter import MarkdownReviewAdapter
from backend.reviewers.report_composer import HumanReadableReportComposer


class ReportGenerator:
    def __init__(
        self,
        llm_client: LLMClient,
        reports_path: Path,
        prompt_token_budget: int,
        token_model: str = "gpt-4o-mini",
    ) -> None:
        self.llm_client = llm_client
        self.reports_path = reports_path
        self.prompt_renderer = PromptRenderer(prompt_token_budget, token_model)
        self.markdown_adapter = MarkdownReviewAdapter()
        self.report_composer = HumanReadableReportComposer()
        self.review_engine = "v2"
        self.token_model = token_model
        self.review_scope: ReviewScope | None = None

    def configure_engine(self, review_engine: str) -> None:
        self.review_engine = review_engine

    def configure_review_scope(self, review_scope: ReviewScope | None) -> None:
        self.review_scope = review_scope

    def generate(self, task_id: str, context: ReviewContext | RepositoryContext) -> ReportResult:
        if self.review_engine == "v3_single_agent":
            report, draft, agent_states, review_state = self._generate_v3_single_agent(task_id, context)
        elif self.review_engine == "v3_multi_agent":
            report, draft, agent_states, review_state = self._generate_v3_multi_agent(task_id, context)
        else:
            prompt = self._build_prompt(context)
            raw_report = self.llm_client.generate_review(prompt)
            report = self._normalize_report(raw_report, context)
            draft, agent_states, review_state = None, [], None
        if self.review_scope is not None and self.review_scope.is_diff_mode:
            report = report.rstrip() + "\n\n" + self._diff_scope_section(as_review_context(context)) + "\n"
        export_path = self.reports_path / f"{task_id}.md"
        export_path.write_text(report, encoding="utf-8")
        return ReportResult(
            report=report,
            export_path=export_path,
            structured_draft=draft,
            agent_states=agent_states,
            review_state=review_state,
        )

    def _generate_v3_single_agent(
        self,
        task_id: str,
        context: ReviewContext | RepositoryContext,
    ) -> tuple[str, StructuredReviewDraft | None, list[AgentExecutionState], ReviewState]:
        review_context = as_review_context(context)
        state = ReviewState(task_id=task_id, context=review_context)
        draft: StructuredReviewDraft | None = None
        agent_states: list[AgentExecutionState] = []
        started = time.perf_counter()
        try:
            agent = ArchitectureAgent(self.llm_client, model=self.token_model)
            agent.set_candidate_paths(self._candidate_paths(review_context))
            draft = agent.review(review_context)
            duration_seconds = time.perf_counter() - started
            state.evidence_bundles[agent.role] = list(agent.last_evidence_bundle)
            state.validated_findings = draft.findings
            agent_states = [
                AgentOrchestrator.build_completed_state(
                    agent.role,
                    draft.findings,
                    agent,
                    duration_seconds=duration_seconds,
                )
            ]
            state.agent_results = agent_states
            state.metadata.update(AgentOrchestrator.build_retrieval_summary_metadata(agent_states))
        except Exception as exc:
            agent_states = [
                AgentExecutionState(
                    agent_id=ArchitectureAgent.role,
                    status="failed",
                    error=str(exc),
                    validation_status="failed",
                    metadata={"duration_seconds": round(time.perf_counter() - started, 6)},
                )
            ]
            state.agent_results = agent_states
            state.errors[ArchitectureAgent.role] = str(exc)
        return self.report_composer.compose(review_context, draft, agent_states), draft, agent_states, state

    def _generate_v3_multi_agent(
        self,
        task_id: str,
        context: ReviewContext | RepositoryContext,
    ) -> tuple[str, StructuredReviewDraft | None, list[AgentExecutionState], ReviewState | None]:
        review_context = as_review_context(context)
        draft: StructuredReviewDraft | None = None
        agent_states: list[AgentExecutionState] = []
        review_state: ReviewState | None = None
        try:
            result = AgentOrchestrator(
                self.llm_client,
                model=self.token_model,
                per_agent_token_budget=max(1000, self.prompt_renderer.token_budgeter.budget // 4),
                candidate_paths=self._candidate_paths(review_context),
            ).review(review_context, task_id=task_id)
            draft = result.draft
            agent_states = result.agent_states
            review_state = result.state
        except Exception:
            draft = None

        report = self.report_composer.compose(review_context, draft, agent_states)
        return report, draft, agent_states, review_state

    def _build_prompt(self, context: ReviewContext | RepositoryContext) -> str:
        return self.prompt_renderer.render(context)

    def _fit_to_token_budget(self, prompt: str) -> str:
        return self.prompt_renderer.token_budgeter.fit(prompt)

    def _count_prompt_tokens(self, prompt: str) -> int:
        return self.prompt_renderer.token_budgeter.count(prompt)

    def _normalize_report(self, report: str, context: RepositoryContext | None = None) -> str:
        return self.markdown_adapter.normalize(report, context)

    def _candidate_paths(self, context: ReviewContext) -> set[str] | None:
        if self.review_scope is None:
            return None
        return self.review_scope.candidate_paths(context)

    def _diff_scope_section(self, context: ReviewContext) -> str:
        assert self.review_scope is not None
        metadata = self.review_scope.metadata(context)
        changed_files = metadata["changed_files"]
        candidate_files = metadata["candidate_files"]
        changed_lines = [f"- `{path}`" for path in changed_files] or ["- None matched supported source files."]
        candidate_lines = [f"- `{path}`" for path in candidate_files] or ["- None."]
        return "\n".join(
            [
                "# Diff Review Scope",
                f"- Source: {self.review_scope.source}",
                f"- Dependency-neighbor context: {str(self.review_scope.include_dependency_neighbors).lower()}",
                "",
                "## Changed Files",
                *changed_lines,
                "",
                "## Reviewed Files And Neighbors",
                *candidate_lines,
            ]
        )
