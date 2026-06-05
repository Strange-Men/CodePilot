from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from backend.core.config import Settings
from backend.llm.client import LLMClient
from backend.models.review import RepositoryContext, ReviewStatus
from backend.parsers.registry import ParserRegistry, default_parser_registry
from backend.reviewers.report_generator import ReportGenerator
from backend.services.clone_service import CloneService
from backend.services.indexer import RepositoryIndexer
from backend.storage.sqlite import ReviewStore

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False

CloneServiceFactory = Callable[[Path], CloneService]
IndexerFactory = Callable[..., RepositoryIndexer]
ReportGeneratorFactory = Callable[..., ReportGenerator]


class ReviewPipeline:
    def __init__(
        self,
        settings: Settings,
        store: ReviewStore,
        llm_client: LLMClient,
        parser_registry: ParserRegistry | None = None,
        clone_service_factory: CloneServiceFactory | None = None,
        indexer_factory: IndexerFactory | None = None,
        report_generator_factory: ReportGeneratorFactory | None = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.llm_client = llm_client
        self.parser_registry = parser_registry or default_parser_registry
        self.clone_service_factory = clone_service_factory or CloneService
        self.indexer_factory = indexer_factory or RepositoryIndexer
        self.report_generator_factory = report_generator_factory or ReportGenerator

    def run(self, task_id: str, repo_url: str) -> None:
        clone_service = self.clone_service_factory(self.settings.workspace_path)
        try:
            logger.info("event=task_started task_id=%s repo_url=%s", task_id, repo_url)

            repo_dir = self._clone_repository(clone_service, task_id, repo_url)
            context = self._build_context(task_id, repo_dir, repo_url)
            self._record_summarized(task_id, context)
            report, export_path = self._generate_report(task_id, context)
            self._complete_review(task_id, report, export_path)
        except Exception as exc:
            self._fail_review(task_id, repo_url, exc)
        finally:
            self._cleanup_workspace(clone_service, task_id)

    def _clone_repository(self, clone_service: CloneService, task_id: str, repo_url: str) -> Path:
        self.store.update_status(task_id, ReviewStatus.cloning)
        logger.info("event=clone_started task_id=%s repo_url=%s", task_id, repo_url)
        repo_dir = clone_service.clone(repo_url, task_id)
        logger.info("event=clone_completed task_id=%s repo_dir=%s", task_id, repo_dir)
        return repo_dir

    def _build_context(self, task_id: str, repo_dir: Path, repo_url: str) -> RepositoryContext:
        self.store.update_status(task_id, ReviewStatus.parsing)
        logger.info("event=parse_started task_id=%s repo_dir=%s", task_id, repo_dir)
        parser = self.parser_registry.create("python")
        indexer = self.indexer_factory(parser, self.settings.max_files, self.settings.max_file_size_bytes)
        context = indexer.build_context(repo_dir, repo_url)
        logger.info(
            "event=parse_completed task_id=%s total_python_files=%s analyzed_files=%s skipped_files=%s",
            task_id,
            context.total_python_files,
            context.analyzed_files,
            context.skipped_files,
        )
        return context

    def _record_summarized(self, task_id: str, context: RepositoryContext) -> None:
        self.store.update_status(task_id, ReviewStatus.summarizing)
        logger.info("event=summarize_completed task_id=%s file_summaries=%s", task_id, len(context.file_summaries))
        # Summaries are deterministic and generated during indexing for the MVP.

    def _generate_report(self, task_id: str, context: RepositoryContext) -> tuple[str, Path]:
        self.store.update_status(task_id, ReviewStatus.reviewing)
        logger.info("event=review_started task_id=%s", task_id)
        report_generator = self.report_generator_factory(
            self.llm_client,
            self.settings.reports_path,
            self.settings.final_prompt_token_budget,
        )
        logger.info("event=export_started task_id=%s", task_id)
        report, export_path = report_generator.generate(task_id, context)
        logger.info("event=export_completed task_id=%s export_path=%s", task_id, export_path)
        logger.info("event=review_completed task_id=%s report_chars=%s", task_id, len(report))
        return report, export_path

    def _complete_review(self, task_id: str, report: str, export_path: Path) -> None:
        self.store.update_status(
            task_id,
            ReviewStatus.completed,
            report_markdown=report,
            export_path=str(export_path),
        )
        logger.info("event=task_completed task_id=%s", task_id)

    def _fail_review(self, task_id: str, repo_url: str, exc: Exception) -> None:
        logger.exception("event=task_failed task_id=%s repo_url=%s", task_id, repo_url)
        self.store.update_status(task_id, ReviewStatus.failed, error=str(exc))

    @staticmethod
    def _cleanup_workspace(clone_service: CloneService, task_id: str) -> None:
        try:
            logger.info("event=workspace_cleanup_started task_id=%s", task_id)
            clone_service.cleanup(task_id)
            logger.info("event=workspace_cleanup_completed task_id=%s", task_id)
        except Exception:
            logger.exception("event=workspace_cleanup_failed task_id=%s", task_id)
