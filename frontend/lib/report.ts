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

export const terminalStatuses: ReviewStatus[] = ["completed", "failed"];

export function parseReport(markdown: string): Record<string, string> {
  const sections: Record<string, string> = {};
  let current = "";
  const recognizedSections = [...orderedSections, repositoryMetricsSection];

  for (const line of markdown.split("\n")) {
    const heading = line.replace(/^#+\s*/, "").trim();
    if (recognizedSections.includes(heading)) {
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
