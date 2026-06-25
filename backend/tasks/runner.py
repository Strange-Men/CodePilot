from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import monotonic
from uuid import uuid4

from backend.api.errors import APIError
from backend.core.config import Settings
from backend.core.logging import get_logger
from backend.llm.client import LLMClient, build_llm_client, build_llm_client_for_mode
from backend.models.review import AgentProgressItem, ReviewProgressSnapshot
from backend.models.review_state import AgentExecutionState
from backend.parsers.registry import ParserRegistry, default_parser_registry
from backend.storage.sqlite import ReviewStore
from backend.tasks.pipeline import ReviewPipeline, ReviewPipelineResult

logger = get_logger(__name__)

PLANNED_AGENTS = (
    ("ArchitectureAgent", "A1 ArchitectureAgent"),
    ("CodeSmellAgent", "A2 CodeSmellAgent"),
    ("MaintainabilityAgent", "A3 MaintainabilityAgent"),
    ("RefactorAgent", "A4 RefactorAgent"),
)
COMPLETED_PROGRESS_TTL_SECONDS = 10 * 60
FAILED_PROGRESS_TTL_SECONDS = 60 * 60


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
        self.pipeline = ReviewPipeline(
            settings,
            store,
            self.llm_client,
            self.parser_registry,
        )
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="codepilot-review")
        self._progress: dict[str, ReviewProgressSnapshot] = {}
        self._progress_terminal_at: dict[str, tuple[float, float]] = {}
        self._progress_lock = Lock()
        self._shutdown = False

    def submit(
        self,
        repo_url: str,
        llm_mode: str = "mock",
        llm_provider: str | None = None,
    ) -> str:
        if self._shutdown:
            raise RuntimeError("Review task runner is shut down.")
        if llm_mode != "mock":
            try:
                build_llm_client_for_mode(self.settings, llm_mode, llm_provider)
            except (RuntimeError, ValueError) as exc:
                raise APIError(
                    400,
                    "LLM configuration error",
                    "llm_config_error",
                    str(exc),
                ) from exc
        task_id = uuid4().hex
        self.store.create_review(task_id, repo_url)
        self._initialize_progress(task_id)
        self.executor.submit(self._run, task_id, repo_url, llm_mode, llm_provider)
        return task_id

    def _run(
        self,
        task_id: str,
        repo_url: str,
        llm_mode: str = "mock",
        llm_provider: str | None = None,
    ) -> ReviewPipelineResult:
        llm_client = build_llm_client_for_mode(self.settings, llm_mode, llm_provider)
        pipeline = ReviewPipeline(
            self.settings,
            self.store,
            llm_client,
            self.parser_registry,
            clone_service_factory=self.pipeline.clone_service_factory,
            indexer_factory=self.pipeline.indexer_factory,
            report_generator_factory=self.pipeline.report_generator_factory,
            review_scope=self.pipeline.review_scope,
            progress_callback=lambda event, agent_id, agent_state: self._update_progress(
                task_id,
                event,
                agent_id,
                agent_state,
            ),
        )
        return pipeline.run(task_id, repo_url)

    def get_progress(self, task_id: str) -> ReviewProgressSnapshot | None:
        with self._progress_lock:
            self._cleanup_progress_locked(monotonic())
            snapshot = self._progress.get(task_id)
            return snapshot.model_copy(deep=True) if snapshot is not None else None

    def cleanup_progress(self, now: float | None = None) -> None:
        with self._progress_lock:
            self._cleanup_progress_locked(monotonic() if now is None else now)

    def clear_progress(self, task_id: str) -> None:
        with self._progress_lock:
            self._progress.pop(task_id, None)
            self._progress_terminal_at.pop(task_id, None)

    def _initialize_progress(self, task_id: str) -> None:
        if self.settings.review_engine != "v3_multi_agent":
            return
        agents = [
            AgentProgressItem(order=index, label=label, agent_id=agent_id)
            for index, (agent_id, label) in enumerate(PLANNED_AGENTS, start=1)
        ]
        with self._progress_lock:
            self._cleanup_progress_locked(monotonic())
            self._progress[task_id] = ReviewProgressSnapshot(
                current_phase="Preparing repository",
                total_agents=len(agents),
                completed_agents=0,
                agents=agents,
            )
            self._progress_terminal_at.pop(task_id, None)

    def _update_progress(
        self,
        task_id: str,
        event: str,
        agent_id: str | None = None,
        agent_state: AgentExecutionState | None = None,
    ) -> None:
        with self._progress_lock:
            now = monotonic()
            self._cleanup_progress_locked(now)
            snapshot = self._progress.get(task_id)
            if snapshot is None:
                return
            phase_labels = {
                "repository_intake": "Preparing repository",
                "sandbox_parsing": "Building sandbox context",
                "evidence_retrieval": "Retrieving evidence",
                "report_composer": "Composing report",
                "done": "Completed",
                "task_failed": "Review failed",
            }
            if event in phase_labels:
                snapshot.current_phase = phase_labels[event]
                if event in {"report_composer", "done", "task_failed"}:
                    snapshot.current_agent_id = None
                if event == "task_failed":
                    for item in snapshot.agents:
                        if item.status == "running":
                            item.status = "failed"
                            item.error = "Agent execution failed."
                    self._progress_terminal_at[task_id] = (
                        now,
                        FAILED_PROGRESS_TTL_SECONDS,
                    )
                elif event == "done":
                    self._progress_terminal_at[task_id] = (
                        now,
                        COMPLETED_PROGRESS_TTL_SECONDS,
                    )
                else:
                    self._progress_terminal_at.pop(task_id, None)
                return
            self._progress_terminal_at.pop(task_id, None)
            item = next(
                (candidate for candidate in snapshot.agents if candidate.agent_id == agent_id),
                None,
            )
            if item is None:
                return
            if event == "agent_running":
                item.status = "running"
                snapshot.current_agent_id = item.agent_id
                snapshot.current_phase = f"Running {item.agent_id}"
            elif event == "agent_completed":
                item.status = "completed"
                item.findings_count = len(agent_state.findings) if agent_state is not None else 0
                item.evidence_count = len(set(agent_state.evidence_ids)) if agent_state is not None else 0
            elif event == "agent_failed":
                item.status = "failed"
                item.findings_count = 0
                item.evidence_count = 0
                item.error = "Agent execution failed."
            snapshot.completed_agents = sum(
                item.status == "completed"
                for item in snapshot.agents
            )

    def _cleanup_progress_locked(self, now: float) -> None:
        expired_task_ids = []
        for task_id, (terminal_at, ttl_seconds) in self._progress_terminal_at.items():
            snapshot = self._progress.get(task_id)
            if snapshot is None:
                expired_task_ids.append(task_id)
                continue
            if snapshot.current_phase not in {"Completed", "Review failed"}:
                continue
            if any(item.status == "running" for item in snapshot.agents):
                continue
            if now - terminal_at >= ttl_seconds:
                expired_task_ids.append(task_id)
        for task_id in expired_task_ids:
            self._progress.pop(task_id, None)
            self._progress_terminal_at.pop(task_id, None)

    def shutdown(self, wait: bool = True) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        self.executor.shutdown(wait=wait, cancel_futures=False)
