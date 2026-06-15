import type { ReviewStatus } from "@/lib/types";

import reportContract from "../../contracts/report_sections.json";

export const STATUS_LABELS: Record<ReviewStatus, string> = {
  pending: "Pending",
  cloning: "Cloning",
  parsing: "Parsing",
  summarizing: "Summarizing",
  reviewing: "Reviewing",
  completed: "Completed",
  failed: "Failed"
};

export const orderedSections = reportContract.sections.map((section) => section.title);
export const repositoryMetricsSection = "Repository Metrics";
export const architectureGraphSection = "Architecture Graph";
export const repositoryInsightsSection = "Repository Insights";
export const reportOverviewSections = [
  "Executive Summary",
  "What This Repository Is",
  "How It Works",
  "Key Architecture Map",
  "Agent Summary",
  "Agent Findings"
];
export const reportClosingSections = [
  "Action Plan",
  "Evidence Appendix"
];
export const legacyReportAppendixSections = [
  repositoryInsightsSection,
  repositoryMetricsSection,
  architectureGraphSection
];

// Chinese heading equivalents for report parsing
const zhHeadingMap: Record<string, string> = {
  "执行摘要": "Executive Summary",
  "主要风险": "Top Risks",
  "仓库概览": "What This Repository Is",
  "工作方式": "How It Works",
  "架构地图": "Key Architecture Map",
  "循环依赖组": "Cycle Groups",
  "Agent 总结": "Agent Summary",
  "Agent 问题发现": "Agent Findings",
  "架构总结": "Architecture Summary",
  "代码坏味道": "Code Smells",
  "可维护性问题": "Maintainability Issues",
  "重构建议": "Refactoring Suggestions",
  "行动计划": "Action Plan",
  "证据附录": "Evidence Appendix",
  "仓库指标": "Repository Metrics",
  "差异审查范围": "Diff Review Scope",
};

export const terminalStatuses: ReviewStatus[] = ["completed", "failed"];

export function parseReport(markdown: string): Record<string, string> {
  const sections: Record<string, string> = {};
  let current = "";
  const recognizedSections = [
    ...reportOverviewSections,
    ...orderedSections,
    ...reportClosingSections,
    ...legacyReportAppendixSections
  ];

  for (const line of markdown.split("\n")) {
    const heading = line.replace(/^#+\s*/, "").trim();
    // Check if it's a recognized English heading or a Chinese heading
    const canonicalHeading = zhHeadingMap[heading] || heading;
    if (recognizedSections.includes(canonicalHeading)) {
      // Use the original heading text as the key so Chinese reports
      // display Chinese headings in the sidebar and section titles
      current = heading;
      sections[current] = "";
      continue;
    }
    if (current) {
      sections[current] = `${sections[current]}${line}\n`;
    }
  }

  return sections;
}

/** Check if a heading (English or Chinese) is a de-emphasized section. */
export function isDeEmphasizedSection(heading: string): boolean {
  const deEmphasized = new Set([
    ...legacyReportAppendixSections,
    "Evidence Appendix",
    architectureGraphSection
  ]);
  // Check both the heading itself and its canonical English name
  const canonical = zhHeadingMap[heading] || heading;
  return deEmphasized.has(heading) || deEmphasized.has(canonical);
}
