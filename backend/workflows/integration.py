from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from backend.core.config import Settings, get_settings
from backend.llm.client import build_llm_client
from backend.models.review import ReviewStatus
from backend.models.review_scope import ReviewScope
from backend.storage.sqlite import ReviewStore
from backend.tasks.pipeline import ReviewPipeline

SEVERITY_ORDER = {
    "none": 99,
    "info": 0,
    "informational": 0,
    "low": 1,
    "minor": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


@dataclass(frozen=True)
class CIExitPolicy:
    fail_on: str = "none"

    def exit_code(self, summary: dict) -> int:
        review = summary.get("review") or {}
        if review.get("status") == ReviewStatus.failed.value:
            return 1
        threshold = SEVERITY_ORDER.get(self.fail_on.lower(), SEVERITY_ORDER["none"])
        if threshold == SEVERITY_ORDER["none"]:
            return 0
        for finding in summary.get("structured_findings", []):
            severity = str(finding.get("severity", "")).lower()
            if SEVERITY_ORDER.get(severity, -1) >= threshold:
                return 1
        return 0


@dataclass(frozen=True)
class ReviewWorkflowResult:
    task_id: str
    summary: dict
    markdown_path: Path | None = None
    json_path: Path | None = None

    @property
    def status(self) -> str:
        return str((self.summary.get("review") or {}).get("status", "unknown"))


class ReviewWorkflow:
    def __init__(
        self,
        settings: Settings | None = None,
        store: ReviewStore | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.store = store or ReviewStore(self.settings.database_path)

    def run_review(
        self,
        repo_url: str,
        *,
        engine_mode: str | None = None,
        use_mock_llm: bool | None = None,
        output_path: Path | None = None,
        json_output_path: Path | None = None,
        review_scope: ReviewScope | None = None,
        task_id: str | None = None,
    ) -> ReviewWorkflowResult:
        settings = self._settings_for_run(engine_mode, use_mock_llm, review_scope)
        task_id = task_id or uuid4().hex
        self.store.create_review(task_id, repo_url)
        pipeline = ReviewPipeline(
            settings,
            self.store,
            build_llm_client(settings),
            review_scope=review_scope,
        )
        pipeline.run(task_id, repo_url)
        summary = build_review_summary(self.store, task_id, review_scope=review_scope)
        markdown_path = self._write_markdown(summary, output_path)
        json_path = self._write_json(summary, json_output_path)
        return ReviewWorkflowResult(
            task_id=task_id,
            summary=summary,
            markdown_path=markdown_path,
            json_path=json_path,
        )

    def get_review_status(self, task_id: str) -> dict:
        review = self.store.get_review(task_id)
        return {"task_id": task_id, "found": review is not None, "review": review}

    def get_review_findings(self, task_id: str) -> list[dict]:
        return self.store.get_structured_findings(task_id)

    def get_review_report(self, task_id: str) -> dict:
        review = self.store.get_review(task_id)
        if review is None:
            return {"task_id": task_id, "found": False, "report_markdown": None}
        return {
            "task_id": task_id,
            "found": True,
            "status": review["status"],
            "report_markdown": review.get("report_markdown"),
            "export_path": review.get("export_path"),
        }

    def get_review_evidence(self, task_id: str) -> list[dict]:
        return self.store.get_evidence_refs(task_id)

    def _settings_for_run(
        self,
        engine_mode: str | None,
        use_mock_llm: bool | None,
        review_scope: ReviewScope | None,
    ) -> Settings:
        engine = engine_mode or self.settings.review_engine
        if review_scope is not None and review_scope.is_diff_mode and engine_mode is None:
            engine = "v3_multi_agent"
        settings = self.settings.model_copy(
            update={
                "review_engine": engine,
                "use_mock_llm": self.settings.use_mock_llm if use_mock_llm is None else use_mock_llm,
            }
        )
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        settings.workspace_path.mkdir(parents=True, exist_ok=True)
        settings.reports_path.mkdir(parents=True, exist_ok=True)
        return settings

    @staticmethod
    def _write_markdown(summary: dict, output_path: Path | None) -> Path | None:
        if output_path is None:
            export_path = (summary.get("review") or {}).get("export_path")
            return Path(export_path) if export_path else None
        output_path.parent.mkdir(parents=True, exist_ok=True)
        export_path = (summary.get("review") or {}).get("export_path")
        if export_path and Path(export_path).exists():
            shutil.copyfile(export_path, output_path)
        else:
            output_path.write_text((summary.get("review") or {}).get("report_markdown") or "", encoding="utf-8")
        return output_path

    @staticmethod
    def _write_json(summary: dict, json_output_path: Path | None) -> Path | None:
        if json_output_path is None:
            return None
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        return json_output_path


def build_review_summary(
    store: ReviewStore,
    task_id: str,
    *,
    review_scope: ReviewScope | None = None,
) -> dict:
    inspection = store.inspect_review(task_id)
    if inspection is None:
        return {"task_id": task_id, "found": False}
    summary = {
        "task_id": task_id,
        "found": True,
        "review": inspection["review"],
        "structured_findings": inspection["structured_findings"],
        "evidence_refs": inspection["evidence_refs"],
        "agent_states": inspection["agent_states"],
        "review_state": inspection["review_state"],
    }
    if review_scope is not None:
        summary["workflow_scope"] = {
            "source": review_scope.source,
            "changed_files": sorted(review_scope.changed_paths),
            "include_dependency_neighbors": review_scope.include_dependency_neighbors,
        }
    return summary
