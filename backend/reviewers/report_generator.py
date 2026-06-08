from __future__ import annotations

from pathlib import Path

from backend.agents.architecture_agent import ArchitectureAgent
from backend.agents.orchestrator import AgentOrchestrator
from backend.core.report_contract import REPORT_SECTIONS
from backend.llm.client import LLMClient
from backend.models.context import RepositoryContext, ReviewContext, as_review_context
from backend.models.review_state import AgentExecutionState, ReviewState
from backend.models.structured_review import StructuredReviewDraft
from backend.prompts import PromptRenderer
from backend.reviewers.markdown_adapter import MarkdownReviewAdapter


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
        self.review_engine = "v2"
        self.token_model = token_model
        self.last_structured_draft: StructuredReviewDraft | None = None
        self.last_agent_states: list[AgentExecutionState] = []
        self.last_review_state: ReviewState | None = None

    def configure_engine(self, review_engine: str) -> None:
        self.review_engine = review_engine

    def generate(self, task_id: str, context: ReviewContext | RepositoryContext) -> tuple[str, Path]:
        self.last_structured_draft = None
        self.last_agent_states = []
        self.last_review_state = None
        if self.review_engine == "v3_single_agent":
            report = self._generate_v3_single_agent(task_id, context)
        elif self.review_engine == "v3_multi_agent":
            report = self._generate_v3_multi_agent(task_id, context)
        else:
            prompt = self._build_prompt(context)
            raw_report = self.llm_client.generate_review(prompt)
            report = self._normalize_report(raw_report, context)
        export_path = self.reports_path / f"{task_id}.md"
        export_path.write_text(report, encoding="utf-8")
        return report, export_path

    def _generate_v3_single_agent(self, task_id: str, context: ReviewContext | RepositoryContext) -> str:
        review_context = as_review_context(context)
        state = ReviewState(task_id=task_id, context=review_context)
        try:
            agent = ArchitectureAgent(self.llm_client, model=self.token_model)
            draft = agent.review(review_context)
            self.last_structured_draft = draft
            state.evidence_bundles[agent.role] = list(agent.last_evidence_bundle)
            state.validated_findings = draft.findings
            self.last_agent_states = [
                AgentOrchestrator._completed_state(agent.role, draft.findings, agent)
            ]
            state.agent_results = self.last_agent_states
            state.metadata.update(AgentOrchestrator._retrieval_summary_metadata(self.last_agent_states))
            architecture_body = draft.section_markdown(REPORT_SECTIONS[0])
        except Exception as exc:
            self.last_agent_states = [
                AgentExecutionState(
                    agent_id=ArchitectureAgent.role,
                    status="failed",
                    error=str(exc),
                    validation_status="failed",
                )
            ]
            state.agent_results = self.last_agent_states
            state.errors[ArchitectureAgent.role] = str(exc)
            architecture_body = ""
        self.last_review_state = state
        if not architecture_body:
            architecture_body = (
                "No validated evidence-grounded architecture findings were produced. "
                "CodePilot preserved the four-section report contract and skipped unsupported claims."
            )
        raw_report = (
            f"# {REPORT_SECTIONS[0]}\n"
            f"{architecture_body}\n\n"
            f"# {REPORT_SECTIONS[1]}\n"
            "No validated evidence-grounded code smell findings were produced by the single-agent V3 engine.\n\n"
            f"# {REPORT_SECTIONS[2]}\n"
            "No validated evidence-grounded maintainability findings were produced by the single-agent V3 engine.\n\n"
            f"# {REPORT_SECTIONS[3]}\n"
            "No validated evidence-grounded refactoring findings were produced by the single-agent V3 engine.\n"
        )
        return self._normalize_report(raw_report, review_context)

    def _generate_v3_multi_agent(self, task_id: str, context: ReviewContext | RepositoryContext) -> str:
        review_context = as_review_context(context)
        try:
            result = AgentOrchestrator(
                self.llm_client,
                model=self.token_model,
                per_agent_token_budget=max(1000, self.prompt_renderer.token_budgeter.budget // 4),
            ).review(review_context, task_id=task_id)
            draft = result.draft
            self.last_structured_draft = draft
            self.last_agent_states = result.agent_states
            self.last_review_state = result.state
        except Exception:
            draft = None

        section_bodies: list[str] = []
        for section in REPORT_SECTIONS:
            body = draft.section_markdown(section) if draft is not None else ""
            if not body:
                body = f"No validated evidence-grounded {section.lower()} findings were produced."
            section_bodies.append(f"# {section}\n{body}")
        return self._normalize_report("\n\n".join(section_bodies) + "\n", review_context)

    def _build_prompt(self, context: ReviewContext | RepositoryContext) -> str:
        return self.prompt_renderer.render(context)

    def _fit_to_token_budget(self, prompt: str) -> str:
        return self.prompt_renderer.token_budgeter.fit(prompt)

    def _count_prompt_tokens(self, prompt: str) -> int:
        return self.prompt_renderer.token_budgeter.count(prompt)

    def _normalize_report(self, report: str, context: RepositoryContext | None = None) -> str:
        return self.markdown_adapter.normalize(report, context)

