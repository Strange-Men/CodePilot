from __future__ import annotations

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
        try:
            self.store.update_status(task_id, ReviewStatus.cloning)
            repo_dir = CloneService(self.settings.workspace_path).clone(repo_url, task_id)

            self.store.update_status(task_id, ReviewStatus.parsing)
            parser = PythonParser()
            indexer = RepositoryIndexer(parser, self.settings.max_files, self.settings.max_file_size_bytes)
            context = indexer.build_context(repo_dir, repo_url)

            self.store.update_status(task_id, ReviewStatus.summarizing)
            # Summaries are deterministic and generated during indexing for the MVP.

            self.store.update_status(task_id, ReviewStatus.reviewing)
            report, export_path = ReportGenerator(
                build_llm_client(self.settings),
                self.settings.reports_path,
                self.settings.final_prompt_token_budget,
            ).generate(task_id, context)

            self.store.update_status(
                task_id,
                ReviewStatus.completed,
                report_markdown=report,
                export_path=str(export_path),
            )
        except Exception as exc:
            self.store.update_status(task_id, ReviewStatus.failed, error=str(exc))

