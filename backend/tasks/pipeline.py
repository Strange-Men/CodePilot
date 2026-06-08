from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from backend.core.config import Settings
from backend.core.logging import get_logger
from backend.llm.client import LLMClient
from backend.models.context import RepositoryContext, ReviewContext
from backend.models.review import ReviewStatus
from backend.parsers.base import SourceParser
from backend.parsers.composite import CompositeSourceParser
from backend.parsers.registry import ParserRegistry, default_parser_registry
from backend.reviewers.report_generator import ReportGenerator
from backend.services.clone_service import CloneService
from backend.services.indexer import RepositoryIndexer
from backend.services.sandbox import SandboxFilter, SandboxManifest
from backend.storage.sqlite import ReviewStore

logger = get_logger(__name__)

CloneServiceFactory = Callable[[Path], CloneService]
IndexerFactory = Callable[..., RepositoryIndexer]
ReportGeneratorFactory = Callable[..., ReportGenerator]


@dataclass(frozen=True)
class ReviewPipelineResult:
    total_python_files: int = 0
    analyzed_files: int = 0
    skipped_files: int = 0

    @property
    def total_source_files(self) -> int:
        return self.total_python_files


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

    def run(self, task_id: str, repo_url: str) -> ReviewPipelineResult:
        clone_service = self.clone_service_factory(self.settings.workspace_path)
        result = ReviewPipelineResult()
        try:
            logger.info("event=task_started task_id=%s repo_url=%s", task_id, repo_url)

            repo_dir = self._clone_repository(clone_service, task_id, repo_url)
            manifest = self._build_manifest(repo_dir)
            context = self._build_context(task_id, repo_dir, repo_url, manifest)
            result = ReviewPipelineResult(
                total_python_files=context.total_python_files,
                analyzed_files=context.analyzed_files,
                skipped_files=context.skipped_files,
            )
            self._record_summarized(task_id, context)
            report, export_path = self._generate_report(task_id, context)
            self._complete_review(task_id, report, export_path)
        except Exception as exc:
            self._fail_review(task_id, repo_url, exc)
        finally:
            self._cleanup_workspace(clone_service, task_id)
        return result

    def _clone_repository(self, clone_service: CloneService, task_id: str, repo_url: str) -> Path:
        self.store.update_status(task_id, ReviewStatus.cloning)
        logger.info("event=clone_started task_id=%s repo_url=%s", task_id, repo_url)
        repo_dir = clone_service.clone(repo_url, task_id)
        logger.info("event=clone_completed task_id=%s repo_dir=%s", task_id, repo_dir)
        return repo_dir

    def _build_manifest(self, repo_dir: Path) -> SandboxManifest:
        return SandboxFilter().build_manifest(
            repo_dir,
            self.settings.max_files,
            self.settings.max_file_size_bytes,
        )

    def _build_context(
        self,
        task_id: str,
        repo_dir: Path,
        repo_url: str,
        manifest: SandboxManifest,
    ) -> ReviewContext:
        self.store.update_status(task_id, ReviewStatus.parsing)
        logger.info("event=parse_started task_id=%s repo_dir=%s", task_id, repo_dir)
        parser = self._select_parser(repo_dir, manifest)
        indexer = self.indexer_factory(parser, self.settings.max_files, self.settings.max_file_size_bytes)
        set_manifest = getattr(indexer, "set_manifest", None)
        if callable(set_manifest):
            set_manifest(manifest)
        build_review_context = getattr(indexer, "build_review_context", None)
        if callable(build_review_context):
            context = build_review_context(repo_dir, repo_url)
        else:
            legacy_context: RepositoryContext = indexer.build_context(repo_dir, repo_url)
            context = legacy_context.to_review_context()
        logger.info(
            "event=parse_completed task_id=%s language=%s total_source_files=%s analyzed_files=%s skipped_files=%s",
            task_id,
            parser.language,
            context.total_python_files,
            context.analyzed_files,
            context.skipped_files,
        )
        return context

    def _select_parser(self, repo_dir: Path, manifest: SandboxManifest | None = None) -> SourceParser:
        if manifest is not None and manifest.files:
            manifest_parser = self._select_parser_from_manifest(manifest)
            if manifest_parser is not None:
                return manifest_parser

        fallback_parser: SourceParser | None = None
        matching_parsers: list[SourceParser] = []
        first_parser: SourceParser | None = None

        language_priority = {"python": 0, "javascript": 1, "typescript": 2}
        for language in sorted(
            self.parser_registry.languages(),
            key=lambda item: (language_priority.get(item, 99), item),
        ):
            parser = self.parser_registry.create(language)
            if first_parser is None:
                first_parser = parser
            _files, total, _skipped = parser.discover_files(
                repo_dir,
                self.settings.max_files,
                self.settings.max_file_size_bytes,
            )
            if parser.language == "python":
                fallback_parser = parser
            if total > 0:
                matching_parsers.append(parser)

        if len(matching_parsers) > 1:
            return CompositeSourceParser(matching_parsers)
        if matching_parsers:
            return matching_parsers[0]
        if fallback_parser is not None:
            return fallback_parser
        if first_parser is not None:
            return first_parser
        return self.parser_registry.create("python")

    def _select_parser_from_manifest(self, manifest: SandboxManifest) -> SourceParser | None:
        extensions = {file.extension for file in manifest.files}
        language_extensions = {
            "python": {".py"},
            "javascript": {".js", ".jsx"},
            "typescript": {".ts", ".tsx"},
        }
        languages = [
            language
            for language in self.parser_registry.languages()
            if extensions.intersection(language_extensions.get(language, set()))
        ]
        if not languages:
            return None
        language_priority = {"python": 0, "javascript": 1, "typescript": 2}
        languages = sorted(languages, key=lambda item: (language_priority.get(item, 99), item))
        parsers = [self.parser_registry.create(language) for language in languages]
        return CompositeSourceParser(parsers) if len(parsers) > 1 else parsers[0]

    def _record_summarized(self, task_id: str, context: ReviewContext) -> None:
        self.store.update_status(task_id, ReviewStatus.summarizing)
        logger.info("event=summarize_completed task_id=%s file_summaries=%s", task_id, len(context.file_summaries))
        # Summaries are deterministic and generated during indexing for the MVP.

    def _generate_report(self, task_id: str, context: ReviewContext) -> tuple[str, Path]:
        self.store.update_status(task_id, ReviewStatus.reviewing)
        logger.info("event=review_started task_id=%s", task_id)
        report_generator = self.report_generator_factory(
            self.llm_client,
            self.settings.reports_path,
            self.settings.final_prompt_token_budget,
            token_model=self.settings.openai_model,
        )
        configure_engine = getattr(report_generator, "configure_engine", None)
        if callable(configure_engine):
            configure_engine(self.settings.review_engine)
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
