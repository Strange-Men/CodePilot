#!/usr/bin/env python3
"""Benchmark script for measuring real LLM review performance.

Usage:
    python scripts/benchmark_real_review.py --repo-url https://github.com/owner/repo

Environment variables:
    USE_MOCK_LLM=false
    REVIEW_ENGINE=v3_multi_agent
    REVIEW_AGENT_CONCURRENCY=4
    REVIEW_SPEED_MODE=balanced
    OPENAI_API_KEY or MIMO_API_KEY (depending on provider)

This script runs a real review and prints a timing summary.
No secrets are logged or printed.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

# Load .env into os.environ so preflight check can read MIMO_API_KEY
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass  # python-dotenv not installed; rely on shell env


def _preflight_auth_check() -> str | None:
    """Validate that a real API key is available before running.

    Returns an error message string if validation fails, or None if OK.
    Never prints the key value, prefix, suffix, or length.
    """
    # Known placeholder patterns from .env.example and common templates
    _placeholder_patterns = {
        "",
        "your-key",
        "your_api_key",
        "your_mimo_api_key",
        "your_openai_api_key",
        "placeholder",
        "changeme",
        "replace_me",
        "xxx",
    }

    mimo_key = os.environ.get("MIMO_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()

    # Check if at least one key is configured
    if not mimo_key and not openai_key:
        return "No API key found. Set MIMO_API_KEY or OPENAI_API_KEY in local .env."

    # Check MiMo key if present
    if mimo_key:
        key_lower = mimo_key.lower()
        if key_lower in _placeholder_patterns:
            return "MIMO_API_KEY appears to be a placeholder. Set a valid key in local .env."
        if mimo_key.startswith("<") and mimo_key.endswith(">"):
            return "MIMO_API_KEY appears to be a placeholder template. Set a valid key in local .env."

    # Check OpenAI key if present
    if openai_key:
        key_lower = openai_key.lower()
        if key_lower in _placeholder_patterns:
            return "OPENAI_API_KEY appears to be a placeholder. Set a valid key in local .env."
        if openai_key.startswith("<") and openai_key.endswith(">"):
            return "OPENAI_API_KEY appears to be a placeholder template. Set a valid key in local .env."

    return None


def extract_performance_events(log_output: str) -> list[dict]:
    """Extract performance_event lines from log output."""
    events = []
    pattern = re.compile(
        r"performance_event\s+"
        r"(?:task_id=(\S+)\s+)?"
        r"stage=(\S+)\s+"
        r"(?:duration_ms=(\S+)\s+)?"
        r"success=(\S+)"
        r"(?:\s+retries=(\S+))?"
        r"(?:\s+provider=(\S+))?"
        r"(?:\s+model=(\S+))?"
        r"(?:\s+concurrency=(\S+))?"
        r"(?:\s+language=(\S+))?"
        r"(?:\s+total_source_files=(\S+))?"
        r"(?:\s+analyzed_files=(\S+))?"
        r"(?:\s+report_chars=(\S+))?"
        r"(?:\s+findings=(\S+))?"
        r"(?:\s+agents=(\S+))?"
        r"(?:\s+engine=(\S+))?"
    )
    for line in log_output.splitlines():
        if "performance_event" not in line:
            continue
        match = pattern.search(line)
        if match:
            groups = match.groups()
            event = {
                "task_id": groups[0],
                "stage": groups[1],
                "duration_ms": groups[2],
                "success": groups[3],
                "retries": groups[4],
                "provider": groups[5],
                "model": groups[6],
                "concurrency": groups[7],
                "language": groups[8],
                "total_source_files": groups[9],
                "analyzed_files": groups[10],
                "report_chars": groups[11],
                "findings": groups[12],
                "agents": groups[13],
                "engine": groups[14],
            }
            events.append(event)
    return events


def print_timing_summary(events: list[dict]) -> None:
    """Print a formatted timing summary."""
    print("\n" + "=" * 60)
    print("BENCHMARK TIMING SUMMARY")
    print("=" * 60)

    # Group by stage
    stage_events: dict[str, list[dict]] = {}
    for event in events:
        stage = event["stage"]
        if stage not in stage_events:
            stage_events[stage] = []
        stage_events[stage].append(event)

    # Print pipeline stages
    pipeline_stages = [
        "total_pipeline",
        "clone",
        "parse",
        "context_build",
        "report_render",
        "report_compose",
        "persistence",
        "persist_findings",
        "persist_agent_states",
        "persist_review_state",
    ]

    print("\n--- Pipeline Stages ---")
    for stage in pipeline_stages:
        if stage in stage_events:
            for event in stage_events[stage]:
                duration = event.get("duration_ms") or "N/A"
                success = event.get("success") or "N/A"
                extra = ""
                if event.get("concurrency"):
                    extra += f" concurrency={event['concurrency']}"
                if event.get("engine"):
                    extra += f" engine={event['engine']}"
                if event.get("report_chars"):
                    extra += f" report_chars={event['report_chars']}"
                if event.get("findings"):
                    extra += f" findings={event['findings']}"
                if event.get("agents"):
                    extra += f" agents={event['agents']}"
                print(f"  {stage:25s} {duration:>8s} ms  success={success}{extra}")

    # Print agent stages
    agent_stages = [s for s in stage_events if s.startswith("agent_")]
    if agent_stages:
        print("\n--- Agent Stages ---")
        for stage in sorted(agent_stages):
            for event in stage_events[stage]:
                duration = event.get("duration_ms") or "N/A"
                success = event.get("success") or "N/A"
                retries = event.get("retries") or "0"
                provider = event.get("provider") or ""
                model = event.get("model") or ""
                concurrency = event.get("concurrency") or ""
                print(
                    f"  {stage:25s} {duration:>8s} ms  success={success} "
                    f"retries={retries} provider={provider} model={model} "
                    f"concurrency={concurrency}"
                )

    # Print LLM stages
    llm_stages = [s for s in stage_events if s == "llm_request"]
    if llm_stages:
        print("\n--- LLM Requests ---")
        for stage in llm_stages:
            for event in stage_events[stage]:
                duration = event.get("duration_ms") or "N/A"
                success = event.get("success") or "N/A"
                retries = event.get("retries") or "0"
                provider = event.get("provider") or ""
                model = event.get("model") or ""
                print(
                    f"  {stage:25s} {duration:>8s} ms  success={success} "
                    f"retries={retries} provider={provider} model={model}"
                )

    # Calculate totals
    total_events = stage_events.get("total_pipeline", [])
    if total_events:
        total_ms = float(total_events[0].get("duration_ms", 0))
        print(f"\n--- Total Wall-Clock: {total_ms:.1f} ms ({total_ms / 1000:.1f} s) ---")

    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark CodePilot real review performance.")
    parser.add_argument(
        "--repo-url",
        required=True,
        help="GitHub repository URL to review.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=None,
        help="Override REVIEW_AGENT_CONCURRENCY (default: from env or 2).",
    )
    parser.add_argument(
        "--speed-mode",
        choices=["balanced", "fast"],
        default=None,
        help="Override REVIEW_SPEED_MODE.",
    )
    parser.add_argument(
        "--engine",
        default=None,
        help="Override REVIEW_ENGINE.",
    )
    args = parser.parse_args()

    # Apply overrides
    if args.concurrency is not None:
        os.environ["REVIEW_AGENT_CONCURRENCY"] = str(args.concurrency)
    if args.speed_mode is not None:
        os.environ["REVIEW_SPEED_MODE"] = args.speed_mode
    if args.engine is not None:
        os.environ["REVIEW_ENGINE"] = args.engine

    # Ensure mock is off
    os.environ["USE_MOCK_LLM"] = "false"

    # Preflight: validate API key before running
    auth_error = _preflight_auth_check()
    if auth_error:
        print(f"ERROR: {auth_error}")
        print("Set a valid key in local .env, then rerun this script.")
        return 1

    print(f"Benchmarking repo: {args.repo_url}")
    print(f"Concurrency: {os.environ.get('REVIEW_AGENT_CONCURRENCY', '2')}")
    print(f"Speed mode: {os.environ.get('REVIEW_SPEED_MODE', 'balanced')}")
    print(f"Engine: {os.environ.get('REVIEW_ENGINE', 'v3_multi_agent')}")
    print()

    # Import after env setup
    import io
    import logging

    # Capture log output
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
    handler.setFormatter(formatter)

    # Add handler to backend loggers
    for logger_name in [
        "backend.tasks.pipeline",
        "backend.agents.orchestrator",
        "backend.llm.client",
        "backend.storage.sqlite",
        "backend.reviewers.report_generator",
    ]:
        log = logging.getLogger(logger_name)
        log.addHandler(handler)
        log.setLevel(logging.INFO)

    try:
        from backend.core.config import get_settings
        from backend.llm.client import build_llm_client_for_mode
        from backend.storage.sqlite import ReviewStore
        from backend.tasks.pipeline import ReviewPipeline

        settings = get_settings()
        store = ReviewStore(settings.database_path)

        # Determine LLM mode
        llm_mode = "mimo" if settings.mimo_api_key else "openai"
        llm_client = build_llm_client_for_mode(settings, llm_mode)

        task_id = f"benchmark-{int(time.time())}"
        store.create_review(task_id, args.repo_url)

        pipeline = ReviewPipeline(
            settings=settings,
            store=store,
            llm_client=llm_client,
        )

        print("Starting review...")
        pipeline_start = time.perf_counter()
        result = pipeline.run(task_id, args.repo_url)
        pipeline_duration = time.perf_counter() - pipeline_start

        print(f"\nReview completed in {pipeline_duration:.1f}s")
        print(f"Files analyzed: {result.analyzed_files}")
        print(f"Files skipped: {result.skipped_files}")

        # Parse and display timing
        log_output = log_capture.getvalue()
        events = extract_performance_events(log_output)
        if events:
            print_timing_summary(events)
        else:
            print("\nNo performance events captured. Check log output:")
            # Print last 50 lines of log
            lines = log_output.strip().splitlines()
            for line in lines[-50:]:
                print(f"  {line}")

        return 0

    except Exception as e:
        print(f"\nBenchmark failed: {e}")
        log_output = log_capture.getvalue()
        if log_output:
            print("\nLog output:")
            lines = log_output.strip().splitlines()
            for line in lines[-30:]:
                print(f"  {line}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
