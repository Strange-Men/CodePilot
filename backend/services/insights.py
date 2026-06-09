from __future__ import annotations

from collections import Counter
from pathlib import PurePosixPath

from backend.models.context import (
    CodeFileSummary,
    InsightReport,
    RepositoryContext,
    RepositoryInsight,
    ReviewContext,
    as_review_context,
)
from backend.services.prioritization import (
    is_docs_path,
    is_test_path,
    ordered_for_recommendations,
)


class RepositoryInsightEngine:
    def generate(self, context: ReviewContext | RepositoryContext) -> InsightReport:
        context = as_review_context(context)
        ordered = ordered_for_recommendations(context.file_summaries)
        production = [summary for summary in ordered if not is_test_path(summary.path)]
        tests = [summary for summary in ordered if is_test_path(summary.path)]
        components = self._major_components(ordered)
        repository_type = self._repository_type(context)
        return InsightReport(
            repository_type=repository_type,
            major_components=components,
            architecture_overview=self._architecture_overview(
                context,
                repository_type,
                components,
            ),
            risk_hotspots=self._risk_hotspots(context, production),
            test_hotspots=self._test_hotspots(context, tests),
            onboarding_guide=self._onboarding_guide(context, ordered),
            refactoring_candidates=self._refactoring_candidates(context, production),
        )

    def _architecture_overview(
        self,
        context: ReviewContext,
        repository_type: str,
        components: list[str],
    ) -> list[RepositoryInsight]:
        insights = [
            RepositoryInsight(
                title="Repository type",
                explanation=(
                    f"This appears to be a {repository_type.lower()}. That classification helps reviewers "
                    "interpret whether control flow begins at runtime entry points, public APIs, or reusable modules."
                ),
            ),
            RepositoryInsight(
                title="Runtime entry points",
                explanation=(
                    "These files are the best place to trace startup and top-level composition."
                    if context.entry_points
                    else "No explicit runtime entry point was detected, so consumers may enter through a library API."
                ),
                files=context.entry_points[:8],
            ),
            RepositoryInsight(
                title="Core modules",
                explanation=(
                    "These modules carry central behavior or receive multiple internal dependencies, so their "
                    "interfaces shape broad repository change risk."
                    if context.core_modules
                    else "No distinct core module boundary was detected from paths and dependency structure."
                ),
                files=context.core_modules[:10],
            ),
            RepositoryInsight(
                title="Supporting modules",
                explanation=(
                    "These modules provide narrower behavior around the core and are useful after the main "
                    "execution path is understood."
                    if context.supporting_modules
                    else "No separate supporting-module layer was detected."
                ),
                files=context.supporting_modules[:10],
            ),
        ]
        if components:
            insights.append(
                RepositoryInsight(
                    title="Major components",
                    explanation=(
                        "These directory-level components contain most analyzed behavior and provide a practical "
                        "map of ownership boundaries."
                    ),
                    files=components,
                )
            )
        return insights

    def _risk_hotspots(
        self,
        context: ReviewContext,
        ordered: list[CodeFileSummary],
    ) -> list[RepositoryInsight]:
        findings: list[RepositoryInsight] = []
        summaries = {summary.path: summary for summary in ordered}
        for path in context.hub_files[:5]:
            summary = summaries.get(path)
            if summary is None or summary.fan_in <= 0:
                continue
            findings.append(
                RepositoryInsight(
                    title=f"High dependency pressure in {path}",
                    explanation=(
                        f"{summary.fan_in} analyzed modules depend on this file. Interface or behavior changes here "
                        "can spread widely, so compatibility and focused tests matter more than its raw score."
                    ),
                    files=[path],
                )
            )

        overloaded = self._overloaded_files(context, ordered)
        for summary in overloaded[:5]:
            findings.append(
                RepositoryInsight(
                    title=f"Responsibility concentration in {summary.path}",
                    explanation=(
                        f"This file combines {summary.line_count} lines, {summary.function_count} functions, and "
                        f"a complexity estimate of {summary.complexity_estimate}. The concentration can hide "
                        "multiple reasons to change and make reviews harder to localize."
                    ),
                    files=[summary.path],
                )
            )

        production_paths = {summary.path for summary in ordered}
        for cycle in context.circular_dependencies[:5]:
            relevant_cycle = [path for path in cycle if path in production_paths]
            if not relevant_cycle:
                continue
            findings.append(
                RepositoryInsight(
                    title=f"Circular dependency group ({len(relevant_cycle)} modules)",
                    explanation=(
                        "This module group is mutually dependent. Treat it as one ownership problem: initialization, "
                        "testing, and ownership become harder because the modules cannot evolve independently."
                    ),
                    files=relevant_cycle,
                )
            )
        if not findings:
            findings.append(
                RepositoryInsight(
                    title="No concentrated structural hotspot detected",
                    explanation=(
                        "The analyzed graph has no dependency cycle, high fan-in module, or unusually concentrated "
                        "file. This lowers structural risk but does not replace behavioral or security review."
                    ),
                )
            )
        return findings

    def _test_hotspots(
        self,
        context: ReviewContext,
        tests: list[CodeFileSummary],
    ) -> list[RepositoryInsight]:
        findings: list[RepositoryInsight] = []
        for summary in self._overloaded_files(context, tests)[:5]:
            findings.append(
                RepositoryInsight(
                    title=f"Large test surface in {summary.path}",
                    explanation=(
                        f"This test file contains {summary.line_count} lines and {summary.function_count} functions. "
                        "Review fixture and scenario organization here separately from production refactoring."
                    ),
                    files=[summary.path],
                )
            )
        test_paths = {summary.path for summary in tests}
        for cycle in context.circular_dependencies:
            relevant_cycle = [path for path in cycle if path in test_paths]
            if not relevant_cycle:
                continue
            findings.append(
                RepositoryInsight(
                    title=f"Test dependency cycle ({len(relevant_cycle)} modules)",
                    explanation=(
                        "These test modules participate in a dependency cycle. Keep this signal in test maintenance "
                        "work so it does not displace production risks."
                    ),
                    files=relevant_cycle,
                )
            )
        return findings[:5]

    def _onboarding_guide(
        self,
        context: ReviewContext,
        ordered: list[CodeFileSummary],
    ) -> list[RepositoryInsight]:
        summaries = {summary.path: summary for summary in ordered}
        candidates = [
            *context.entry_points,
            *context.core_modules,
            *[summary.path for summary in ordered],
        ]
        reading_order: list[RepositoryInsight] = []
        seen: set[str] = set()
        for path in candidates:
            if path in seen or path not in summaries:
                continue
            seen.add(path)
            summary = summaries[path]
            if summary.file_role == "Entry Point":
                reason = "Start here to see how the application boots and connects its top-level dependencies."
            elif summary.is_hub:
                reason = (
                    "Read this next because many modules depend on it; its public behavior explains a large part "
                    "of the repository."
                )
            elif summary.file_role == "Core Module":
                reason = "Read this to understand a central domain or service boundary after startup is clear."
            else:
                reason = f"Read this for supporting context: {summary.purpose.rstrip('.')}."
            reading_order.append(
                RepositoryInsight(
                    title=f"{len(reading_order) + 1}. {path}",
                    explanation=reason,
                    files=[path],
                )
            )
            if len(reading_order) == 8:
                break
        if not reading_order:
            reading_order.append(
                RepositoryInsight(
                    title="No source reading order available",
                    explanation="No supported source files were analyzed for this repository.",
                )
            )
        return reading_order

    def _refactoring_candidates(
        self,
        context: ReviewContext,
        ordered: list[CodeFileSummary],
    ) -> list[RepositoryInsight]:
        candidates: list[RepositoryInsight] = []
        seen: set[tuple[str, ...]] = set()

        for summary in self._overloaded_files(context, ordered)[:5]:
            key = (summary.path,)
            seen.add(key)
            candidates.append(
                RepositoryInsight(
                    title=f"Split responsibilities in {summary.path}",
                    explanation=(
                        "Look for cohesive groups of functions or classes that can move behind a smaller interface. "
                        "The goal is to reduce independent reasons to change, not merely shorten the file."
                    ),
                    files=[summary.path],
                )
            )

        for summary in ordered:
            if not summary.is_hub or summary.fan_in < 2 or (summary.path,) in seen:
                continue
            seen.add((summary.path,))
            candidates.append(
                RepositoryInsight(
                    title=f"Stabilize the boundary around {summary.path}",
                    explanation=(
                        f"{summary.fan_in} modules depend on this bottleneck. A narrow interface and contract tests "
                        "can contain change impact before larger extraction work."
                    ),
                    files=[summary.path],
                )
            )

        for cycle in context.circular_dependencies:
            key = tuple(cycle)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                RepositoryInsight(
                    title="Break a circular dependency",
                    explanation=(
                        "Move the smallest shared contract or dependency inversion point to a neutral module so "
                        "these files can be tested and changed independently."
                    ),
                    files=cycle,
                )
            )
        if not candidates:
            candidates.append(
                RepositoryInsight(
                    title="Preserve current module boundaries",
                    explanation=(
                        "No strong structural refactoring candidate was detected. Prefer targeted changes backed "
                        "by tests instead of reorganizing modules solely from size or naming."
                    ),
                )
            )
        return candidates[:8]

    @staticmethod
    def _major_components(summaries: list[CodeFileSummary]) -> list[str]:
        component_counts: Counter[str] = Counter()
        for summary in summaries:
            parts = PurePosixPath(summary.path).parts
            component = parts[0] if len(parts) > 1 else PurePosixPath(summary.path).stem
            component_counts[component] += 1
        return [
            f"{component} ({count} files)"
            for component, count in sorted(
                component_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[:8]
        ]

    @staticmethod
    def _repository_type(context: ReviewContext) -> str:
        languages = {language.strip() for language in context.language.split("+")}
        lower_paths = [summary.path.lower() for summary in context.file_summaries]
        summaries = context.file_summaries
        production_paths = [path for path in lower_paths if not is_test_path(path) and not is_docs_path(path)]
        test_count = sum(is_test_path(path) for path in lower_paths)
        docs_count = sum(is_docs_path(path) for path in lower_paths)
        total = len(lower_paths)
        symbol_names = {
            name.lower()
            for summary in summaries
            for name in [*summary.classes, *summary.functions]
        }
        route_count = sum(len(summary.routes) for summary in summaries)
        has_frontend = any(
            path.endswith((".tsx", ".jsx"))
            or any(part in path.split("/") for part in {"frontend", "components", "pages"})
            for path in production_paths
        )
        has_backend = any(
            any(part in path.split("/") for part in {"backend", "api", "routes", "server"})
            for path in production_paths
        )
        if len(languages) > 1 and "Python" in languages and languages & {"JavaScript", "TypeScript"}:
            return "Full-stack mixed-language application"
        framework_markers = {
            "flask",
            "blueprint",
            "django",
            "fastapi",
            "starlette",
            "application",
            "request",
            "response",
        }
        if (
            route_count > 0
            or len(framework_markers & symbol_names) >= 2
            or any(
                marker in f"/{path}/"
                for path in production_paths
                for marker in ("/flask/", "/django/", "/starlette/")
            )
        ):
            return f"{context.language} web framework"
        if has_backend and (
            route_count > 0
            or any("/api/" in f"/{path}/" or "/routes/" in f"/{path}/" for path in production_paths)
        ):
            return f"{context.language} backend API"
        if has_frontend and not has_backend:
            return "Frontend application"
        sdk_markers = {"client", "sdk", "transport", "session"}
        if len(sdk_markers & symbol_names) >= 2 or any(
            part in {"client", "clients", "sdk"} for path in production_paths for part in path.split("/")
        ):
            return f"{context.language} SDK or client library"
        cli_paths = [
            path
            for path in production_paths
            if PurePosixPath(path).name.startswith("cli.")
            or PurePosixPath(path).stem in {"__main__", "command", "commands"}
        ]
        if cli_paths and (
            len(production_paths) <= 3
            or len(cli_paths) >= max(2, len(production_paths) // 3)
        ):
            return f"{context.language} CLI tool"
        if total and test_count / total >= 0.6:
            return f"Test-heavy {context.language} repository"
        if total and docs_count / total >= 0.6:
            return f"Docs-heavy {context.language} repository"
        if context.entry_points:
            return f"{context.language} application"
        return f"{context.language} library"

    @staticmethod
    def _overloaded_files(
        context: ReviewContext,
        ordered: list[CodeFileSummary],
    ) -> list[CodeFileSummary]:
        if not ordered:
            return []
        avg_lines = context.total_lines / len(ordered)
        line_threshold = max(200.0, avg_lines * 1.75)
        complexity_threshold = max(15.0, context.avg_complexity * 1.75)
        return [
            summary
            for summary in ordered
            if (
                summary.line_count >= line_threshold
                or summary.complexity_estimate >= complexity_threshold
                or summary.complexity_estimate >= 25
                or summary.function_count >= 15
                or (summary.function_count >= 12 and summary.fan_out >= 3)
            )
        ]
