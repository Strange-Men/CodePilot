from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluation.registry import EvaluationRunRegistry, load_dataset_definition  # noqa: E402

INTERNAL_ERROR_MARKERS = [
    "Traceback",
    'File "',
    "IndexError",
    "KeyError",
    "AttributeError",
    "list index out of range",
    "NoneType",
]


@dataclass(frozen=True)
class EvalResult:
    repo_url: str
    status: str
    passed: bool
    details: str
    total_python_files: int = 0
    analyzed_files: int = 0
    skipped_files: int = 0


# ---------------------------------------------------------------------------
# Dataset and config loading
# ---------------------------------------------------------------------------


def load_dataset(path: Path) -> list[dict]:
    """Load structured repo dataset from JSON."""
    return load_dataset_definition(path).repos


def load_config(path: Path) -> dict:
    """Load evaluation configuration from JSON."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_repos(path: Path) -> list[str]:
    """Load flat repo URL list (legacy mode)."""
    repos: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            repos.append(stripped)
    return repos


# ---------------------------------------------------------------------------
# Result checking helpers
# ---------------------------------------------------------------------------


def is_user_friendly_error(error: str | None) -> bool:
    if not error or not error.strip():
        return False
    if len(error) > 2000:
        return False
    return not any(marker in error for marker in INTERNAL_ERROR_MARKERS)


def has_required_sections(report: str | None) -> bool:
    from backend.llm.client import REPORT_SECTIONS

    if not report:
        return False
    return all(f"# {section}" in report for section in REPORT_SECTIONS)


def classify_failure_stage(row: dict | None) -> str:
    """Return 'clone', 'parse', 'review', or 'unknown'."""
    if not row:
        return "unknown"
    error = (row.get("error") or "").lower()
    if "clone" in error or "git" in error:
        return "clone"
    if row.get("status") == "failed":
        return "review"
    return "unknown"


# ---------------------------------------------------------------------------
# Single-repo evaluation (core logic, preserved from V1.1)
# ---------------------------------------------------------------------------


class EvaluationFixtureCloneService:
    def __init__(self, workspace_path: Path, fixture_path: Path) -> None:
        self.workspace_path = workspace_path
        self.fixture_path = fixture_path

    def clone(self, repo_url: str, task_id: str) -> Path:
        if not self.fixture_path.is_dir():
            raise RuntimeError(f"Evaluation fixture directory does not exist: {self.fixture_path}")
        destination = self.workspace_path / task_id / "repo"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.fixture_path, destination)
        return destination

    def cleanup(self, task_id: str) -> None:
        shutil.rmtree(self.workspace_path / task_id, ignore_errors=True)


def run_repo_eval(
    repo_url: str,
    base_dir: Path,
    review_engine: str = "v3_multi_agent",
    fixture_path: Path | None = None,
    real_llm: bool = False,
    model: str | None = None,
) -> EvalResult:
    from backend.core.config import Settings
    from backend.models.review import ReviewStatus
    from backend.storage.sqlite import ReviewStore
    from backend.tasks.runner import ReviewTaskRunner

    safe_name = "".join(char if char.isalnum() else "-" for char in repo_url).strip("-")[:80]
    run_dir = base_dir / safe_name
    run_dir.mkdir(parents=True, exist_ok=True)

    settings_values = {
        "database_path": run_dir / "reviews.db",
        "workspace_path": run_dir / "workspace",
        "reports_path": run_dir / "reports",
        "USE_MOCK_LLM": not real_llm,
        "ENABLE_REAL_LLM": real_llm,
        "REVIEW_ENGINE": review_engine,
    }
    if model:
        settings_values["OPENAI_MODEL"] = model
    settings = Settings(
        **settings_values,
    )
    settings.workspace_path.mkdir(parents=True, exist_ok=True)
    settings.reports_path.mkdir(parents=True, exist_ok=True)

    store = ReviewStore(settings.database_path)
    runner = ReviewTaskRunner(settings, store)
    if fixture_path is not None:
        runner.pipeline.clone_service_factory = lambda workspace_path: EvaluationFixtureCloneService(
            workspace_path,
            fixture_path,
        )
    task_id = "eval"
    store.create_review(task_id, repo_url)
    pipeline_result = runner._run(task_id, repo_url)
    runner.executor.shutdown(wait=False, cancel_futures=True)

    row = store.get_review(task_id)
    if not row:
        return EvalResult(repo_url, "missing", False, "review row was not persisted")

    status = row["status"]
    if status == ReviewStatus.completed.value:
        if has_required_sections(row["report_markdown"]):
            return EvalResult(
                repo_url,
                status,
                True,
                "completed with all required report sections",
                pipeline_result.total_python_files,
                pipeline_result.analyzed_files,
                pipeline_result.skipped_files,
            )
        return EvalResult(
            repo_url,
            status,
            False,
            "completed report is missing one or more required sections",
            pipeline_result.total_python_files,
            pipeline_result.analyzed_files,
            pipeline_result.skipped_files,
        )

    if status == ReviewStatus.failed.value:
        if is_user_friendly_error(row["error"]):
            return EvalResult(
                repo_url,
                status,
                True,
                f"controlled failure: {row['error']}",
                pipeline_result.total_python_files,
                pipeline_result.analyzed_files,
                pipeline_result.skipped_files,
            )
        return EvalResult(
            repo_url,
            status,
            False,
            f"unfriendly failure: {row['error']!r}",
            pipeline_result.total_python_files,
            pipeline_result.analyzed_files,
            pipeline_result.skipped_files,
        )

    return EvalResult(repo_url, status, False, "review did not reach completed or failed state")


# ---------------------------------------------------------------------------
# Dataset evaluation with metrics
# ---------------------------------------------------------------------------


def run_dataset_eval(
    dataset: list[dict],
    base_dir: Path,
    config: dict,
    registry: EvaluationRunRegistry | None = None,
    real_llm: bool = False,
    model: str | None = None,
) -> list:
    """Run evaluation for each repo in the dataset, returning RepoResults."""
    from backend.llm.client import REPORT_SECTIONS
    from evaluation.metrics import RepoResult

    results: list[RepoResult] = []
    total = len(dataset)

    for idx, entry in enumerate(dataset, 1):
        repo_id = entry["id"]
        repo_url = entry["url"]
        repo_name = entry["name"]
        categories = entry["categories"]

        print(f"\n[{idx}/{total}] Evaluating {repo_name} ({repo_id})...")

        started_at = datetime.now(UTC)
        start = time.perf_counter()
        review_engine = config.get("runner", {}).get("review_engine", "v3_multi_agent")
        fixture_path = Path(entry["fixture_path"]) if entry.get("fixture_path") else None
        if fixture_path is None and not real_llm and model is None:
            eval_result = run_repo_eval(repo_url, base_dir, review_engine=review_engine)
        else:
            eval_result = run_repo_eval(
                repo_url,
                base_dir,
                review_engine=review_engine,
                fixture_path=fixture_path,
                real_llm=real_llm,
                model=model,
            )
        elapsed = time.perf_counter() - start
        ended_at = datetime.now(UTC)

        # Read back persisted report state; parser stats are returned from the in-memory pipeline result.
        safe_name = "".join(
            char if char.isalnum() else "-" for char in repo_url
        ).strip("-")[:80]
        run_dir = base_dir / safe_name
        total_py = eval_result.total_python_files
        analyzed = eval_result.analyzed_files
        skipped = eval_result.skipped_files
        has_report = False
        has_all_sections = False
        report_markdown = ""
        full_report_markdown = ""
        findings: list[dict] = []
        evidence_refs: list[dict] = []
        agent_states: list[dict] = []

        db_path = run_dir / "reviews.db"
        if db_path.exists():
            from backend.storage.sqlite import ReviewStore
            from evaluation.registry import REPORT_MARKDOWN_MAX_CHARS

            store = ReviewStore(db_path)
            row = store.get_review("eval")
            if row:
                report_md = row.get("report_markdown") or ""
                full_report_markdown = report_md
                has_report = bool(report_md.strip())
                has_all_sections = all(
                    f"# {s}" in report_md for s in REPORT_SECTIONS
                )
                if report_md:
                    report_markdown = report_md[:REPORT_MARKDOWN_MAX_CHARS]
                findings = store.get_structured_findings("eval")
                evidence_refs = store.get_evidence_refs("eval")
                agent_states = store.get_agent_states("eval")

        passed, details = apply_expectations(
            entry,
            config,
            eval_result.passed,
            eval_result.details,
            eval_result.status,
            total_py,
        )
        quality_metrics = None
        quality_scores = None
        failed_checks: list[str] = []
        if full_report_markdown:
            from evaluation.quality_metrics import evaluate_report_quality

            quality = evaluate_report_quality(
                full_report_markdown,
                findings,
                evidence_refs,
                agent_states,
                tags=entry.get("tags", []),
            )
            quality_metrics = quality.to_dict()
            quality_scores = {
                dimension.name: dimension.score for dimension in quality.dimensions
            }
            failed_checks = quality.failed_checks
            if not quality.passed:
                passed = False
                details = f"{details}; quality checks failed: {', '.join(failed_checks)}"
        repo_result = RepoResult(
            repo_id=repo_id,
            repo_url=repo_url,
            repo_name=repo_name,
            categories=categories,
            tags=entry.get("tags", []),
            status=eval_result.status,
            passed=passed,
            details=details,
            runtime_seconds=elapsed,
            total_python_files=total_py,
            analyzed_files=analyzed,
            skipped_files=skipped,
            has_report=has_report,
            has_all_sections=has_all_sections,
            report_markdown=report_markdown,
            quality_score=quality_metrics["aggregate_score"] if quality_metrics else None,
            quality_scores=quality_scores,
            failed_checks=failed_checks,
        )
        results.append(repo_result)
        if registry is not None:
            registry.add_repo(
                repo_id=repo_id,
                repo_name=repo_name,
                repo_url=repo_url,
                started_at=started_at.isoformat(),
                ended_at=ended_at.isoformat(),
                duration_seconds=elapsed,
                status=eval_result.status,
                passed=passed,
                report_markdown=full_report_markdown,
                findings=findings,
                evidence_refs=evidence_refs,
                agent_states=agent_states,
                quality_metrics=quality_metrics,
            )

        marker = "PASS" if passed else "FAIL"
        print(f"  {marker} [{eval_result.status}] {elapsed:.1f}s - {details}")

    return results


def apply_expectations(
    entry: dict,
    config: dict,
    passed: bool,
    details: str,
    status: str,
    total_source_files: int,
) -> tuple[bool, str]:
    expected = entry.get("expected", {})
    categories = entry.get("categories", {})
    language = categories.get("language", "unknown")
    language_expectations = config.get("language_expectations", {}).get(language, {})
    min_source_files = expected.get("min_source_files", language_expectations.get("min_source_files"))
    max_source_files = expected.get("max_source_files", language_expectations.get("max_source_files"))

    if min_source_files is not None and status == "completed" and total_source_files < int(min_source_files):
        return (
            False,
            f"parsed source file count {total_source_files} is below required minimum {min_source_files}",
        )
    if max_source_files is not None and status == "completed" and total_source_files > int(max_source_files):
        return (
            False,
            f"parsed source file count {total_source_files} is above allowed maximum {max_source_files}",
        )
    return passed, details


def apply_filters(
    dataset: list[dict],
    filter_size: str | None,
    filter_language: str | None,
    filter_health: str | None,
    filter_id: str | None,
) -> list[dict]:
    """Filter dataset entries by category dimensions or id."""
    filtered = dataset
    if filter_size:
        filtered = [r for r in filtered if r["categories"]["size"] == filter_size]
    if filter_language:
        filtered = [
            r for r in filtered if r["categories"]["language"] == filter_language
        ]
    if filter_health:
        filtered = [
            r for r in filtered if r["categories"]["health"] == filter_health
        ]
    if filter_id:
        filtered = [r for r in filtered if r["id"] == filter_id]
    return filtered


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def generate_reports(
    report_obj,
    reports_dir: Path,
) -> tuple[Path, Path]:
    """Write JSON and Markdown reports. Returns (json_path, md_path)."""
    from evaluation.metrics import report_to_dict, report_to_markdown

    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")

    json_path = reports_dir / f"eval-{ts}.json"
    md_path = reports_dir / f"eval-{ts}.md"

    json_path.write_text(
        json.dumps(report_to_dict(report_obj), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md_path.write_text(report_to_markdown(report_obj), encoding="utf-8")

    return json_path, md_path


def print_summary_table(report_obj) -> None:
    """Print a formatted summary to stdout."""
    print("\n" + "=" * 70)
    print("CodePilot Evaluation Report")
    print("=" * 70)
    print(f"Timestamp: {report_obj.timestamp}")
    print(
        f"Total: {report_obj.total_repos} | "
        f"Passed: {report_obj.passed_repos} | "
        f"Failed: {report_obj.failed_repos} | "
        f"Success Rate: {report_obj.overall_success_rate * 100:.1f}%"
    )
    print(f"Average Runtime: {report_obj.overall_average_runtime_seconds:.1f}s")
    print("=" * 70)

    for cat_type, label in [
        ("size", "By Size"),
        ("language", "By Language"),
        ("health", "By Health"),
    ]:
        cat_metrics = [
            m
            for m in report_obj.category_metrics
            if m.category_type == cat_type
        ]
        if not cat_metrics:
            continue
        print(f"\n{label}:")
        for m in sorted(cat_metrics, key=lambda x: x.category_value):
            print(
                f"  {m.category_value:12s}: "
                f"{m.passed_repos}/{m.total_repos} passed "
                f"({m.review_success_rate * 100:5.1f}%)  "
                f"avg {m.average_runtime_seconds:.1f}s"
            )

    print("\n" + "-" * 70)
    print("Per-Repo Results:")
    print("-" * 70)
    for r in report_obj.repo_results:
        marker = "PASS" if r.passed else "FAIL"
        cat_str = (
            f"{r.categories.get('size', '?')}/"
            f"{r.categories.get('language', '?')}/"
            f"{r.categories.get('health', '?')}"
        )
        print(
            f"  {marker}  {r.repo_id:16s} ({cat_str:22s}) "
            f"{r.runtime_seconds:6.1f}s  files={r.total_python_files:5d}  "
            f"{r.details}"
        )
    print("=" * 70)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run CodePilot repository review evaluations."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT_DIR / "evaluation" / "datasets" / "repos.json",
        help="Path to the JSON dataset file.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT_DIR / "evaluation" / "configs" / "default.json",
        help="Path to the evaluation config file.",
    )
    parser.add_argument(
        "--output-dir",
        "--reports-dir",
        dest="output_dir",
        type=Path,
        default=ROOT_DIR / "evaluation" / "runs",
        help="Root directory for generated evaluation runs.",
    )
    parser.add_argument(
        "--repos",
        type=Path,
        default=None,
        help="Legacy flat repo URL list (bypasses dataset/metrics).",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Optional persistent work directory.",
    )
    parser.add_argument(
        "--keep-work-dir",
        action="store_true",
        help="Keep the temporary work directory after evaluation.",
    )
    parser.add_argument("--filter-size", choices=["small", "medium", "large"])
    parser.add_argument("--filter-language", choices=["python", "javascript", "mixed"])
    parser.add_argument("--filter-health", choices=["healthy", "problematic"])
    parser.add_argument("--filter-id", type=str, help="Run only a specific repo id.")
    parser.add_argument(
        "--real-llm",
        action="store_true",
        help="Explicitly opt in to real LLM evaluation. Mock mode is the default.",
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "openai-compatible"],
        default="openai",
        help="Provider metadata for real LLM runs.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name for real LLM runs. Defaults to OPENAI_MODEL or gpt-4o-mini.",
    )
    parser.add_argument(
        "--max-repos",
        type=positive_int,
        default=None,
        help="Limit the number of repositories after filters are applied.",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip writing report files.",
    )
    return parser.parse_args(argv)


def validate_real_llm_configuration(
    *,
    real_llm: bool,
    provider: str,
    model: str,
    environ: dict[str, str] | None = None,
) -> str | None:
    if not real_llm:
        return None
    environment = os.environ if environ is None else environ
    if provider not in {"openai", "openai-compatible"}:
        return f"Unsupported real LLM provider: {provider}"
    if not model.strip():
        return "Real LLM evaluation requires a non-empty --model value."
    if not environment.get("OPENAI_API_KEY", "").strip():
        return (
            "Real LLM evaluation requires OPENAI_API_KEY. "
            "Set the credential in the environment or omit --real-llm to use mock mode."
        )
    return None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    model = args.model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    configuration_error = validate_real_llm_configuration(
        real_llm=args.real_llm,
        provider=args.provider,
        model=model,
    )
    if configuration_error:
        print(f"Evaluation configuration error: {configuration_error}", file=sys.stderr)
        return 2

    # --- Legacy mode ---
    if args.repos:
        return _run_legacy(args, model=model)

    # --- Dataset mode ---
    dataset_definition = load_dataset_definition(args.dataset)
    dataset = dataset_definition.repos
    config = load_config(args.config)

    dataset = apply_filters(
        dataset,
        args.filter_size,
        args.filter_language,
        args.filter_health,
        args.filter_id,
    )
    if args.max_repos is not None:
        dataset = dataset[: args.max_repos]
    if not dataset:
        print("No repositories matched the given filters.")
        return 1

    print(f"Loaded {len(dataset)} repositories from {args.dataset}")

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if args.work_dir:
        base_dir = args.work_dir
        base_dir.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir = tempfile.TemporaryDirectory(
            prefix="codepilot-eval-", ignore_cleanup_errors=True
        )
        base_dir = Path(temp_dir.name)

    print(f"Work dir: {base_dir}")

    review_engine = config.get("runner", {}).get("review_engine", "v3_multi_agent")
    registry = EvaluationRunRegistry(
        args.output_dir,
        dataset_definition.metadata,
        engine=review_engine,
        mode="real" if args.real_llm else "mock",
        provider=args.provider if args.real_llm else None,
        model=model if args.real_llm else None,
    )
    print(f"Run ID: {registry.run.run_id}")
    print(f"Run dir: {registry.output_dir}")

    results = run_dataset_eval(
        dataset,
        base_dir,
        config,
        registry=registry,
        real_llm=args.real_llm,
        model=model if args.real_llm else None,
    )
    registry.finalize()

    from evaluation.metrics import compute_eval_report

    timestamp = datetime.now(UTC).isoformat()
    config_version = config.get("version", "1.0")
    report_obj = compute_eval_report(results, config_version, timestamp)
    _write_quality_summary(registry)

    print_summary_table(report_obj)

    if not args.no_report:
        json_path, md_path = generate_reports(report_obj, args.output_dir)
        print("\nReports written:")
        print(f"  JSON: {json_path}")
        print(f"  Markdown: {md_path}")

    # Preserve work dir on failure
    if temp_dir and (args.keep_work_dir or report_obj.failed_repos > 0):
        preserved = ROOT_DIR / ".eval-work"
        if preserved.exists():
            shutil.rmtree(preserved)
        shutil.copytree(base_dir, preserved)
        print(f"\nPreserved eval work dir: {preserved}")

    if temp_dir and not args.keep_work_dir:
        temp_dir.cleanup()

    return 0 if report_obj.failed_repos == 0 else 1


def _write_quality_summary(registry: EvaluationRunRegistry) -> None:
    scored = [repo for repo in registry.run.repos if repo.quality_score is not None]
    aggregate = (
        sum(float(repo.quality_score) for repo in scored) / len(scored)
        if scored
        else None
    )
    payload = {
        "schema_version": "3.5",
        "run_id": registry.run.run_id,
        "aggregate_score": round(aggregate, 2) if aggregate is not None else None,
        "repos": [
            {
                "repo_id": repo.repo_id,
                "repo_name": repo.repo_name,
                "aggregate_score": repo.quality_score,
                "dimensions": (repo.quality_metrics or {}).get("dimensions", []),
                "failed_checks": repo.failed_checks,
            }
            for repo in scored
        ],
    }
    (registry.output_dir / "quality-summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# CodePilot V3.5 Report Quality Summary",
        "",
        f"Run: `{registry.run.run_id}`",
        "",
        f"Aggregate quality score: **{aggregate:.2f}/100**" if aggregate is not None else "No reports were scored.",
        "",
        "| Repository | Score | Failed Checks |",
        "| --- | ---: | --- |",
    ]
    for repo in scored:
        failures = ", ".join(repo.failed_checks) or "None"
        lines.append(f"| {repo.repo_name} | {repo.quality_score:.2f} | {failures} |")
    (registry.output_dir / "quality-summary.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def _run_legacy(args: argparse.Namespace, *, model: str) -> int:
    """Legacy flat-file mode for backward compatibility."""
    repos = load_repos(args.repos)
    if not repos:
        print(f"No repositories found in {args.repos}")
        return 1

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if args.work_dir:
        base_dir = args.work_dir
        base_dir.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir = tempfile.TemporaryDirectory(
            prefix="codepilot-eval-", ignore_cleanup_errors=True
        )
        base_dir = Path(temp_dir.name)

    print(f"Evaluation work dir: {base_dir}")
    if args.max_repos is not None:
        repos = repos[: args.max_repos]
    results = [
        run_repo_eval(
            repo_url,
            base_dir,
            real_llm=args.real_llm,
            model=model if args.real_llm else None,
        )
        for repo_url in repos
    ]

    print("\nResults:")
    for result in results:
        marker = "PASS" if result.passed else "FAIL"
        print(f"- {marker} [{result.status}] {result.repo_url} - {result.details}")

    passed = all(result.passed for result in results)
    if temp_dir and (args.keep_work_dir or not passed):
        preserved = ROOT_DIR / ".eval-work"
        if preserved.exists():
            shutil.rmtree(preserved)
        shutil.copytree(base_dir, preserved)
        print(f"\nPreserved eval work dir: {preserved}")

    if temp_dir and not args.keep_work_dir:
        temp_dir.cleanup()

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
