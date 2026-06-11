from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

REPORT_MARKDOWN_MAX_CHARS = 5000
RUN_SCHEMA_VERSION = "3.5"


@dataclass(frozen=True)
class DatasetMetadata:
    version: str
    description: str
    path: str
    sha256: str
    repo_count: int


@dataclass(frozen=True)
class DatasetDefinition:
    metadata: DatasetMetadata
    repos: list[dict]


@dataclass(frozen=True)
class EvaluationRepoRecord:
    repo_id: str
    repo_name: str
    repo_url: str
    engine: str
    mode: str
    provider: str | None
    model: str | None
    started_at: str
    ended_at: str
    duration_seconds: float
    status: str
    passed: bool
    quality_checks: dict[str, bool]
    quality_score: float | None
    quality_metrics: dict | None
    failed_checks: list[str]
    usage: dict | None
    report_path: str | None
    report_markdown: str
    findings_count: int
    evidence_count: int
    agent_state_summary: list[dict]


@dataclass
class EvaluationRun:
    run_id: str
    output_dir: Path
    dataset: DatasetMetadata
    engine: str
    mode: str
    provider: str | None
    model: str | None
    started_at: str
    ended_at: str | None = None
    duration_seconds: float | None = None
    repos: list[EvaluationRepoRecord] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema_version": RUN_SCHEMA_VERSION,
            "run_id": self.run_id,
            "dataset": asdict(self.dataset),
            "engine": self.engine,
            "mode": self.mode,
            "provider": self.provider,
            "model": self.model,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": self.duration_seconds,
            "repos": [asdict(repo) for repo in self.repos],
        }


def load_dataset_definition(path: Path) -> DatasetDefinition:
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    version = str(data.get("version") or "").strip()
    if not version:
        raise ValueError(f"Evaluation dataset {path} is missing a version.")
    repos = data.get("repos")
    if not isinstance(repos, list):
        raise ValueError(f"Evaluation dataset {path} must contain a repos list.")

    normalized: list[dict] = []
    for repo in repos:
        entry = dict(repo)
        source = entry.get("source") or {}
        if source.get("type") == "fixture":
            fixture_path = Path(source["path"])
            if not fixture_path.is_absolute():
                fixture_path = (path.parent / fixture_path).resolve()
            entry["fixture_path"] = str(fixture_path)
            entry.setdefault("url", f"fixture://{entry['id']}")
        normalized.append(entry)

    return DatasetDefinition(
        metadata=DatasetMetadata(
            version=version,
            description=str(data.get("description") or ""),
            path=str(path.resolve()),
            sha256=hashlib.sha256(raw).hexdigest(),
            repo_count=len(normalized),
        ),
        repos=normalized,
    )


class EvaluationRunRegistry:
    def __init__(
        self,
        output_root: Path,
        dataset: DatasetMetadata,
        *,
        engine: str,
        mode: str,
        provider: str | None = None,
        model: str | None = None,
        now: datetime | None = None,
    ) -> None:
        started = now or datetime.now(UTC)
        run_id = f"{started.strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
        output_dir = output_root / run_id
        output_dir.mkdir(parents=True, exist_ok=False)
        self.run = EvaluationRun(
            run_id=run_id,
            output_dir=output_dir,
            dataset=dataset,
            engine=engine,
            mode=mode,
            provider=provider,
            model=model,
            started_at=started.isoformat(),
        )
        self._started = started
        self.persist()

    @property
    def output_dir(self) -> Path:
        return self.run.output_dir

    def add_repo(
        self,
        *,
        repo_id: str,
        repo_name: str,
        repo_url: str,
        started_at: str,
        ended_at: str,
        duration_seconds: float,
        status: str,
        passed: bool,
        report_markdown: str,
        findings: list[dict],
        evidence_refs: list[dict],
        agent_states: list[dict],
        quality_metrics: dict | None = None,
        usage: dict | None = None,
    ) -> EvaluationRepoRecord:
        repo_dir = self.output_dir / "repos" / safe_repo_segment(repo_id)
        repo_dir.mkdir(parents=True, exist_ok=True)
        bounded_report = report_markdown[:REPORT_MARKDOWN_MAX_CHARS]
        report_path: str | None = None
        if report_markdown:
            report_file = repo_dir / "report.md"
            report_file.write_text(report_markdown, encoding="utf-8")
            report_path = str(report_file.relative_to(self.output_dir))

        record = EvaluationRepoRecord(
            repo_id=repo_id,
            repo_name=repo_name,
            repo_url=repo_url,
            engine=self.run.engine,
            mode=self.run.mode,
            provider=self.run.provider,
            model=self.run.model,
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=round(duration_seconds, 6),
            status=status,
            passed=passed,
            quality_checks={
                "pipeline": passed,
                "report_quality": bool(quality_metrics and quality_metrics.get("passed")),
            },
            quality_score=quality_metrics.get("aggregate_score") if quality_metrics else None,
            quality_metrics=quality_metrics,
            failed_checks=list(quality_metrics.get("failed_checks") or []) if quality_metrics else [],
            usage=usage,
            report_path=report_path,
            report_markdown=bounded_report,
            findings_count=len(findings),
            evidence_count=len(evidence_refs),
            agent_state_summary=_summarize_agent_states(agent_states),
        )
        self.run.repos.append(record)
        self.persist()
        return record

    def finalize(self, now: datetime | None = None) -> None:
        ended = now or datetime.now(UTC)
        self.run.ended_at = ended.isoformat()
        self.run.duration_seconds = round((ended - self._started).total_seconds(), 6)
        self.persist()

    def persist(self) -> Path:
        path = self.output_dir / "run.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(self.run.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
        return path


def safe_repo_segment(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return safe[:80] or "repo"


def _summarize_agent_states(agent_states: list[dict]) -> list[dict]:
    summary: list[dict] = []
    for state in agent_states:
        findings = state.get("findings") or []
        severities: dict[str, int] = {}
        confidences: list[float] = []
        for finding in findings:
            severity = str(finding.get("severity") or "unknown")
            severities[severity] = severities.get(severity, 0) + 1
            confidence = finding.get("confidence")
            if confidence is not None:
                confidences.append(float(confidence))
        summary.append(
            {
                "agent_id": state.get("agent_id"),
                "status": state.get("status"),
                "finding_count": len(findings),
                "severity_distribution": severities,
                "average_confidence": (
                    round(sum(confidences) / len(confidences), 4)
                    if confidences
                    else None
                ),
                "evidence_count": len(state.get("evidence_ids") or []),
                "prompt_tokens": state.get("prompt_tokens"),
                "completion_tokens": state.get("completion_tokens"),
                "llm_calls": state.get("llm_calls"),
                "duration_seconds": (state.get("metadata") or {}).get("duration_seconds"),
            }
        )
    return summary
