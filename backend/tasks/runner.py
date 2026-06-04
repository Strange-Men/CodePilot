from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from backend.core.config import Settings
from backend.llm.client import build_llm_client
from backend.models.review import ReviewStatus
from backend.parsers.python_parser import PythonParser
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


class ReviewTaskRunner:
    def __init__(self, settings: Settings, store: ReviewStore) -> None:
        self.settings = settings
        self.store = store
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="codepilot-review")

    def submit(self, repo_url: str) -> str:
        task_id = uuid4().hex
        self.store.create_review(task_id, repo_url)
        self.executor.submit(self._run, task_id, repo_url)
        return task_id

    def _run(self, task_id: str, repo_url: str) -> None:
        clone_service = CloneService(self.settings.workspace_path)
        try:
            logger.info("event=task_started task_id=%s repo_url=%s", task_id, repo_url)

            self.store.update_status(task_id, ReviewStatus.cloning)
            logger.info("event=clone_started task_id=%s repo_url=%s", task_id, repo_url)
            repo_dir = clone_service.clone(repo_url, task_id)
            logger.info("event=clone_completed task_id=%s repo_dir=%s", task_id, repo_dir)

            self.store.update_status(task_id, ReviewStatus.parsing)
            logger.info("event=parse_started task_id=%s repo_dir=%s", task_id, repo_dir)
            parser = PythonParser()
            indexer = RepositoryIndexer(parser, self.settings.max_files, self.settings.max_file_size_bytes)
            context = indexer.build_context(repo_dir, repo_url)
            logger.info(
                "event=parse_completed task_id=%s total_python_files=%s analyzed_files=%s skipped_files=%s",
                task_id,
                context.total_python_files,
                context.analyzed_files,
                context.skipped_files,
            )

            self.store.update_status(task_id, ReviewStatus.summarizing)
            logger.info("event=summarize_completed task_id=%s file_summaries=%s", task_id, len(context.file_summaries))
            # Summaries are deterministic and generated during indexing for the MVP.

            self.store.update_status(task_id, ReviewStatus.reviewing)
            logger.info("event=review_started task_id=%s", task_id)
            report_generator = ReportGenerator(
                build_llm_client(self.settings),
                self.settings.reports_path,
                self.settings.final_prompt_token_budget,
            )
            logger.info("event=export_started task_id=%s", task_id)
            report, export_path = report_generator.generate(task_id, context)
            logger.info("event=export_completed task_id=%s export_path=%s", task_id, export_path)
            logger.info("event=review_completed task_id=%s report_chars=%s", task_id, len(report))

            self.store.update_status(
                task_id,
                ReviewStatus.completed,
                report_markdown=report,
                export_path=str(export_path),
            )
            logger.info("event=task_completed task_id=%s", task_id)
        except Exception as exc:
            logger.exception("event=task_failed task_id=%s repo_url=%s", task_id, repo_url)
            self.store.update_status(task_id, ReviewStatus.failed, error=str(exc))
        finally:
            try:
                logger.info("event=workspace_cleanup_started task_id=%s", task_id)
                clone_service.cleanup(task_id)
                logger.info("event=workspace_cleanup_completed task_id=%s", task_id)
            except Exception:
                logger.exception("event=workspace_cleanup_failed task_id=%s", task_id)
