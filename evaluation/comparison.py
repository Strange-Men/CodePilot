from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepoComparison:
    repo_id: str
    quality_score_delta: float | None
    failed_checks_added: list[str]
    failed_checks_resolved: list[str]
    estimated_cost_delta: float | None
    duration_seconds_delta: float | None


@dataclass(frozen=True)
class RunComparison:
    current_run_id: str
    previous_run_id: str
    repo_comparisons: list[RepoComparison]

    def to_dict(self) -> dict:
        quality_deltas = [
            comparison.quality_score_delta
            for comparison in self.repo_comparisons
            if comparison.quality_score_delta is not None
        ]
        cost_deltas = [
            comparison.estimated_cost_delta
            for comparison in self.repo_comparisons
            if comparison.estimated_cost_delta is not None
        ]
        latency_deltas = [
            comparison.duration_seconds_delta
            for comparison in self.repo_comparisons
            if comparison.duration_seconds_delta is not None
        ]
        return {
            "schema_version": "3.5",
            "current_run_id": self.current_run_id,
            "previous_run_id": self.previous_run_id,
            "aggregate": {
                "average_quality_score_delta": _average(quality_deltas),
                "estimated_cost_delta": round(sum(cost_deltas), 8) if cost_deltas else None,
                "duration_seconds_delta": round(sum(latency_deltas), 6) if latency_deltas else None,
            },
            "repos": [asdict(comparison) for comparison in self.repo_comparisons],
        }


def find_previous_comparable_run(output_root: Path, current_run_dir: Path) -> Path | None:
    current = _load_run(current_run_dir)
    candidates: list[tuple[str, str, Path]] = []
    for run_path in output_root.iterdir() if output_root.exists() else []:
        if not run_path.is_dir() or run_path.resolve() == current_run_dir.resolve():
            continue
        run_file = run_path / "run.json"
        if not run_file.exists():
            continue
        candidate = _load_run(run_path)
        if candidate.get("ended_at") is None or not _comparable(current, candidate):
            continue
        candidates.append((str(candidate["ended_at"]), str(candidate["run_id"]), run_path))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def compare_run_directories(current_run_dir: Path, previous_run_dir: Path) -> RunComparison:
    current = _load_run(current_run_dir)
    previous = _load_run(previous_run_dir)
    if not _comparable(current, previous):
        raise ValueError("Evaluation runs are not comparable.")
    current_repos = {repo["repo_id"]: repo for repo in current.get("repos", [])}
    previous_repos = {repo["repo_id"]: repo for repo in previous.get("repos", [])}
    comparisons: list[RepoComparison] = []
    for repo_id in sorted(current_repos.keys() & previous_repos.keys()):
        current_repo = current_repos[repo_id]
        previous_repo = previous_repos[repo_id]
        current_failed = set(current_repo.get("failed_checks") or [])
        previous_failed = set(previous_repo.get("failed_checks") or [])
        comparisons.append(
            RepoComparison(
                repo_id=repo_id,
                quality_score_delta=_delta(
                    current_repo.get("quality_score"),
                    previous_repo.get("quality_score"),
                    digits=2,
                ),
                failed_checks_added=sorted(current_failed - previous_failed),
                failed_checks_resolved=sorted(previous_failed - current_failed),
                estimated_cost_delta=_delta(
                    (current_repo.get("usage") or {}).get("estimated_cost"),
                    (previous_repo.get("usage") or {}).get("estimated_cost"),
                    digits=8,
                ),
                duration_seconds_delta=_delta(
                    (current_repo.get("usage") or {}).get("duration_seconds"),
                    (previous_repo.get("usage") or {}).get("duration_seconds"),
                    digits=6,
                ),
            )
        )
    return RunComparison(
        current_run_id=str(current["run_id"]),
        previous_run_id=str(previous["run_id"]),
        repo_comparisons=comparisons,
    )


def write_comparison_artifacts(comparison: RunComparison, output_dir: Path) -> tuple[Path, Path]:
    payload = comparison.to_dict()
    json_path = output_dir / "comparison.json"
    markdown_path = output_dir / "comparison.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# CodePilot V3.5 Regression Comparison",
        "",
        f"- Current run: `{comparison.current_run_id}`",
        f"- Previous run: `{comparison.previous_run_id}`",
        "",
        "| Repository | Quality Delta | New Failed Checks | Resolved Checks | Cost Delta | Runtime Delta |",
        "| --- | ---: | --- | --- | ---: | ---: |",
    ]
    for repo in comparison.repo_comparisons:
        lines.append(
            f"| {repo.repo_id} | {_format_delta(repo.quality_score_delta)} | "
            f"{', '.join(repo.failed_checks_added) or 'None'} | "
            f"{', '.join(repo.failed_checks_resolved) or 'None'} | "
            f"{_format_delta(repo.estimated_cost_delta)} | "
            f"{_format_delta(repo.duration_seconds_delta)} |"
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, markdown_path


def _load_run(run_dir: Path) -> dict:
    return json.loads((run_dir / "run.json").read_text(encoding="utf-8"))


def _comparable(left: dict, right: dict) -> bool:
    return (
        (left.get("dataset") or {}).get("sha256") == (right.get("dataset") or {}).get("sha256")
        and left.get("engine") == right.get("engine")
        and left.get("mode") == right.get("mode")
        and left.get("provider") == right.get("provider")
        and left.get("model") == right.get("model")
    )


def _delta(current: object, previous: object, *, digits: int) -> float | None:
    if current is None or previous is None:
        return None
    return round(float(current) - float(previous), digits)


def _average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _format_delta(value: float | None) -> str:
    return f"{value:+g}" if value is not None else "N/A"
