from __future__ import annotations

from collections import Counter

from backend.core.report_contract import REPORT_SECTIONS
from backend.models.context import ReviewContext
from backend.models.review_state import AgentExecutionState
from backend.models.structured_review import ReviewFinding, StructuredReviewDraft
from backend.reviewers.constants import DEFAULT_SECTION_CONTENT, format_cycle_group
from backend.reviewers.evidence_display import (
    EvidenceDisplayMap,
    build_evidence_appendix,
    format_evidence_ref,
)
from backend.services.prioritization import is_test_path

SEVERITY_ORDER = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "informational": 4,
}


class HumanReadableReportComposer:
    """Compose a bounded V3 report from validated findings and safe repository metadata."""

    def compose(
        self,
        context: ReviewContext,
        draft: StructuredReviewDraft | None,
        agent_states: list[AgentExecutionState] | None = None,
        *,
        lang: str = "en",
    ) -> str:
        findings = self._unique_findings(draft.findings if draft is not None else [])
        agent_states = agent_states or []
        display_map = EvidenceDisplayMap.from_findings(findings)
        sections = [
            self._executive_summary(context, findings, display_map),
            self._repository_identity(context),
            self._how_it_works(context),
            self._architecture_map(context),
            self._agent_summary(agent_states, lang),
            self._agent_findings(agent_states, findings, display_map),
            self._contract_sections(findings, display_map, lang),
            self._action_plan(context, findings, display_map),
            self._evidence_appendix(context, findings, display_map, lang),
        ]
        return "\n\n".join(section for section in sections if section).rstrip() + "\n"

    def _executive_summary(
        self,
        context: ReviewContext,
        findings: list[ReviewFinding],
        display_map: EvidenceDisplayMap,
    ) -> str:
        severity_mix = Counter(self._severity(finding) for finding in findings)
        severity_text = ", ".join(
            f"{count} {severity}"
            for severity, count in sorted(severity_mix.items(), key=lambda item: SEVERITY_ORDER[item[0]])
        )
        if not severity_text:
            severity_text = "no validated risks"
        top_risks = self._ranked_findings(findings)[:5]
        lines = [
            "# Executive Summary",
            (
                f"CodePilot analyzed {context.analyzed_files} {context.language} source files and produced "
                f"{len(findings)} evidence-grounded findings ({severity_text})."
            ),
            "",
            "## Top Risks",
        ]
        if top_risks:
            lines.extend(self._compact_finding_line(finding, display_map) for finding in top_risks)
        else:
            lines.append(
                "- No validated evidence-grounded risk was produced. Treat this as limited evidence, "
                "not proof of safety."
            )
        return "\n".join(lines)

    @staticmethod
    def _repository_identity(context: ReviewContext) -> str:
        repository_type = context.insights.repository_type
        if not repository_type or repository_type == "Software repository":
            repository_type = f"{context.language} repository"
        components = ", ".join(context.insights.major_components[:6]) or "no dominant directory boundary detected"
        return "\n".join(
            [
                "# What This Repository Is",
                f"- **Type:** {repository_type}",
                f"- **Primary components:** {components}",
                (
                    f"- **Scope analyzed:** {context.analyzed_files} of {context.total_source_files} "
                    "supported source files"
                ),
                f"- **Repository summary:** {context.repository_summary or 'No repository summary was available.'}",
            ]
        )

    @staticmethod
    def _how_it_works(context: ReviewContext) -> str:
        entry_points = HumanReadableReportComposer._path_list(context.entry_points, 6)
        core_modules = HumanReadableReportComposer._path_list(context.core_modules, 8)
        supporting = HumanReadableReportComposer._path_list(context.supporting_modules, 6)
        if context.entry_points and context.core_modules:
            flow = (
                f"Execution begins around {entry_points}, then delegates into {core_modules}. "
                f"Supporting behavior is organized around {supporting}."
            )
        elif context.core_modules:
            flow = (
                f"No explicit runtime entry point was detected. Consumers appear to enter through the reusable "
                f"interfaces around {core_modules}; supporting behavior is organized around {supporting}."
            )
        else:
            flow = (
                "The static index did not identify a stable entry-point-to-core flow. Start with the architecture map "
                "and evidence-backed findings before assuming runtime behavior."
            )
        return "\n".join(
            [
                "# How It Works",
                flow,
                "",
                "- This description is based on paths, symbols, routes, and resolved internal dependencies.",
                "- It does not claim runtime semantics that were not present in the analyzed evidence.",
            ]
        )

    @staticmethod
    def _architecture_map(context: ReviewContext) -> str:
        lines = [
            "# Key Architecture Map",
            "",
            "| Area | Files | Why It Matters |",
            "| --- | --- | --- |",
            (
                f"| Entry points | {HumanReadableReportComposer._path_list(context.entry_points, 5)} | "
                "Trace startup and top-level composition here. |"
            ),
            (
                f"| Core modules | {HumanReadableReportComposer._path_list(context.core_modules, 6)} | "
                "These files define central behavior and change boundaries. |"
            ),
            (
                f"| Dependency hubs | {HumanReadableReportComposer._path_list(context.hub_files, 6)} | "
                "Changes can affect several internal consumers. |"
            ),
        ]
        if context.circular_dependencies:
            lines.extend(["", "## Cycle Groups"])
            lines.extend(
                format_cycle_group(cycle)
                for cycle in context.circular_dependencies[:5]
                if cycle
            )
        return "\n".join(lines)

    @staticmethod
    def _agent_summary(agent_states: list[AgentExecutionState], lang: str = "en") -> str:
        unavailable = "暂无数据" if lang == "zh" else "n/a"
        lines = [
            "# Agent Summary",
            "",
            "| Agent | Status | Findings | Severity Mix | Avg Confidence | Evidence |",
            "| --- | --- | ---: | --- | ---: | ---: |",
        ]
        if not agent_states:
            label = "暂无数据" if lang == "zh" else "Not available"
            lines.append(f"| {label} | not_applicable | 0 | none | {unavailable} | 0 |")
            return "\n".join(lines)
        for state in agent_states:
            severity_mix = Counter(
                HumanReadableReportComposer._severity(finding)
                for finding in state.findings
            )
            severity = ", ".join(
                f"{name}={count}"
                for name, count in sorted(severity_mix.items(), key=lambda item: SEVERITY_ORDER[item[0]])
            ) or "none"
            confidences = [
                finding.confidence
                for finding in state.findings
                if finding.confidence is not None
            ]
            average_confidence = (
                f"{sum(confidences) / len(confidences):.2f}"
                if confidences
                else unavailable
            )
            evidence_count = len(
                {
                    *state.evidence_ids,
                    *(
                        evidence_id
                        for finding in state.findings
                        for evidence_id in finding.evidence_ids
                    ),
                }
            )
            lines.append(
                f"| {state.agent_id} | {state.status} | {len(state.findings)} | {severity} | "
                f"{average_confidence} | {evidence_count} |"
            )
        return "\n".join(lines)

    @staticmethod
    def _agent_findings(
        agent_states: list[AgentExecutionState],
        findings: list[ReviewFinding],
        display_map: EvidenceDisplayMap,
    ) -> str:
        lines = [
            "# Agent Findings",
            (
                "Findings are grouped by the agent that produced them. "
                "Evidence references remain compact and snippet-free."
            ),
        ]
        if not agent_states:
            if not findings:
                lines.append("- No validated finding was produced.")
            else:
                lines.extend(
                    HumanReadableReportComposer._compact_finding_line(finding, display_map)
                    for finding in findings[:12]
                )
            return "\n".join(lines)
        for state in agent_states:
            lines.extend(
                [
                    "",
                    f"## {state.agent_id}",
                    f"Status: **{state.status}**; validation: **{state.validation_status}**.",
                ]
            )
            if not state.findings:
                detail = f" Error: {state.error}" if state.error else ""
                lines.append(f"No validated findings.{detail}")
                continue
            lines.extend(
                [
                    "",
                    "| Severity | Finding | Confidence | Files | Evidence |",
                    "| --- | --- | ---: | --- | --- |",
                ]
            )
            lines.extend(
                HumanReadableReportComposer._agent_finding_row(finding, display_map)
                for finding in state.findings[:8]
            )
        return "\n".join(lines)

    @staticmethod
    def _agent_finding_row(finding: ReviewFinding, display_map: EvidenceDisplayMap) -> str:
        title = HumanReadableReportComposer._table_cell(finding.title or finding.description)
        files = HumanReadableReportComposer._path_list(finding.files, 3)
        evidence = format_evidence_ref(display_map, finding.evidence_ids[:3]) or "none"
        return (
            f"| {HumanReadableReportComposer._severity(finding)} | {title} | "
            f"{(finding.confidence or 0.0):.2f} | {files} | {evidence} |"
        )

    @staticmethod
    def _contract_sections(findings: list[ReviewFinding], display_map: EvidenceDisplayMap, lang: str = "en") -> str:
        rendered: list[str] = []
        for section in REPORT_SECTIONS:
            section_findings = [finding for finding in findings if finding.section == section]
            if lang == "zh":
                body = "\n\n".join(finding.to_localized_markdown("zh", display_map) for finding in section_findings)
            else:
                body = "\n\n".join(finding.to_markdown(display_map) for finding in section_findings)
            rendered.append(f"# {section}\n{body or DEFAULT_SECTION_CONTENT}")
        return "\n\n".join(rendered)

    def _action_plan(
        self,
        context: ReviewContext,
        findings: list[ReviewFinding],
        display_map: EvidenceDisplayMap,
    ) -> str:
        actionable = [finding for finding in self._ranked_findings(findings) if finding.recommendation]
        lines = ["# Action Plan"]
        if not actionable:
            lines.append(
                "No evidence-grounded action is recommended yet. Gather targeted evidence before changing boundaries."
            )
            return "\n".join(lines)
        for index, finding in enumerate(actionable[:5], start=1):
            files = self._path_list(finding.files, 4)
            evidence = format_evidence_ref(display_map, finding.evidence_ids[:3])
            symbols = self._finding_symbols(context, finding)
            responsibility = (
                f"validated symbols {self._code_list(symbols, 5)}"
                if symbols
                else f"the cited code path in {files}"
            )
            why_it_matters = finding.impact.strip() if finding.impact else finding.description.strip()
            first_step = finding.first_step.strip() if finding.first_step else self._first_step(finding, symbols)
            if finding.validation_tests:
                validation = ", ".join(
                    self._format_validation_test(test) for test in finding.validation_tests
                )
            else:
                validation = self._validation_hint(context, finding.files, symbols)
            lines.extend(
                [
                    f"## {index}. {finding.title or finding.category or 'Repository finding'}",
                    f"- **Why it matters:** {why_it_matters}",
                    f"- **Where:** {files}",
                    f"- **Likely responsibility area:** {responsibility}.",
                    f"- **First step:** {first_step}",
                    f"- **Change risk:** {self._change_risk(context, finding)}",
                    f"- **Evidence:** {evidence or 'No validated evidence reference.'}",
                    f"- **Validation tests:** {validation}",
                ]
            )
            if finding.caveat:
                lines.append(f"- **Caveat:** {finding.caveat.strip()}")
        return "\n".join(lines)

    @staticmethod
    def _finding_symbols(
        context: ReviewContext,
        finding: ReviewFinding,
    ) -> list[str]:
        evidence_ids = set(finding.evidence_ids)
        symbols: list[str] = []
        for record in context.evidence:
            if record.evidence_id not in evidence_ids:
                continue
            for symbol in record.symbols:
                if symbol not in symbols:
                    symbols.append(symbol)
        return symbols

    @staticmethod
    def _first_step(finding: ReviewFinding, symbols: list[str]) -> str:
        location = HumanReadableReportComposer._path_list(finding.files, 2)
        target = (
            f"the code around {HumanReadableReportComposer._code_list(symbols, 3)}"
            if symbols
            else "the cited responsibility"
        )
        recommendation = (finding.recommendation or "").strip()
        next_step = (
            recommendation[0].lower() + recommendation[1:]
            if recommendation
            else "make the smallest evidence-backed change"
        )
        return (
            f"In {location}, add or confirm characterization coverage for {target}; "
            f"then {next_step}"
        )

    @staticmethod
    def _change_risk(context: ReviewContext, finding: ReviewFinding) -> str:
        summaries = {summary.path: summary for summary in context.file_summaries}
        cycle_paths = {
            path
            for cycle in context.circular_dependencies
            for path in cycle
        }
        if any(path in cycle_paths for path in finding.files):
            return "Higher structural risk because at least one cited file participates in a dependency cycle."
        fan_in = max(
            (summaries[path].fan_in for path in finding.files if path in summaries),
            default=0,
        )
        if fan_in:
            return f"Changes can affect up to {fan_in} resolved internal consumers of the cited files."
        return (
            f"{HumanReadableReportComposer._severity(finding).capitalize()} finding risk; "
            "keep the change local to the validated evidence and verify behavior before widening scope."
        )

    @staticmethod
    def _validation_hint(
        context: ReviewContext,
        files: list[str],
        symbols: list[str],
    ) -> str:
        target_tokens = {
            token
            for path in files
            for token in HumanReadableReportComposer._name_tokens(path)
        }
        target_tokens.update(
            token
            for symbol in symbols
            for token in HumanReadableReportComposer._name_tokens(symbol)
        )
        related_tests = [
            summary.path
            for summary in context.file_summaries
            if is_test_path(summary.path)
            and target_tokens.intersection(HumanReadableReportComposer._name_tokens(summary.path))
        ][:3]
        if related_tests:
            return f"Run {HumanReadableReportComposer._path_list(related_tests, 3)} before and after the change."
        target = HumanReadableReportComposer._code_list(symbols, 3) if symbols else "the cited behavior"
        return (
            f"No related test file was identified by name. Add a focused characterization test for {target}, "
            "then run the repository test suite."
        )

    @staticmethod
    def _evidence_appendix(
        context: ReviewContext,
        findings: list[ReviewFinding],
        display_map: EvidenceDisplayMap,
        lang: str = "en",
    ) -> str:
        evidence_section = build_evidence_appendix(
            findings, context.evidence, display_map, lang=lang,
        )
        if lang == "zh":
            metrics_title = "## 仓库指标"
        else:
            metrics_title = "## Repository Metrics"
        metrics_lines = [
            metrics_title,
            f"- {'源文件总数' if lang == 'zh' else 'Supported source files'}: {context.total_source_files}",
            f"- {'已分析文件' if lang == 'zh' else 'Analyzed files'}: {context.analyzed_files}",
            f"- {'已跳过文件' if lang == 'zh' else 'Skipped files'}: {context.skipped_files}",
            f"- {'总行数' if lang == 'zh' else 'Total lines'}: {context.total_lines}",
            f"- {'平均复杂度' if lang == 'zh' else 'Average complexity estimate'}: {context.avg_complexity:.2f}",
        ]
        return evidence_section + "\n\n" + "\n".join(metrics_lines)

    @staticmethod
    def _ranked_findings(findings: list[ReviewFinding]) -> list[ReviewFinding]:
        return sorted(
            findings,
            key=lambda finding: (
                bool(finding.files) and all(is_test_path(path) for path in finding.files),
                SEVERITY_ORDER[HumanReadableReportComposer._severity(finding)],
                -(finding.confidence or 0.0),
                finding.title or finding.description,
            ),
        )

    @staticmethod
    def _severity(finding: ReviewFinding) -> str:
        severity = finding.severity.lower()
        return severity if severity in SEVERITY_ORDER else "informational"

    @staticmethod
    def _compact_finding_line(finding: ReviewFinding, display_map: EvidenceDisplayMap) -> str:
        title = finding.title or finding.description
        files = HumanReadableReportComposer._path_list(finding.files, 3)
        evidence = format_evidence_ref(display_map, finding.evidence_ids[:2]) or "none"
        return (
            f"- **{title}** ({HumanReadableReportComposer._severity(finding)}, "
            f"confidence {(finding.confidence or 0.0):.2f}) in {files}; evidence: {evidence}."
        )

    @staticmethod
    def _path_list(paths: list[str], limit: int) -> str:
        if not paths:
            return "none detected"
        visible = ", ".join(f"`{path}`" for path in paths[:limit])
        if len(paths) > limit:
            visible += f", +{len(paths) - limit} more"
        return visible

    @staticmethod
    def _table_cell(value: str) -> str:
        normalized = " ".join(value.split())
        escaped: list[str] = []
        preceding_backslashes = 0
        for character in normalized:
            if character == "|" and preceding_backslashes % 2 == 0:
                escaped.append("\\")
            escaped.append(character)
            preceding_backslashes = preceding_backslashes + 1 if character == "\\" else 0
        return "".join(escaped)

    @staticmethod
    def _code_list(values: list[str], limit: int) -> str:
        return ", ".join(f"`{value}`" for value in values[:limit])

    @staticmethod
    def _format_validation_test(test: str) -> str:
        """Format a validation test string for display.

        Commands and file paths remain code-styled (backticks).
        Natural language descriptions are rendered as plain text.
        """
        stripped = test.strip()
        # Heuristic: if it looks like a command (starts with run, pytest, npm, etc.)
        # or a file path (contains / or \), use code styling
        command_prefixes = ("run ", "pytest", "npm ", "python ", "make ", "cargo ", "go ")
        lower = stripped.lower()
        is_command = any(lower.startswith(prefix) for prefix in command_prefixes)
        is_path = "/" in stripped or "\\" in stripped or stripped.endswith((".py", ".js", ".ts", ".sh"))
        if is_command or is_path:
            return f"`{stripped}`"
        return stripped

    @staticmethod
    def _name_tokens(value: str) -> set[str]:
        normalized = value.replace("\\", "/").lower()
        for separator in ("/", ".", "-", "_"):
            normalized = normalized.replace(separator, " ")
        return {
            token
            for token in normalized.split()
            if token not in {"src", "test", "tests", "spec", "py", "js", "jsx", "ts", "tsx"}
        }

    @staticmethod
    def _unique_findings(findings: list[ReviewFinding]) -> list[ReviewFinding]:
        unique: dict[tuple[str, str, tuple[str, ...]], ReviewFinding] = {}
        for finding in findings:
            key = (
                finding.section,
                " ".join((finding.title or finding.description).lower().split()),
                tuple(finding.evidence_ids),
            )
            unique.setdefault(key, finding)
        return list(unique.values())
