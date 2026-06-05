from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from dataclasses import dataclass
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


def load_repos(path: Path) -> list[str]:
    repos: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            repos.append(stripped)
    return repos


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CodePilot repository review evaluations.")
    parser.add_argument(
        "--repos",
        type=Path,
        default=ROOT_DIR / "evaluation" / "repos.txt",
        help="Path to a newline-delimited repo URL list.",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Optional directory for eval databases, clone workspaces, and reports.",
    )
    parser.add_argument(
        "--keep-work-dir",
        action="store_true",
        help="Keep the temporary work directory after evaluation.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repos = load_repos(args.repos)
    if not repos:
        print(f"No repositories found in {args.repos}")
        return 1

    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    if args.work_dir:
        base_dir = args.work_dir
        base_dir.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir = tempfile.TemporaryDirectory(prefix="codepilot-eval-", ignore_cleanup_errors=True)
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
