from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from backend.core.config import Settings
from backend.core.logging import get_logger
from backend.llm.client import LLMClient, build_llm_client
from backend.parsers.registry import ParserRegistry, default_parser_registry
from backend.storage.sqlite import ReviewStore
from backend.tasks.pipeline import ReviewPipeline, ReviewPipelineResult

logger = get_logger(__name__)


class ReviewTaskRunner:
    def __init__(
        self,
        settings: Settings,
        store: ReviewStore,
        parser_registry: ParserRegistry | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.parser_registry = parser_registry or default_parser_registry
        self.llm_client = llm_client if llm_client is not None else build_llm_client(settings)
        self.pipeline = ReviewPipeline(settings, store, self.llm_client, self.parser_registry)
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="codepilot-review")

    def submit(self, repo_url: str) -> str:
        task_id = uuid4().hex
        self.store.create_review(task_id, repo_url)
        self.executor.submit(self._run, task_id, repo_url)
        return task_id

    def _run(self, task_id: str, repo_url: str) -> ReviewPipelineResult:
        return self.pipeline.run(task_id, repo_url)
