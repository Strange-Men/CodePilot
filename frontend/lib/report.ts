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

export const terminalStatuses: ReviewStatus[] = ["completed", "failed"];

export type AgentContribution = {
  name: string;
  status: string;
  findingsCount: number;
  severityMix: string;
  averageConfidence?: string;
  evidenceCount: number;
};

export type AgentFinding = {
  agentName: string;
  severity: string;
  confidence?: string;
  summary: string;
  files: string[];
  evidenceIds: string[];
};

export type AgentReportDetails = {
  contributions: AgentContribution[];
  findings: AgentFinding[];
};

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

export function parseAgentReportDetails(markdown: string): AgentReportDetails {
  const sections = parseReport(markdown);
  return {
    contributions: parseAgentSummary(sections["Agent Summary"] || ""),
    findings: parseAgentFindings(sections["Agent Findings"] || "")
  };
}

function parseAgentSummary(section: string): AgentContribution[] {
  const table = findMarkdownTable(section, [
    "agent",
    "status",
    "findings",
    "severity mix",
    "avg confidence",
    "evidence"
  ]);
  if (!table) {
    return [];
  }

  return table.rows.flatMap((row) => {
    const name = cleanCell(row[table.columns.agent] || "");
    if (!isAgentName(name)) {
      return [];
    }

    const findingsCount = parseNonNegativeInteger(row[table.columns.findings]);
    const evidenceCount = parseNonNegativeInteger(row[table.columns.evidence]);
    if (findingsCount === null || evidenceCount === null) {
      return [];
    }

    const averageConfidence = optionalValue(row[table.columns["avg confidence"]]);
    return [{
      name,
      status: cleanCell(row[table.columns.status] || "unknown"),
      findingsCount,
      severityMix: cleanCell(row[table.columns["severity mix"]] || "none"),
      averageConfidence,
      evidenceCount
    }];
  });
}

function parseAgentFindings(section: string): AgentFinding[] {
  const lines = section.split("\n");
  const findings: AgentFinding[] = [];
  let agentName = "";

  for (let index = 0; index < lines.length; index += 1) {
    const heading = lines[index].match(/^#{2,6}\s+(.+?)\s*$/);
    if (heading) {
      const candidate = cleanCell(heading[1]);
      agentName = isAgentName(candidate) ? candidate : "";
      continue;
    }
    if (!agentName || !lines[index].trim().startsWith("|")) {
      continue;
    }

    const table = readMarkdownTable(lines, index);
    if (!table || !hasColumns(table.columns, ["severity", "finding", "files", "evidence"])) {
      continue;
    }

    for (const row of table.rows) {
      const summary = cleanCell(row[table.columns.finding] || "");
      if (!summary) {
        continue;
      }
      findings.push({
        agentName,
        severity: cleanCell(row[table.columns.severity] || "informational").toLowerCase(),
        confidence: table.columns.confidence === undefined
          ? undefined
          : optionalValue(row[table.columns.confidence]),
        summary,
        files: parseCommaList(row[table.columns.files]),
        evidenceIds: parseEvidenceIds(row[table.columns.evidence])
      });
    }
    index = table.endIndex;
  }

  return findings;
}

type MarkdownTable = {
  columns: Record<string, number>;
  rows: string[][];
  endIndex: number;
};

function findMarkdownTable(section: string, requiredColumns: string[]): MarkdownTable | null {
  const lines = section.split("\n");
  for (let index = 0; index < lines.length; index += 1) {
    if (!lines[index].trim().startsWith("|")) {
      continue;
    }
    const table = readMarkdownTable(lines, index);
    if (table && hasColumns(table.columns, requiredColumns)) {
      return table;
    }
  }
  return null;
}

function readMarkdownTable(lines: string[], headerIndex: number): MarkdownTable | null {
  if (headerIndex + 1 >= lines.length) {
    return null;
  }

  const headers = splitMarkdownRow(lines[headerIndex]);
  const separators = splitMarkdownRow(lines[headerIndex + 1]);
  if (
    headers.length === 0
    || headers.length !== separators.length
    || !separators.every((cell) => /^:?-{3,}:?$/.test(cell.trim()))
  ) {
    return null;
  }

  const columns = Object.fromEntries(
    headers.map((header, index) => [cleanCell(header).toLowerCase(), index])
  );
  const rows: string[][] = [];
  let endIndex = headerIndex + 1;
  for (let index = headerIndex + 2; index < lines.length; index += 1) {
    if (!lines[index].trim().startsWith("|")) {
      break;
    }
    const row = splitMarkdownRow(lines[index]);
    if (row.length !== headers.length) {
      break;
    }
    rows.push(row);
    endIndex = index;
  }

  return { columns, rows, endIndex };
}

function splitMarkdownRow(line: string): string[] {
  const trimmed = line.trim();
  if (!trimmed.startsWith("|") || !trimmed.endsWith("|")) {
    return [];
  }

  const cells: string[] = [];
  let cell = "";
  for (let index = 1; index < trimmed.length - 1; index += 1) {
    const character = trimmed[index];
    if (character === "\\" && trimmed[index + 1] === "|") {
      cell += "|";
      index += 1;
    } else if (character === "|") {
      cells.push(cell.trim());
      cell = "";
    } else {
      cell += character;
    }
  }
  cells.push(cell.trim());
  return cells;
}

function hasColumns(columns: Record<string, number>, requiredColumns: string[]): boolean {
  return requiredColumns.every((column) => columns[column] !== undefined);
}

function cleanCell(value: string): string {
  return value
    .replace(/`([^`]*)`/g, "$1")
    .replace(/\*\*([^*]*)\*\*/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
}

function isAgentName(value: string): boolean {
  return /^[A-Za-z][A-Za-z0-9]*Agent$/.test(value) && value.length <= 64;
}

function parseNonNegativeInteger(value: string | undefined): number | null {
  const normalized = cleanCell(value || "");
  return /^\d+$/.test(normalized) ? Number(normalized) : null;
}

function optionalValue(value: string | undefined): string | undefined {
  const normalized = cleanCell(value || "");
  return normalized && !/^(n\/a|none|not available)$/i.test(normalized)
    ? normalized
    : undefined;
}

function parseCommaList(value: string | undefined): string[] {
  return cleanCell(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item && !/^(none|n\/a|none detected)$/i.test(item))
    .slice(0, 6);
}

function parseEvidenceIds(value: string | undefined): string[] {
  return parseCommaList(value)
    .filter((item) => /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$/.test(item))
    .slice(0, 6);
}
