from __future__ import annotations

from pathlib import Path

from backend.llm.client import LLMClient
from backend.models.context import RepositoryContext, ReviewContext, as_review_context
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

    def generate(self, task_id: str, context: ReviewContext | RepositoryContext) -> tuple[str, Path]:
        prompt = self._build_prompt(context)
        raw_report = self.llm_client.generate_review(prompt)
        report = self._normalize_report(raw_report, context)
        export_path = self.reports_path / f"{task_id}.md"
        export_path.write_text(report, encoding="utf-8")
        return report, export_path

    def _build_prompt(self, context: ReviewContext | RepositoryContext) -> str:
        return self.prompt_renderer.render(context)

    def _fit_to_token_budget(self, prompt: str) -> str:
        return self.prompt_renderer.token_budgeter.fit(prompt)

    def _count_prompt_tokens(self, prompt: str) -> int:
        return self.prompt_renderer.token_budgeter.count(prompt)

    def _normalize_report(self, report: str, context: RepositoryContext | None = None) -> str:
        return self.markdown_adapter.normalize(report, context)

    @staticmethod
    def _repository_insights_section(context: RepositoryContext) -> str:
        return MarkdownReviewAdapter.repository_insights_section(as_review_context(context))

    @staticmethod
    def _architecture_graph_section(context: RepositoryContext) -> str:
        return MarkdownReviewAdapter.architecture_graph_section(as_review_context(context))

    @staticmethod
    def _important_dependency_relationships(
        context: ReviewContext | RepositoryContext,
        *,
        limit: int,
    ) -> list[tuple[str, str]]:
        return PromptRenderer.important_dependency_relationships(context, limit=limit)

    @staticmethod
    def _extract_sections(report: str) -> dict[str, str]:
        return MarkdownReviewAdapter.extract_sections(report)
