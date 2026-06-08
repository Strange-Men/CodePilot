from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.models.review_scope import ReviewScope
from backend.workflows import CIExitPolicy, ReviewWorkflow, parse_changed_files, parse_unified_diff_paths

ENGINE_CHOICES = ("v2", "v3_single_agent", "v3_multi_agent")
SEVERITY_CHOICES = ("none", "low", "medium", "high", "critical")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    workflow = ReviewWorkflow()

    if args.command == "review":
        result = workflow.run_review(
            args.repo_url,
            engine_mode=args.engine,
            use_mock_llm=_mock_flag(args),
            output_path=args.output,
            json_output_path=args.json_output,
        )
        _print_summary(result.summary)
        return 0 if result.status != "failed" else 1

    if args.command == "ci":
        result = workflow.run_review(
            args.repo_url,
            engine_mode=args.engine,
            use_mock_llm=_mock_flag(args),
            output_path=args.output,
            json_output_path=args.json_output,
        )
        _print_summary(result.summary)
        return CIExitPolicy(args.fail_on).exit_code(result.summary)

    if args.command == "diff":
        changed_paths = _diff_paths_from_args(args)
        scope = ReviewScope.for_changed_paths(
            changed_paths,
            source="diff",
            include_dependency_neighbors=not args.no_dependency_neighbors,
        )
        result = workflow.run_review(
            args.repo_url,
            engine_mode=args.engine,
            use_mock_llm=_mock_flag(args),
            output_path=args.output,
            json_output_path=args.json_output,
            review_scope=scope,
        )
        _print_summary(result.summary)
        return 0 if result.status != "failed" else 1

    parser.error(f"Unsupported command: {args.command}")
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codepilot", description="CodePilot developer workflow tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_review_command(subparsers)
    _add_ci_command(subparsers)
    _add_diff_command(subparsers)
    return parser


def _add_common_review_args(command: argparse.ArgumentParser) -> None:
    command.add_argument("repo_url", help="Public GitHub repository URL to review.")
    command.add_argument("--engine", choices=ENGINE_CHOICES, default=None, help="Review engine mode.")
    command.add_argument("--output", type=Path, default=None, help="Markdown report output path.")
    command.add_argument("--json-output", type=Path, default=None, help="Optional JSON summary output path.")
    llm_group = command.add_mutually_exclusive_group()
    llm_group.add_argument("--mock-llm", action="store_true", help="Force mock LLM mode.")
    llm_group.add_argument("--real-llm", action="store_true", help="Use configured real LLM mode.")


def _add_review_command(subparsers: argparse._SubParsersAction) -> None:
    command = subparsers.add_parser("review", help="Run a local repository review.")
    _add_common_review_args(command)


def _add_ci_command(subparsers: argparse._SubParsersAction) -> None:
    command = subparsers.add_parser("ci", help="Run CI-friendly report mode.")
    _add_common_review_args(command)
    command.add_argument(
        "--fail-on",
        choices=SEVERITY_CHOICES,
        default="none",
        help="Return exit code 1 when a finding meets this severity. Default is non-blocking.",
    )


def _add_diff_command(subparsers: argparse._SubParsersAction) -> None:
    command = subparsers.add_parser("diff", help="Run diff-aware review mode.")
    _add_common_review_args(command)
    command.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="Changed file path. Repeat for multiple files.",
    )
    command.add_argument("--diff-file", type=Path, default=None, help="Unified diff file to parse.")
    command.add_argument(
        "--no-dependency-neighbors",
        action="store_true",
        help="Only review changed files, without dependency-neighbor context.",
    )


def _mock_flag(args: argparse.Namespace) -> bool | None:
    if args.mock_llm:
        return True
    if args.real_llm:
        return False
    return None


def _diff_paths_from_args(args: argparse.Namespace) -> set[str]:
    paths = parse_changed_files(args.changed_file)
    if args.diff_file is not None:
        paths.update(parse_unified_diff_paths(args.diff_file.read_text(encoding="utf-8")))
    if not paths:
        raise SystemExit("diff mode requires --changed-file or --diff-file.")
    return paths


def _print_summary(summary: dict) -> None:
    review = summary.get("review") or {}
    output = {
        "task_id": summary.get("task_id"),
        "status": review.get("status"),
        "report_path": review.get("export_path"),
        "findings": len(summary.get("structured_findings", [])),
    }
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    sys.exit(main())
