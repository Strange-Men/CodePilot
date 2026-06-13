from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from backend.api.errors import APIError
from backend.core.config import Settings
from backend.core.logging import get_logger
from backend.llm.client import LLMClient, build_llm_client, build_llm_client_for_mode
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
        self._shutdown = False

    def submit(self, repo_url: str, llm_mode: str = "mock") -> str:
        if self._shutdown:
            raise RuntimeError("Review task runner is shut down.")
        if llm_mode != "mock":
            try:
                build_llm_client_for_mode(self.settings, llm_mode)
            except RuntimeError as exc:
                raise APIError(
                    400,
                    "LLM configuration error",
                    "llm_config_error",
                    str(exc),
                ) from exc
        task_id = uuid4().hex
        self.store.create_review(task_id, repo_url)
        self.executor.submit(self._run, task_id, repo_url, llm_mode)
        return task_id

    def _run(self, task_id: str, repo_url: str, llm_mode: str = "mock") -> ReviewPipelineResult:
        if llm_mode == "mock":
            return self.pipeline.run(task_id, repo_url)
        llm_client = build_llm_client_for_mode(self.settings, llm_mode)
        pipeline = ReviewPipeline(
            self.settings, self.store, llm_client, self.parser_registry
        )
        return pipeline.run(task_id, repo_url)

    def shutdown(self, wait: bool = True) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        self.executor.shutdown(wait=wait, cancel_futures=False)
