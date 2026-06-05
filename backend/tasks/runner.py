from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from backend.core.config import Settings
from backend.parsers.registry import ParserRegistry, default_parser_registry
from backend.storage.sqlite import ReviewStore
from backend.tasks.pipeline import ReviewPipeline

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


class ReviewTaskRunner:
    def __init__(
        self,
        settings: Settings,
        store: ReviewStore,
        parser_registry: ParserRegistry | None = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.parser_registry = parser_registry or default_parser_registry
        self.pipeline = ReviewPipeline(settings, store, self.parser_registry)
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="codepilot-review")

    def submit(self, repo_url: str) -> str:
        task_id = uuid4().hex
        self.store.create_review(task_id, repo_url)
        self.executor.submit(self._run, task_id, repo_url)
        return task_id

    def _run(self, task_id: str, repo_url: str) -> None:
        self.pipeline.run(task_id, repo_url)
