from __future__ import annotations

import argparse
import json
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


# ---------------------------------------------------------------------------
# Dataset and config loading
# ---------------------------------------------------------------------------


def load_dataset(path: Path) -> list[dict]:
    """Load structured repo dataset from JSON."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["repos"]


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


def run_repo_eval(repo_url: str, base_dir: Path) -> EvalResult:
    from backend.core.config import Settings
    from backend.models.review import ReviewStatus
    from backend.storage.sqlite import ReviewStore
    from backend.tasks.runner import ReviewTaskRunner

    safe_name = "".join(char if char.isalnum() else "-" for char in repo_url).strip("-")[:80]
    run_dir = base_dir / safe_name
    run_dir.mkdir(parents=True, exist_ok=True)

    settings = Settings(
        database_path=run_dir / "reviews.db",
        workspace_path=run_dir / "workspace",
        reports_path=run_dir / "reports",
        use_mock_llm=True,
    )
    settings.workspace_path.mkdir(parents=True, exist_ok=True)
    settings.reports_path.mkdir(parents=True, exist_ok=True)

    store = ReviewStore(settings.database_path)
    runner = ReviewTaskRunner(settings, store)
    task_id = "eval"
    store.create_review(task_id, repo_url)
    runner._run(task_id, repo_url)
    runner.executor.shutdown(wait=False, cancel_futures=True)

    row = store.get_review(task_id)
    if not row:
        return EvalResult(repo_url, "missing", False, "review row was not persisted")

    status = row["status"]
    if status == ReviewStatus.completed.value:
        if has_required_sections(row["report_markdown"]):
            return EvalResult(repo_url, status, True, "completed with all required report sections")
        return EvalResult(repo_url, status, False, "completed report is missing one or more required sections")

    if status == ReviewStatus.failed.value:
        if is_user_friendly_error(row["error"]):
            return EvalResult(repo_url, status, True, f"controlled failure: {row['error']}")
        return EvalResult(repo_url, status, False, f"unfriendly failure: {row['error']!r}")

    return EvalResult(repo_url, status, False, "review did not reach completed or failed state")


# ---------------------------------------------------------------------------
# Dataset evaluation with metrics
# ---------------------------------------------------------------------------


def run_dataset_eval(
    dataset: list[dict],
    base_dir: Path,
    config: dict,
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

        start = time.perf_counter()
        eval_result = run_repo_eval(repo_url, base_dir)
        elapsed = time.perf_counter() - start

        # Read back the review row to extract parser stats
        safe_name = "".join(
            char if char.isalnum() else "-" for char in repo_url
        ).strip("-")[:80]
        run_dir = base_dir / safe_name
        total_py = 0
        analyzed = 0
        skipped = 0
        has_report = False
        has_all_sections = False

        db_path = run_dir / "reviews.db"
        if db_path.exists():
            from backend.storage.sqlite import ReviewStore

            store = ReviewStore(db_path)
            row = store.get_review("eval")
            if row:
                report_md = row.get("report_markdown") or ""
                has_report = bool(report_md.strip())
                has_all_sections = all(
                    f"# {s}" in report_md for s in REPORT_SECTIONS
                )

        repo_result = RepoResult(
            repo_id=repo_id,
            repo_url=repo_url,
            repo_name=repo_name,
            categories=categories,
            tags=entry.get("tags", []),
            status=eval_result.status,
            passed=eval_result.passed,
            details=eval_result.details,
            runtime_seconds=elapsed,
            total_python_files=total_py,
            analyzed_files=analyzed,
            skipped_files=skipped,
            has_report=has_report,
            has_all_sections=has_all_sections,
        )
        results.append(repo_result)

        marker = "PASS" if eval_result.passed else "FAIL"
        print(f"  {marker} [{eval_result.status}] {elapsed:.1f}s - {eval_result.details}")

    return results


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
    print("CodePilot V1.2 Evaluation Report")
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
            f"{r.runtime_seconds:6.1f}s  py={r.total_python_files:5d}  "
            f"{r.details}"
        )
    print("=" * 70)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
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
        "--reports-dir",
        type=Path,
        default=ROOT_DIR / "evaluation" / "reports",
        help="Directory for generated reports.",
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
        "--no-report",
        action="store_true",
        help="Skip writing report files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # --- Legacy mode ---
    if args.repos:
        return _run_legacy(args)

    # --- Dataset mode ---
    dataset = load_dataset(args.dataset)
    config = load_config(args.config)

    dataset = apply_filters(
        dataset,
        args.filter_size,
        args.filter_language,
        args.filter_health,
        args.filter_id,
    )
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

    results = run_dataset_eval(dataset, base_dir, config)

    from evaluation.metrics import compute_eval_report

    timestamp = datetime.now(UTC).isoformat()
    config_version = config.get("version", "1.0")
    report_obj = compute_eval_report(results, config_version, timestamp)

    print_summary_table(report_obj)

    if not args.no_report:
        json_path, md_path = generate_reports(report_obj, args.reports_dir)
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


def _run_legacy(args: argparse.Namespace) -> int:
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
    results = [run_repo_eval(repo_url, base_dir) for repo_url in repos]

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
