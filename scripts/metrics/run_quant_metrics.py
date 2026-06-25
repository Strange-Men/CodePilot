from __future__ import annotations

# ruff: noqa: E402, I001

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from stat import S_IWRITE
from typing import Any
from urllib.parse import urlparse

import httpx

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.core.config import Settings
from backend.core.report_contract import REPORT_SECTIONS
from backend.llm.client import MockLLMClient, resolve_llm_config
from backend.models.context import ReviewContext
from backend.models.report_result import ReportResult
from backend.parsers.composite import CompositeSourceParser
from backend.parsers.registry import default_parser_registry
from backend.prompts import PromptRenderer
from backend.reviewers.report_generator import ReportGenerator
from backend.services.clone_service import CloneService
from backend.services.indexer import RepositoryIndexer
from backend.services.sandbox import ALLOWED_SOURCE_EXTENSIONS, IGNORE_DIRS, SandboxFilter
from backend.services.token_counting import PromptTokenCounter, tiktoken

DEFAULT_OUTPUT = ROOT_DIR / "reports" / "quant_metrics_v3_7"
DEFAULT_BENCHMARK = ROOT_DIR / "evaluation" / "datasets" / "repos.json"
REPRO_BOTH_COMMAND = (
    "python scripts/metrics/run_quant_metrics.py --benchmark evaluation/datasets/repos.json "
    "--mode both --max-repos 3 --output reports/quant_metrics_v3_7"
)
REPRO_REAL_COMMAND = (
    "python scripts/metrics/run_quant_metrics.py --benchmark evaluation/datasets/repos.json "
    "--mode real --max-repos 1 --output reports/quant_metrics_v3_7"
)
REPRO_BASELINE_COMMAND = (
    "python scripts/metrics/run_quant_metrics.py --benchmark evaluation/datasets/repos.json "
    "--mode baseline --max-repos 1 --output reports/quant_metrics_v3_7"
)
RAW_EV_RE = re.compile(r"\bev_[0-9a-f]{20}\b")
PATH_RE = re.compile(r"`([^`]+\.(?:py|js|jsx|ts|tsx))`|([\w./\\-]+\.(?:py|js|jsx|ts|tsx))")
SYMBOL_RE = re.compile(
    r"\b(function|class|method|line|lines|import|dependency|complexity|fan[-_ ]?in|fan[-_ ]?out)\b", re.I
)
GENERIC_RE = re.compile(
    r"\b(optimi[sz]e|improve maintainability|reduce complexity|clean up|refactor this|best practices)\b",
    re.I,
)


@dataclass(frozen=True)
class RepoSpec:
    name: str
    url: str | None = None
    path: Path | None = None
    size: str = "custom"
    note: str = ""
    dataset_id: str | None = None


@dataclass(frozen=True)
class PreparedRepo:
    spec: RepoSpec
    path: Path
    source: str
    clone_duration_seconds: float | None = None


class TrackingRealLLMClient:
    """OpenAI-compatible client used only by the metrics runner.

    It mirrors CodePilot's real provider resolution and request shape, while recording
    usage and retry metadata for the quant report.
    """

    def __init__(self, settings: Settings, *, max_retries: int = 1) -> None:
        self.settings = settings
        self.resolved = resolve_llm_config(settings)
        self.max_retries = max(0, max_retries)
        self.calls = 0
        self.retry_count = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.errors: list[str] = []

    def generate_review(self, prompt: str) -> str:
        if not self.resolved.api_key:
            raise RuntimeError(f"{self.resolved.api_key_env_name} is missing; real LLM cannot run.")
        url = self.resolved.base_url.rstrip("/") + "/chat/completions"
        structured_output = "Return only JSON" in prompt
        system_content = (
            "You are CodePilot, an evidence-grounded code review agent. "
            "Return only valid JSON matching the schema in the user prompt."
            if structured_output
            else (
                "You are CodePilot, an AI code review agent. Return markdown with exactly these "
                f"top-level headings: {', '.join(REPORT_SECTIONS)}. Do not add extra sections."
            )
        )
        payload = {
            "model": self.resolved.model,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        timeout = httpx.Timeout(
            connect=self.settings.llm_connect_timeout,
            read=self.settings.llm_read_timeout,
            write=self.settings.llm_write_timeout,
            pool=self.settings.llm_pool_timeout,
        )
        with httpx.Client(timeout=timeout) as client:
            for attempt in range(self.max_retries + 1):
                self.calls += 1
                try:
                    response = client.post(
                        url, headers={"Authorization": f"Bearer {self.resolved.api_key}"}, json=payload
                    )
                    if response.status_code >= 500 or response.status_code in {408, 409, 429}:
                        if attempt < self.max_retries:
                            self.retry_count += 1
                            time.sleep(1.0 * (2**attempt))
                            continue
                    response.raise_for_status()
                    data = response.json()
                    usage = data.get("usage") or {}
                    self.prompt_tokens += int(usage.get("prompt_tokens") or 0)
                    self.completion_tokens += int(usage.get("completion_tokens") or 0)
                    self.total_tokens += int(usage.get("total_tokens") or 0)
                    return data["choices"][0]["message"]["content"]
                except Exception as exc:
                    self.errors.append(_short_error(exc))
                    if attempt >= self.max_retries:
                        raise
                    self.retry_count += 1
                    time.sleep(1.0 * (2**attempt))
        raise RuntimeError("Real LLM request failed without a response.")

    @property
    def usage(self) -> dict[str, Any]:
        if self.prompt_tokens == 0 and self.completion_tokens == 0 and self.total_tokens == 0:
            return {
                "real_llm_input_tokens": unsupported("provider response did not include token usage"),
                "real_llm_output_tokens": unsupported("provider response did not include token usage"),
                "real_llm_total_tokens": unsupported("provider response did not include token usage"),
            }
        return {
            "real_llm_input_tokens": self.prompt_tokens,
            "real_llm_output_tokens": self.completion_tokens,
            "real_llm_total_tokens": self.total_tokens or self.prompt_tokens + self.completion_tokens,
        }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = (ROOT_DIR / args.output).resolve() if not Path(args.output).is_absolute() else Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    ensure_output_dirs(output)

    started = time.perf_counter()
    metadata = build_metadata(args, output)
    print(f"[metrics] output={output}")
    print(f"[metrics] mode={args.mode} resumed={not args.rerun}")

    unsupported_items: list[dict[str, Any]] = []
    repo_specs = resolve_repo_specs(args)
    if args.benchmark and args.max_repos:
        repo_specs = candidate_specs_for_benchmark(repo_specs, args.max_repos)
    prepared: list[PreparedRepo] = []
    temp_root = output / "_work"
    temp_root.mkdir(parents=True, exist_ok=True)

    for spec in repo_specs:
        try:
            prepared.append(prepare_repo(spec, temp_root, args.rerun))
        except Exception as exc:
            unsupported_items.append({"scope": spec.name, "metric": "clone_or_prepare", "reason": _short_error(exc)})

    if args.benchmark and args.max_repos:
        prepared = select_benchmark_buckets(prepared, args.max_repos)

    results: list[dict[str, Any]] = []
    for index, repo in enumerate(prepared):
        print(f"[metrics] repo={repo.spec.name} source={repo.source}")
        result = run_for_repo(
            repo,
            args,
            output,
            allow_baseline=index == 0,
            allow_real=args.mode != "both" or index == 0,
        )
        results.append(result)
        unsupported_items.extend(result.get("unsupported", []))

    remove_tree(temp_root)
    quality = run_quality_checks(output, skip_frontend=not args.frontend_quality)
    report = {
        "metadata": metadata | {"duration_seconds": round(time.perf_counter() - started, 2)},
        "repos": results,
        "aggregate": aggregate_results(results),
        "mock": collect_mode_summary(results, "mock"),
        "real": collect_mode_summary(results, "real_llm"),
        "baseline": collect_baseline_summary(results),
        "quality": quality,
        "resume_safe": build_resume_safe(results),
        "unsupported": unsupported_items + collect_unsupported(results, quality),
    }
    write_json_and_markdown(report, output)
    print(f"[metrics] wrote {output / 'codepilot_quant_metrics.json'}")
    print(f"[metrics] wrote {output / 'codepilot_quant_metrics.md'}")
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run reproducible CodePilot V3.7 quant metrics.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--repo-url")
    source.add_argument("--repo-path")
    source.add_argument("--benchmark")
    parser.add_argument("--mode", choices=("scan-only", "mock", "real", "baseline", "both"), default="scan-only")
    parser.add_argument("--max-repos", type=int, default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT.relative_to(ROOT_DIR)))
    parser.add_argument("--rerun", action="store_true", help="Ignore successful existing repo+mode artifacts.")
    parser.add_argument(
        "--frontend-quality", action="store_true", help="Also run frontend npm test/build quality gates."
    )
    return parser.parse_args(argv)


def ensure_output_dirs(output: Path) -> None:
    for dirname in ("mock_review_outputs", "real_llm_review_outputs", "baseline_direct_llm_outputs", "raw_logs"):
        (output / dirname).mkdir(parents=True, exist_ok=True)


def build_metadata(args: argparse.Namespace, output: Path) -> dict[str, Any]:
    settings = Settings()
    resolved = resolve_llm_config(settings)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "project_root": str(ROOT_DIR),
        "output_dir": str(output),
        "mode": args.mode,
        "token_estimation_method": token_method(),
        "token_estimation_approximate": tiktoken is None,
        "real_llm_config": {
            "use_mock_llm": settings.use_mock_llm,
            "enable_real_llm": settings.enable_real_llm,
            "provider": resolved.provider,
            "model": resolved.model,
            "base_url_host": urlparse(resolved.base_url).netloc,
            "api_key_env_name": resolved.api_key_env_name,
            "api_key_present": bool(resolved.api_key),
            "api_key_preview": mask_key(resolved.api_key),
        },
        "commands": {
            "both": REPRO_BOTH_COMMAND,
            "real": REPRO_REAL_COMMAND,
            "baseline": REPRO_BASELINE_COMMAND,
        },
    }


def resolve_repo_specs(args: argparse.Namespace) -> list[RepoSpec]:
    if args.repo_path:
        path = Path(args.repo_path).resolve()
        return [RepoSpec(name=safe_repo_name(path.name), path=path, size="local", note="user supplied local path")]
    if args.repo_url:
        return [
            RepoSpec(
                name=safe_repo_name(Path(urlparse(args.repo_url).path).stem),
                url=args.repo_url,
                note="user supplied URL",
            )
        ]

    benchmark = (
        (ROOT_DIR / args.benchmark).resolve() if not Path(args.benchmark).is_absolute() else Path(args.benchmark)
    )
    data = json.loads(benchmark.read_text(encoding="utf-8"))
    raw_repos = data.get("repos", data if isinstance(data, list) else [])
    specs = []
    for item in raw_repos:
        categories = item.get("categories") or {}
        language = categories.get("language", "")
        if language not in {"python", "mixed"}:
            continue
        specs.append(
            RepoSpec(
                name=safe_repo_name(item.get("id") or item.get("name") or Path(urlparse(item["url"]).path).stem),
                url=item["url"],
                size=categories.get("size", "unknown"),
                note=item.get("notes", ""),
                dataset_id=item.get("id"),
            )
        )
    return specs


def candidate_specs_for_benchmark(specs: list[RepoSpec], max_repos: int) -> list[RepoSpec]:
    """Bound benchmark preparation while keeping small/medium/upper candidates."""
    if max_repos <= 0:
        return []
    selected: list[RepoSpec] = []
    for size in ("small", "medium", "large"):
        matches = [spec for spec in specs if spec.size == size]
        selected.extend(matches[: max(2, max_repos)])
    if len(selected) < max_repos:
        selected.extend(spec for spec in specs if spec not in selected)
    seen: set[str] = set()
    deduped: list[RepoSpec] = []
    for spec in selected:
        key = spec.url or str(spec.path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(spec)
    return deduped[: max(max_repos * 3, max_repos)]


def prepare_repo(spec: RepoSpec, temp_root: Path, rerun: bool) -> PreparedRepo:
    if spec.path is not None:
        if not spec.path.exists():
            raise FileNotFoundError(spec.path)
        return PreparedRepo(spec=spec, path=spec.path, source="local_path")

    assert spec.url is not None
    repo_dir = temp_root / spec.name / "repo"
    if repo_dir.exists() and not rerun:
        return PreparedRepo(spec=spec, path=repo_dir, source="cached_clone", clone_duration_seconds=0.0)
    if repo_dir.parent.exists():
        shutil.rmtree(repo_dir.parent)
    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    print(f"[metrics] cloning {spec.url}")
    cloned = CloneService(repo_dir.parent).clone(spec.url, "clone")
    if cloned != repo_dir:
        if repo_dir.exists():
            shutil.rmtree(repo_dir)
        shutil.move(str(cloned), str(repo_dir))
    return PreparedRepo(
        spec=spec, path=repo_dir, source="first_clone", clone_duration_seconds=round(time.perf_counter() - started, 2)
    )


def remove_tree(path: Path) -> None:
    def _chmod_and_retry(func, failed_path: str, _exc_info) -> None:
        try:
            os.chmod(failed_path, S_IWRITE)
            func(failed_path)
        except OSError:
            pass

    if path.exists():
        shutil.rmtree(path, onerror=_chmod_and_retry)


def select_benchmark_buckets(prepared: list[PreparedRepo], max_repos: int) -> list[PreparedRepo]:
    buckets = {
        "small": (0, 10),
        "medium": (20, 30),
        "upper_limit": (40, 50),
    }
    scored: list[tuple[str, int, int, PreparedRepo]] = []
    for repo in prepared:
        py_count = count_git_tracked_python(repo.path)
        for bucket, (low, high) in buckets.items():
            distance = 0 if low <= py_count <= high else min(abs(py_count - low), abs(py_count - high))
            scored.append((bucket, distance, py_count, repo))
    selected: list[PreparedRepo] = []
    used: set[Path] = set()
    for bucket in buckets:
        candidates = [item for item in scored if item[0] == bucket and item[3].path not in used]
        if not candidates:
            continue
        _bucket, _distance, py_count, repo = sorted(candidates, key=lambda item: (item[1], item[2], item[3].spec.name))[
            0
        ]
        selected.append(repo)
        used.add(repo.path)
        print(f"[metrics] selected {bucket}: {repo.spec.name} python_files={py_count}")
        if len(selected) >= max_repos:
            return selected
    if len(selected) < max_repos:
        for repo in prepared:
            if repo.path not in used:
                selected.append(repo)
                used.add(repo.path)
            if len(selected) >= max_repos:
                break
    return selected[:max_repos]


def run_for_repo(
    repo: PreparedRepo,
    args: argparse.Namespace,
    output: Path,
    *,
    allow_baseline: bool = True,
    allow_real: bool = True,
) -> dict[str, Any]:
    repo_started = time.perf_counter()
    settings = metrics_settings(output)
    context_started = time.perf_counter()
    scan = scan_repository(repo.path, settings)
    context = build_context(repo, settings)
    context_duration = round(time.perf_counter() - context_started, 2)
    token_metrics = token_compression_metrics(repo.path, context, settings)
    code_metrics = code_understanding_metrics(repo.path, context)
    result: dict[str, Any] = {
        "name": repo.spec.name,
        "url": repo.spec.url,
        "path": str(repo.path),
        "size": repo.spec.size,
        "note": repo.spec.note,
        "source": repo.source,
        "benchmark_threshold": benchmark_threshold(repo.path),
        "scan": scan,
        "tokens": token_metrics,
        "code_understanding": code_metrics,
        "performance": {
            "clone_duration_seconds": repo.clone_duration_seconds,
            "context_build_duration_seconds": context_duration,
            "e2e_duration_seconds": None,
        },
        "unsupported": [],
    }
    modes = modes_to_run(args.mode)
    if "mock" in modes:
        result["mock"] = run_review_mode(repo, context, settings, output, "mock", rerun=args.rerun)
    if "real_llm" in modes and allow_real:
        result["real_llm"] = run_review_mode(repo, context, settings, output, "real_llm", rerun=args.rerun)
        if result["real_llm"].get("review_success"):
            merge_real_token_usage(result["tokens"], result["real_llm"])
    elif "real_llm" in modes:
        result["real_llm_skipped"] = (
            "Real LLM is limited to the first selected repo in both mode after a prior slow/hung real run."
        )
    if "baseline" in modes and allow_baseline:
        result["baseline"] = run_baseline(repo, context, settings, output, rerun=args.rerun)
    elif "baseline" in modes:
        result["baseline_skipped"] = "Baseline is intentionally limited to the first selected small repo."
    result["performance"]["e2e_duration_seconds"] = round(time.perf_counter() - repo_started, 2)
    return result


def metrics_settings(output: Path) -> Settings:
    return Settings(
        reports_path=output / "raw_logs" / "codepilot_internal_reports",
        workspace_path=output / "_pipeline_workspace",
        database_path=output / "raw_logs" / "metrics.sqlite",
        use_mock_llm=True,
        enable_real_llm=True,
    )


def build_context(repo: PreparedRepo, settings: Settings) -> ReviewContext:
    manifest = SandboxFilter().build_manifest(repo.path, settings.max_files, settings.max_file_size_bytes)
    parser = select_parser(repo.path, manifest)
    indexer = RepositoryIndexer(parser, settings.max_files, settings.max_file_size_bytes)
    indexer.set_manifest(manifest)
    indexer.set_large_repo_threshold(settings.large_repo_threshold)
    return indexer.build_review_context(repo.path, repo.spec.url or str(repo.path))


def select_parser(repo_path: Path, manifest) -> Any:
    extensions = {file.extension for file in manifest.files}
    language_extensions = {
        "python": {".py"},
        "javascript": {".js", ".jsx"},
        "typescript": {".ts", ".tsx"},
    }
    languages = [
        language
        for language in default_parser_registry.languages()
        if extensions.intersection(language_extensions.get(language, set()))
    ]
    if not languages:
        return default_parser_registry.create("python")
    priority = {"python": 0, "javascript": 1, "typescript": 2}
    parsers = [
        default_parser_registry.create(language)
        for language in sorted(languages, key=lambda item: priority.get(item, 99))
    ]
    return CompositeSourceParser(parsers) if len(parsers) > 1 else parsers[0]


def scan_repository(repo_path: Path, settings: Settings) -> dict[str, Any]:
    raw_total_files = sum(1 for path in repo_path.rglob("*") if path.is_file())
    git_tracked = git_ls_files(repo_path)
    repo_git_tracked_files = len(git_tracked)
    manifest = SandboxFilter().build_manifest(repo_path, settings.max_files, settings.max_file_size_bytes)
    eligible_files = len(manifest.files)
    tracked_paths = (
        [repo_path / path for path in git_tracked]
        if git_tracked
        else [path for path in repo_path.rglob("*") if path.is_file()]
    )
    source_files = [path for path in tracked_paths if path.suffix.lower() in ALLOWED_SOURCE_EXTENSIONS]
    python_files = [path for path in source_files if path.suffix.lower() == ".py"]
    js_ts_files = [path for path in source_files if path.suffix.lower() in {".js", ".jsx", ".ts", ".tsx"}]
    skipped_large = 0
    skipped_unsupported = 0
    for path in tracked_paths:
        rel_parts = path.relative_to(repo_path).parts if path.exists() else Path(path).parts
        if any(part in IGNORE_DIRS for part in rel_parts):
            continue
        if path.suffix.lower() not in ALLOWED_SOURCE_EXTENSIONS:
            skipped_unsupported += 1
            continue
        try:
            if path.stat().st_size > settings.max_file_size_bytes:
                skipped_large += 1
        except OSError:
            pass
    denominator = repo_git_tracked_files or raw_total_files
    raw_reference = pct((raw_total_files - eligible_files) / raw_total_files) if raw_total_files else None
    return {
        "raw_total_files": raw_total_files,
        "repo_git_tracked_files": repo_git_tracked_files,
        "eligible_files": eligible_files,
        "source_files": len(source_files),
        "python_files": len(python_files),
        "js_ts_files": len(js_ts_files),
        "skipped_large_files": skipped_large,
        "skipped_unsupported_files": skipped_unsupported,
        "max_directory_depth": max_directory_depth(repo_path),
        "file_noise_reduction_rate": pct((denominator - eligible_files) / denominator) if denominator else None,
        "raw_file_noise_reduction_rate_reference": raw_reference,
        "noise_scope_note": "Primary denominator is git ls-files; raw_total_files is reference only.",
    }


def token_compression_metrics(repo_path: Path, context: ReviewContext, settings: Settings) -> dict[str, Any]:
    counter = PromptTokenCounter(settings.openai_model)
    source_text = "\n\n".join(read_context_source_text(repo_path, summary.path) for summary in context.file_summaries)
    renderer = PromptRenderer(settings.final_prompt_token_budget, settings.openai_model)
    structured_prompt = renderer.render(context)
    baseline_tokens = counter.count(source_text)
    structured_tokens = counter.count(structured_prompt)
    compression = pct((baseline_tokens - structured_tokens) / baseline_tokens) if baseline_tokens else None
    return {
        "baseline_source_tokens": int(baseline_tokens),
        "structured_context_tokens": int(structured_tokens),
        "token_compression_rate": compression,
        "token_estimation_method": token_method(),
        "token_scope_note": (
            "Both counts use analyzed CodePilot file_summaries scope; source is raw text for those files, "
            "context is PromptRenderer output."
        ),
        "real_llm_input_tokens": unsupported("real mode not run or provider usage unavailable"),
        "real_llm_output_tokens": unsupported("real mode not run or provider usage unavailable"),
        "real_llm_total_tokens": unsupported("real mode not run or provider usage unavailable"),
        "real_call_token_compression_rate": unsupported("real mode not run or provider usage unavailable"),
    }


def code_understanding_metrics(repo_path: Path, context: ReviewContext) -> dict[str, Any]:
    py_summaries = [summary for summary in context.file_summaries if summary.path.endswith(".py")]
    ast_success = 0
    symbol_files = 0
    for summary in py_summaries:
        text = read_context_source_text(repo_path, summary.path)
        try:
            ast.parse(text)
            ast_success += 1
        except SyntaxError:
            pass
        if summary.functions or summary.classes or summary.imports:
            symbol_files += 1
    dependency_edges = sum(len(targets) for targets in context.dependency_edges.values())
    return {
        "total_code_lines": sum(summary.line_count for summary in context.file_summaries),
        "total_functions": sum(len(summary.functions) for summary in context.file_summaries),
        "total_classes": sum(len(summary.classes) for summary in context.file_summaries),
        "total_imports": sum(len(summary.imports) for summary in context.file_summaries),
        "ast_parse_success_rate": pct(ast_success / len(py_summaries))
        if py_summaries
        else unsupported("no Python files in analyzed context"),
        "symbol_extraction_coverage": pct(symbol_files / len(py_summaries))
        if py_summaries
        else unsupported("no Python files in analyzed context"),
        "dependency_edges": dependency_edges,
        "circular_dependency_groups": len(context.circular_dependencies),
    }


def run_review_mode(
    repo: PreparedRepo,
    context: ReviewContext,
    settings: Settings,
    output: Path,
    mode: str,
    *,
    rerun: bool,
) -> dict[str, Any]:
    out_dir = output / ("mock_review_outputs" if mode == "mock" else "real_llm_review_outputs")
    stem = f"{repo.spec.name}_{mode}"
    md_path = out_dir / f"{stem}.md"
    json_path = out_dir / f"{stem}.json"
    if md_path.exists() and json_path.exists() and not rerun:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        data["resume_status"] = "skipped_existing"
        return data

    started = time.perf_counter()
    client: Any = MockLLMClient() if mode == "mock" else TrackingRealLLMClient(settings, max_retries=1)
    generator = ReportGenerator(
        client,
        out_dir,
        settings.final_prompt_token_budget,
        token_model=settings.openai_model,
        agent_concurrency=settings.review_agent_concurrency,
        agent_mode=settings.review_agent_mode,
    )
    generator.configure_engine(settings.review_engine)
    try:
        result = generator.generate(stem, context)
        md_path.write_text(result.report, encoding="utf-8")
        metrics = review_quality_metrics(result, context)
        metrics.update(
            {
                "review_success": True,
                "mode": mode,
                "duration_seconds": round(time.perf_counter() - started, 2),
                "failure_stage": None,
                "failure_reason_available": False,
                "llm_retry_count": getattr(client, "retry_count", 0),
                "model": getattr(getattr(client, "resolved", None), "model", "mock"),
                "base_url_host": urlparse(getattr(getattr(client, "resolved", None), "base_url", "")).netloc,
                "markdown_path": str(md_path),
                "json_path": str(json_path),
                "resume_status": "rerun" if rerun else "completed",
            }
        )
        if mode == "real_llm":
            metrics.update(client.usage)
            baseline_tokens = PromptTokenCounter(settings.openai_model).count(
                "\n\n".join(read_context_source_text(repo.path, summary.path) for summary in context.file_summaries)
            )
            input_tokens = metrics.get("real_llm_input_tokens")
            if isinstance(input_tokens, int) and baseline_tokens:
                metrics["real_call_token_compression_rate"] = pct((baseline_tokens - input_tokens) / baseline_tokens)
        json_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
        return metrics
    except Exception as exc:
        metrics = {
            "review_success": False,
            "mode": mode,
            "duration_seconds": round(time.perf_counter() - started, 2),
            "failure_stage": "real_llm_review" if mode == "real_llm" else "mock_review",
            "failure_reason_available": True,
            "error_msg": _short_error(exc),
            "llm_retry_count": getattr(client, "retry_count", 0),
            "resume_status": "failed",
            "markdown_path": str(md_path),
            "json_path": str(json_path),
        }
        md_path.write_text(f"# {repo.spec.name} {mode} failed\n\n{metrics['error_msg']}\n", encoding="utf-8")
        json_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
        return metrics


def run_baseline(
    repo: PreparedRepo,
    context: ReviewContext,
    settings: Settings,
    output: Path,
    *,
    rerun: bool,
) -> dict[str, Any]:
    out_dir = output / "baseline_direct_llm_outputs"
    stem = f"{repo.spec.name}_baseline_direct_llm"
    md_path = out_dir / f"{stem}.md"
    json_path = out_dir / f"{stem}.json"
    if md_path.exists() and json_path.exists() and not rerun:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        data["resume_status"] = "skipped_existing"
        return data
    started = time.perf_counter()
    client = TrackingRealLLMClient(settings, max_retries=1)
    raw_source = "\n\n".join(
        f"### {summary.path}\n```\n{read_context_source_text(repo.path, summary.path)}\n```"
        for summary in context.file_summaries
    )
    prompt = baseline_prompt(raw_source)
    try:
        report = client.generate_review(prompt)
        md_path.write_text(report, encoding="utf-8")
        pseudo = ReportResult(report=report, export_path=md_path)
        metrics = review_quality_metrics(pseudo, context)
        metrics.update(
            {
                "review_success": True,
                "mode": "baseline_direct_llm",
                "duration_seconds": round(time.perf_counter() - started, 2),
                "failure_stage": None,
                "failure_reason_available": False,
                "llm_retry_count": client.retry_count,
                "model": client.resolved.model,
                "base_url_host": urlparse(client.resolved.base_url).netloc,
                "limitations": "One small repo qualitative baseline; not a large-scale controlled experiment.",
                "markdown_path": str(md_path),
                "json_path": str(json_path),
                "resume_status": "rerun" if rerun else "completed",
            }
        )
        metrics.update(client.usage)
        json_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
        return metrics
    except Exception as exc:
        metrics = {
            "review_success": False,
            "mode": "baseline_direct_llm",
            "duration_seconds": round(time.perf_counter() - started, 2),
            "failure_stage": "baseline_direct_llm",
            "failure_reason_available": True,
            "error_msg": _short_error(exc),
            "llm_retry_count": client.retry_count,
            "limitations": "One small repo qualitative baseline; failed run is not used for deltas.",
            "markdown_path": str(md_path),
            "json_path": str(json_path),
            "resume_status": "failed",
        }
        md_path.write_text(
            f"# {repo.spec.name} baseline_direct_llm failed\n\n{metrics['error_msg']}\n", encoding="utf-8"
        )
        json_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
        return metrics


def merge_real_token_usage(token_metrics: dict[str, Any], real_metrics: dict[str, Any]) -> None:
    for key in (
        "real_llm_input_tokens",
        "real_llm_output_tokens",
        "real_llm_total_tokens",
        "real_call_token_compression_rate",
    ):
        if key in real_metrics:
            token_metrics[key] = real_metrics[key]


def baseline_prompt(raw_source: str) -> str:
    section_lines = "\n".join(f"{index}. {section}" for index, section in enumerate(REPORT_SECTIONS, start=1))
    return (
        "Review this repository using only the raw source code below.\n"
        "Return markdown with exactly four top-level sections:\n"
        f"{section_lines}\n"
        "Every finding should cite concrete file paths and code elements when possible.\n\n"
        f"{raw_source}"
    )


def review_quality_metrics(result: ReportResult, context: ReviewContext) -> dict[str, Any]:
    findings = []
    agent_states = result.agent_states or []
    for state in agent_states:
        findings.extend(state.findings)
    if not findings:
        findings = split_markdown_findings(result.report)
    total_findings = len(findings)
    evidence_ids = {record.evidence_id for record in context.evidence}
    valid_paths = {summary.path for summary in context.file_summaries}
    symbols = {symbol.name for summary in context.file_summaries for symbol in summary.symbols}
    evidence_bound = 0
    invalid_refs = 0
    generic = 0
    findings_by_agent: dict[str, int] = {}
    findings_by_severity: Counter[str] = Counter()
    if agent_states:
        for state in agent_states:
            findings_by_agent[state.agent_id] = len(state.findings)
            for finding in state.findings:
                findings_by_severity[finding.severity] += 1
                if finding.evidence_ids and all(eid in evidence_ids for eid in finding.evidence_ids):
                    evidence_bound += 1
                invalid_refs += sum(1 for eid in finding.evidence_ids if eid not in evidence_ids)
                invalid_refs += sum(1 for path in finding.files if path not in valid_paths)
                text = " ".join([finding.title or "", finding.description, finding.recommendation or ""])
                if is_generic_text(text):
                    generic += 1
    else:
        for text in findings:
            path_refs = extract_paths(text)
            has_path = any(path in valid_paths for path in path_refs)
            has_symbolish = bool(
                SYMBOL_RE.search(text)
                or RAW_EV_RE.search(text)
                or any(symbol in text for symbol in list(symbols)[:200])
            )
            if has_path and has_symbolish:
                evidence_bound += 1
            invalid_refs += sum(1 for path in path_refs if path not in valid_paths)
            invalid_refs += sum(1 for eid in RAW_EV_RE.findall(text) if eid not in evidence_ids)
            if is_generic_text(text):
                generic += 1
    report_sections_complete = all(
        re.search(rf"^#\s+{re.escape(section)}\s*$", result.report, re.MULTILINE) for section in REPORT_SECTIONS
    )
    current_contract_sections = [
        "Executive Summary",
        "Agent Findings",
        "Action Plan",
        "Evidence Appendix",
    ]
    current_contract_complete = all(
        re.search(rf"^#\s+{re.escape(section)}\s*$", result.report, re.MULTILINE)
        for section in current_contract_sections
    )
    return {
        "total_findings": total_findings,
        "findings_by_agent": findings_by_agent,
        "findings_by_severity": dict(findings_by_severity),
        "evidence_total": len(context.evidence),
        "evidence_bound_findings": evidence_bound,
        "evidence_binding_rate": pct(evidence_bound / total_findings) if total_findings else None,
        "generic_suggestion_rate": pct(generic / total_findings) if total_findings else None,
        "invalid_evidence_refs": invalid_refs,
        "report_sections_complete": report_sections_complete,
        "current_report_contract_complete": current_contract_complete,
        "markdown_export_available": bool(result.report.strip()),
        "raw_internal_id_leak_count": len(RAW_EV_RE.findall(result.report)),
        "zh_en_supported": True,
    }


def split_markdown_findings(markdown: str) -> list[str]:
    items = [line.strip()[2:].strip() for line in markdown.splitlines() if line.strip().startswith("- ")]
    if items:
        return items
    paragraphs = [
        part.strip() for part in re.split(r"\n\s*\n", markdown) if part.strip() and not part.lstrip().startswith("#")
    ]
    split: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) > 600:
            split.extend(part.strip() for part in re.split(r"(?<=[.;])\s+", paragraph) if part.strip())
        else:
            split.append(paragraph)
    return split


def run_quality_checks(output: Path, *, skip_frontend: bool) -> dict[str, Any]:
    checks = [
        ("pytest_all", ["python", "-m", "pytest", "tests/", "-q"], ROOT_DIR),
        ("ruff", ["ruff", "check", "."], ROOT_DIR),
        ("audit_harness", ["python", "scripts/audit_harness.py"], ROOT_DIR),
    ]
    if skip_frontend:
        frontend = {
            "frontend_tests": {"status": "skipped", "reason": "frontend not changed"},
            "frontend_build": {"status": "skipped", "reason": "frontend not changed"},
        }
    else:
        checks.extend(
            [
                ("frontend_tests", ["npm", "test"], ROOT_DIR / "frontend"),
                ("frontend_build", ["npm", "run", "build"], ROOT_DIR / "frontend"),
            ]
        )
        frontend = {}
    results: dict[str, Any] = {}
    for name, command, cwd in checks:
        results[name] = run_logged_command(name, command, cwd, output / "raw_logs")
    results.update(frontend)
    return results


def run_logged_command(name: str, command: list[str], cwd: Path, log_dir: Path) -> dict[str, Any]:
    log_path = log_dir / f"{name}.log"
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=300,
            encoding="utf-8",
            errors="replace",
        )
        log_path.write_text(
            f"$ {' '.join(command)}\n\nSTDOUT:\n{completed.stdout}\n\nSTDERR:\n{completed.stderr}\n",
            encoding="utf-8",
        )
        return {
            "status": "passed" if completed.returncode == 0 else "failed",
            "returncode": completed.returncode,
            "duration_seconds": round(time.perf_counter() - started, 2),
            "log_path": str(log_path),
        }
    except FileNotFoundError as exc:
        log_path.write_text(str(exc), encoding="utf-8")
        return {"status": "skipped", "reason": _short_error(exc), "log_path": str(log_path)}
    except subprocess.TimeoutExpired as exc:
        log_path.write_text(str(exc), encoding="utf-8")
        return {
            "status": "failed",
            "reason": "timeout",
            "duration_seconds": round(time.perf_counter() - started, 2),
            "log_path": str(log_path),
        }


def aggregate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "repo_count": len(results),
        "avg_file_noise_reduction_rate": avg_metric(results, ("scan", "file_noise_reduction_rate")),
        "avg_token_compression_rate": avg_metric(results, ("tokens", "token_compression_rate")),
        "avg_ast_parse_success_rate": avg_metric(results, ("code_understanding", "ast_parse_success_rate")),
        "avg_symbol_extraction_coverage": avg_metric(results, ("code_understanding", "symbol_extraction_coverage")),
        "avg_mock_success_rate": success_rate(results, "mock"),
        "avg_real_success_rate": success_rate(results, "real_llm"),
    }


def collect_mode_summary(results: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    rows = [result[mode] for result in results if mode in result]
    successes = [row for row in rows if row.get("review_success")]
    return {
        "attempted": len(rows),
        "succeeded": len(successes),
        "success_rate": pct(len(successes) / len(rows)) if rows else None,
        "avg_evidence_binding_rate": avg_rows(successes, "evidence_binding_rate"),
        "avg_generic_suggestion_rate": avg_rows(successes, "generic_suggestion_rate"),
        "avg_duration_seconds": avg_rows(successes, "duration_seconds"),
        "token_usage": {
            "input": sum(
                row.get("real_llm_input_tokens", 0)
                for row in successes
                if isinstance(row.get("real_llm_input_tokens"), int)
            ),
            "output": sum(
                row.get("real_llm_output_tokens", 0)
                for row in successes
                if isinstance(row.get("real_llm_output_tokens"), int)
            ),
            "total": sum(
                row.get("real_llm_total_tokens", 0)
                for row in successes
                if isinstance(row.get("real_llm_total_tokens"), int)
            ),
        },
    }


def collect_baseline_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [result["baseline"] for result in results if "baseline" in result]
    summary = (
        collect_mode_summary([{"baseline": row} for row in rows], "baseline")
        if rows
        else {"attempted": 0, "succeeded": 0}
    )
    for result in results:
        real = result.get("real_llm")
        baseline = result.get("baseline")
        if real and baseline and real.get("review_success") and baseline.get("review_success"):
            summary["evidence_binding_rate_delta"] = round(
                (real.get("evidence_binding_rate") or 0) - (baseline.get("evidence_binding_rate") or 0), 1
            )
            summary["generic_suggestion_rate_delta"] = round(
                (baseline.get("generic_suggestion_rate") or 0) - (real.get("generic_suggestion_rate") or 0), 1
            )
            summary["format_completion_delta"] = int(bool(real.get("report_sections_complete"))) - int(
                bool(baseline.get("report_sections_complete"))
            )
            break
    summary["limitations"] = (
        "Baseline runs only one small repo and is qualitative, not a large-scale controlled experiment."
    )
    return summary


def build_resume_safe(results: list[dict[str, Any]]) -> list[str]:
    if not results:
        return []
    lines = []
    noise = avg_metric(results, ("scan", "file_noise_reduction_rate"))
    compression = avg_metric(results, ("tokens", "token_compression_rate"))
    mock = collect_mode_summary(results, "mock")
    if noise is not None and compression is not None:
        lines.append(
            f"Across {len(results)} benchmark repo(s), CodePilot measured {noise:.1f}% average file noise "
            f"reduction and {compression:.1f}% structured-context token compression."
        )
    if mock.get("attempted"):
        lines.append(
            f"Mock review success rate was {mock['success_rate']:.1f}% with "
            f"{mock.get('avg_evidence_binding_rate') or 0:.1f}% average evidence binding on successful runs."
        )
    real = collect_mode_summary(results, "real_llm")
    if real.get("succeeded") == 1:
        lines.append("Real LLM produced one successful repo-level validation; no multi-repo Real average is claimed.")
    elif real.get("succeeded", 0) > 1:
        lines.append(f"Real LLM succeeded on {real['succeeded']} repos with {real['success_rate']:.1f}% success rate.")
    return lines


def collect_unsupported(results: list[dict[str, Any]], quality: dict[str, Any]) -> list[dict[str, Any]]:
    unsupported_items = []
    for result in results:
        for section in ("tokens", "code_understanding"):
            for key, value in result.get(section, {}).items():
                if isinstance(value, dict) and value.get("status") == "unsupported":
                    unsupported_items.append({"scope": result["name"], "metric": key, "reason": value.get("reason")})
        for mode in ("real_llm", "baseline"):
            row = result.get(mode)
            if row and not row.get("review_success"):
                unsupported_items.append(
                    {"scope": result["name"], "metric": mode, "reason": row.get("error_msg", "run failed")}
                )
    for key, value in quality.items():
        if value.get("status") in {"failed", "skipped"}:
            unsupported_items.append(
                {"scope": "quality", "metric": key, "reason": value.get("reason") or value.get("status")}
            )
    return unsupported_items


def write_json_and_markdown(report: dict[str, Any], output: Path) -> None:
    (output / "codepilot_quant_metrics.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    (output / "codepilot_quant_metrics.md").write_text(render_markdown(report), encoding="utf-8")


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# CodePilot Quant Metrics Report",
        "",
        "## Metadata",
        f"- Generated at: {report['metadata']['generated_at']}",
        f"- Mode: {report['metadata']['mode']}",
        f"- Token method: {report['metadata']['token_estimation_method']}",
        "",
        "## Benchmark",
        "| Repo | Source | Python Files | Eligible Files | Threshold |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for repo in report["repos"]:
        lines.append(
            f"| {repo['name']} | {repo['source']} | {repo['scan']['python_files']} | "
            f"{repo['scan']['eligible_files']} | {repo['benchmark_threshold']['label']} |"
        )
    lines.extend(
        ["", "## Noise", "| Repo | Git tracked | Eligible | Reduction |", "| --- | ---: | ---: | ---: |"]
    )
    for repo in report["repos"]:
        lines.append(
            f"| {repo['name']} | {repo['scan']['repo_git_tracked_files']} | "
            f"{repo['scan']['eligible_files']} | {fmt_pct(repo['scan']['file_noise_reduction_rate'])} |"
        )
    lines.extend(
        ["", "## Token", "| Repo | Source Tokens | Context Tokens | Compression |", "| --- | ---: | ---: | ---: |"]
    )
    for repo in report["repos"]:
        lines.append(
            f"| {repo['name']} | {repo['tokens']['baseline_source_tokens']} | "
            f"{repo['tokens']['structured_context_tokens']} | "
            f"{fmt_pct(repo['tokens']['token_compression_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## Code Understanding",
            "| Repo | AST Success | Symbol Coverage | Functions | Classes | Dependency Edges |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for repo in report["repos"]:
        code = repo["code_understanding"]
        lines.append(
            f"| {repo['name']} | {fmt_pct(code['ast_parse_success_rate'])} | "
            f"{fmt_pct(code['symbol_extraction_coverage'])} | {code['total_functions']} | "
            f"{code['total_classes']} | {code['dependency_edges']} |"
        )
    lines.extend(
        [
            "",
            "## Agent Quality",
            "| Repo | Mode | Success | Findings | Evidence Binding | Generic Rate | Sections |",
            "| --- | --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for repo in report["repos"]:
        for mode in ("mock", "real_llm"):
            if mode in repo:
                row = repo[mode]
                lines.append(
                    f"| {repo['name']} | {mode} | {row.get('review_success')} | "
                    f"{row.get('total_findings', 0)} | {fmt_pct(row.get('evidence_binding_rate'))} | "
                    f"{fmt_pct(row.get('generic_suggestion_rate'))} | "
                    f"{row.get('report_sections_complete')} |"
                )
    lines.extend(["", "## Baseline"])
    baseline = report["baseline"]
    lines.append(f"- Attempted: {baseline.get('attempted', 0)}; succeeded: {baseline.get('succeeded', 0)}.")
    for key in ("evidence_binding_rate_delta", "generic_suggestion_rate_delta", "format_completion_delta"):
        if key in baseline:
            lines.append(f"- {key}: {baseline[key]}")
    lines.append(f"- Limitation: {baseline.get('limitations')}")
    lines.extend(
        [
            "",
            "## Performance",
            "| Repo | E2E | Clone | Context | Mock | Real | Baseline |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for repo in report["repos"]:
        perf = repo["performance"]
        mock_duration = repo.get("mock", {}).get("duration_seconds")
        real_duration = repo.get("real_llm", {}).get("duration_seconds")
        baseline_duration = repo.get("baseline", {}).get("duration_seconds")
        lines.append(
            f"| {repo['name']} | {fmt_seconds(perf.get('e2e_duration_seconds'))} | "
            f"{fmt_seconds(perf.get('clone_duration_seconds'))} | "
            f"{fmt_seconds(perf.get('context_build_duration_seconds'))} | {fmt_seconds(mock_duration)} | "
            f"{fmt_seconds(real_duration)} | {fmt_seconds(baseline_duration)} |"
        )
    lines.extend(["", "## Quality"])
    for name, result in report["quality"].items():
        lines.append(f"- {name}: {result.get('status')} ({result.get('log_path', result.get('reason', ''))})")
    lines.extend(["", "## Resume-safe"])
    if report["resume_safe"]:
        lines.extend(f"- {line}" for line in report["resume_safe"])
    else:
        lines.append("- No resume-safe claims generated because successful metric data was insufficient.")
    lines.extend(["", "## Unsupported"])
    if report["unsupported"]:
        lines.extend(
            f"- {item.get('scope')}: {item.get('metric')} - {item.get('reason')}" for item in report["unsupported"]
        )
    else:
        lines.append("- None.")
    lines.extend(["", "## Reproduction"])
    for command in report["metadata"]["commands"].values():
        lines.append(f"- `{command}`")
    lines.append("")
    return "\n".join(lines)


def modes_to_run(mode: str) -> set[str]:
    if mode == "both":
        return {"mock", "real_llm", "baseline"}
    if mode == "mock":
        return {"mock"}
    if mode == "real":
        return {"real_llm"}
    if mode == "baseline":
        return {"baseline"}
    return set()


def git_ls_files(repo_path: Path) -> list[str]:
    completed = subprocess.run(["git", "ls-files"], cwd=repo_path, text=True, capture_output=True)
    if completed.returncode != 0:
        return []
    return [line for line in completed.stdout.splitlines() if line.strip()]


def count_git_tracked_python(repo_path: Path) -> int:
    files = git_ls_files(repo_path)
    if files:
        return sum(1 for path in files if path.endswith(".py"))
    return sum(1 for path in repo_path.rglob("*.py") if ".git" not in path.parts)


def max_directory_depth(repo_path: Path) -> int:
    depths = []
    for path in repo_path.rglob("*"):
        if path.is_file() and ".git" not in path.parts:
            depths.append(len(path.relative_to(repo_path).parts) - 1)
    return max(depths, default=0)


def read_context_source_text(repo_path: Path, relative_path: str) -> str:
    try:
        return (repo_path / relative_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def benchmark_threshold(repo_path: Path) -> dict[str, Any]:
    count = count_git_tracked_python(repo_path)
    ranges = {"small": (0, 10), "medium": (20, 30), "upper_limit": (40, 50)}
    best = min(
        ranges.items(),
        key=lambda item: (
            0 if item[1][0] <= count <= item[1][1] else min(abs(count - item[1][0]), abs(count - item[1][1]))
        ),
    )
    low, high = best[1]
    return {"label": best[0], "python_files": count, "matches": low <= count <= high, "target_range": f"{low}-{high}"}


def extract_paths(text: str) -> list[str]:
    return [match.group(1) or match.group(2) for match in PATH_RE.finditer(text)]


def is_generic_text(text: str) -> bool:
    return (
        bool(GENERIC_RE.search(text))
        and not extract_paths(text)
        and not RAW_EV_RE.search(text)
        and not SYMBOL_RE.search(text)
    )


def avg_metric(results: list[dict[str, Any]], path: tuple[str, str]) -> float | None:
    values = []
    for result in results:
        value = result.get(path[0], {}).get(path[1])
        if isinstance(value, int | float):
            values.append(float(value))
    return round(sum(values) / len(values), 1) if values else None


def avg_rows(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if isinstance(row.get(key), int | float)]
    return round(sum(values) / len(values), 2) if values else None


def success_rate(results: list[dict[str, Any]], mode: str) -> float | None:
    rows = [result[mode] for result in results if mode in result]
    if not rows:
        return None
    return pct(sum(1 for row in rows if row.get("review_success")) / len(rows))


def pct(value: float) -> float:
    return round(value * 100, 1)


def fmt_pct(value: Any) -> str:
    return f"{value:.1f}%" if isinstance(value, int | float) else "unsupported"


def fmt_seconds(value: Any) -> str:
    return f"{value:.2f}s" if isinstance(value, int | float) else "n/a"


def token_method() -> str:
    return "tiktoken" if tiktoken is not None else "codepilot_fallback_regex"


def unsupported(reason: str) -> dict[str, str]:
    return {"status": "unsupported", "reason": reason}


def safe_repo_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip().replace(".git", ""))
    return cleaned.strip("-") or "repo"


def mask_key(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "***"
    return f"{value[:3]}***{value[-4:]}"


def _short_error(exc: BaseException) -> str:
    return " ".join(str(exc).split())[:500] or type(exc).__name__


if __name__ == "__main__":
    raise SystemExit(main())
