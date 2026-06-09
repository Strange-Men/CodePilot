from __future__ import annotations

from collections import Counter

from backend.core.report_contract import REPORT_SECTIONS
from backend.models.context import EvidenceRecord, ReviewContext
from backend.models.structured_review import ReviewFinding, StructuredReviewDraft
from backend.reviewers.markdown_adapter import DEFAULT_SECTION_CONTENT, MarkdownReviewAdapter

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
    ) -> str:
        findings = self._unique_findings(draft.findings if draft is not None else [])
        sections = [
            self._executive_summary(context, findings),
            self._repository_identity(context),
            self._how_it_works(context),
            self._architecture_map(context),
            self._agent_findings_overview(findings),
            self._contract_sections(findings),
            self._action_plan(findings),
            self._evidence_appendix(context, findings),
        ]
        return "\n\n".join(section for section in sections if section).rstrip() + "\n"

    def _executive_summary(
        self,
        context: ReviewContext,
        findings: list[ReviewFinding],
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
            lines.extend(self._compact_finding_line(finding) for finding in top_risks)
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
                MarkdownReviewAdapter._format_cycle_group(cycle)
                for cycle in context.circular_dependencies[:5]
                if cycle
            )
        return "\n".join(lines)

    @staticmethod
    def _agent_findings_overview(findings: list[ReviewFinding]) -> str:
        lines = [
            "# Agent Findings",
            (
                "Validated structured findings are summarized below. Detailed descriptions remain in the four "
                "compatible report sections."
            ),
        ]
        if not findings:
            lines.append("- No validated finding was produced.")
            return "\n".join(lines)
        lines.extend(HumanReadableReportComposer._compact_finding_line(finding) for finding in findings[:12])
        return "\n".join(lines)

    @staticmethod
    def _contract_sections(findings: list[ReviewFinding]) -> str:
        rendered: list[str] = []
        for section in REPORT_SECTIONS:
            section_findings = [finding for finding in findings if finding.section == section]
            body = "\n\n".join(finding.to_markdown() for finding in section_findings)
            rendered.append(f"# {section}\n{body or DEFAULT_SECTION_CONTENT}")
        return "\n\n".join(rendered)

    def _action_plan(self, findings: list[ReviewFinding]) -> str:
        actionable = [finding for finding in self._ranked_findings(findings) if finding.recommendation]
        lines = ["# Action Plan"]
        if not actionable:
            lines.append(
                "No evidence-grounded action is recommended yet. Gather targeted evidence before changing boundaries."
            )
            return "\n".join(lines)
        for index, finding in enumerate(actionable[:5], start=1):
            files = self._path_list(finding.files, 4)
            evidence = ", ".join(f"`{evidence_id}`" for evidence_id in finding.evidence_ids[:3])
            lines.extend(
                [
                    f"## {index}. {finding.title or finding.category or 'Repository finding'}",
                    f"- **Why it matters:** {finding.description.strip()}",
                    f"- **First step:** {finding.recommendation.strip()}",
                    f"- **Where:** {files}",
                    f"- **Evidence:** {evidence or 'No validated evidence reference.'}",
                    f"- **Validation hint:** Run focused tests for {files} before and after the change.",
                ]
            )
        return "\n".join(lines)

    @staticmethod
    def _evidence_appendix(
        context: ReviewContext,
        findings: list[ReviewFinding],
    ) -> str:
        used_ids = {
            evidence_id
            for finding in findings
            for evidence_id in finding.evidence_ids
        }
        records = [
            record
            for record in context.evidence
            if record.evidence_id in used_ids
        ]
        lines = [
            "# Evidence Appendix",
            "Only validated references are shown. Source snippets are intentionally omitted.",
            "",
            "| Evidence ID | Location | Kind | Symbols |",
            "| --- | --- | --- | --- |",
        ]
        if not records:
            lines.append("| None | No validated evidence was cited | n/a | n/a |")
        else:
            lines.extend(HumanReadableReportComposer._evidence_row(record) for record in records[:30])
        lines.extend(
            [
                "",
                "## Repository Metrics",
                f"- Supported source files: {context.total_source_files}",
                f"- Analyzed files: {context.analyzed_files}",
                f"- Skipped files: {context.skipped_files}",
                f"- Total lines: {context.total_lines}",
                f"- Average complexity estimate: {context.avg_complexity:.2f}",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _evidence_row(record: EvidenceRecord) -> str:
        location = f"`{record.file_path}:{record.start_line}-{record.end_line}`"
        symbols = ", ".join(f"`{symbol}`" for symbol in record.symbols[:5]) or "n/a"
        return f"| `{record.evidence_id}` | {location} | {record.kind} | {symbols} |"

    @staticmethod
    def _ranked_findings(findings: list[ReviewFinding]) -> list[ReviewFinding]:
        return sorted(
            findings,
            key=lambda finding: (
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
    def _compact_finding_line(finding: ReviewFinding) -> str:
        title = finding.title or finding.description
        files = HumanReadableReportComposer._path_list(finding.files, 3)
        evidence = ", ".join(f"`{item}`" for item in finding.evidence_ids[:2]) or "none"
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
