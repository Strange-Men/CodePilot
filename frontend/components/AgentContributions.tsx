import React from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type AgentContribution,
  type AgentFinding,
  parseAgentReportDetails
} from "@/lib/report";
import { cn } from "@/lib/utils";

type AgentContributionsProps = {
  reportMarkdown: string;
};

const preferredAgentOrder = [
  "ArchitectureAgent",
  "CodeSmellAgent",
  "MaintainabilityAgent",
  "RefactorAgent"
];

const severityStyles: Record<string, string> = {
  critical: "border-red-300 bg-red-50 text-red-800",
  high: "border-orange-300 bg-orange-50 text-orange-800",
  medium: "border-amber-300 bg-amber-50 text-amber-800",
  low: "border-sky-300 bg-sky-50 text-sky-800",
  informational: "border-slate-300 bg-slate-50 text-slate-700"
};

export function AgentContributions({ reportMarkdown }: AgentContributionsProps) {
  const details = parseAgentReportDetails(reportMarkdown);
  const contributions = sortByAgent(details.contributions);
  const groupedFindings = groupFindings(details.findings);

  return (
    <>
      <Card aria-labelledby="agent-contribution-title">
        <CardHeader>
          <CardTitle id="agent-contribution-title">Agent Contribution</CardTitle>
          <p className="text-sm text-muted-foreground">
            Evidence-grounded work completed by each review specialist.
          </p>
        </CardHeader>
        <CardContent>
          {contributions.length ? (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              {contributions.map((agent) => (
                <AgentCard agent={agent} key={agent.name} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Agent details are not available for this review.
            </p>
          )}
        </CardContent>
      </Card>

      <Card aria-labelledby="agent-findings-title">
        <CardHeader>
          <CardTitle id="agent-findings-title">Agent Findings</CardTitle>
        </CardHeader>
        <CardContent>
          {groupedFindings.length ? (
            <div className="space-y-5">
              {groupedFindings.map(([agentName, findings]) => (
                <section
                  aria-labelledby={`agent-findings-${agentName.toLowerCase()}`}
                  data-agent-findings-group={agentName}
                  key={agentName}
                >
                  <h3
                    className="mb-2 text-sm font-semibold"
                    id={`agent-findings-${agentName.toLowerCase()}`}
                  >
                    {agentName}
                  </h3>
                  <div className="space-y-2">
                    {findings.map((finding, index) => (
                      <FindingRow finding={finding} key={`${agentName}-${index}`} />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No grouped agent findings are available for this review.
            </p>
          )}
        </CardContent>
      </Card>
    </>
  );
}

function AgentCard({ agent }: { agent: AgentContribution }) {
  return (
    <div
      className="rounded-md border border-border bg-background p-3"
      data-agent-card={agent.name}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="break-words text-sm font-semibold">{agent.name}</h3>
        <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
          {agent.status}
        </span>
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
        <Metric label="Findings" value={String(agent.findingsCount)} />
        <Metric label="Evidence" value={String(agent.evidenceCount)} />
        <Metric label="Severity mix" value={agent.severityMix} wide />
        <Metric label="Avg confidence" value={agent.averageConfidence || "n/a"} wide />
      </dl>
    </div>
  );
}

function Metric({ label, value, wide = false }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={wide ? "col-span-2" : undefined}>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 break-words font-medium text-foreground">{value}</dd>
    </div>
  );
}

function FindingRow({ finding }: { finding: AgentFinding }) {
  return (
    <article className="rounded-md border border-border bg-background p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={cn(
            "rounded-full border px-2 py-0.5 text-xs font-semibold uppercase",
            severityStyles[finding.severity] || severityStyles.informational
          )}
        >
          {finding.severity}
        </span>
        {finding.confidence ? (
          <span className="text-xs text-muted-foreground">
            Confidence {finding.confidence}
          </span>
        ) : null}
      </div>
      <p className="mt-2 font-medium">{finding.summary}</p>
      {finding.files.length ? (
        <p className="mt-2 break-words text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Affected files:</span>{" "}
          {finding.files.join(", ")}
        </p>
      ) : null}
      {finding.evidenceIds.length ? (
        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
          <span className="font-medium">Evidence:</span>
          {finding.evidenceIds.map((evidenceId) => (
            <code
              className="rounded border border-primary/30 bg-primary/10 px-1.5 py-0.5 font-semibold text-primary"
              key={evidenceId}
            >
              {evidenceId}
            </code>
          ))}
        </div>
      ) : null}
    </article>
  );
}

function sortByAgent<T extends { name: string }>(agents: T[]): T[] {
  return [...agents].sort((left, right) => agentRank(left.name) - agentRank(right.name));
}

function groupFindings(findings: AgentFinding[]): [string, AgentFinding[]][] {
  const groups = new Map<string, AgentFinding[]>();
  for (const finding of findings) {
    groups.set(finding.agentName, [...(groups.get(finding.agentName) || []), finding]);
  }
  return [...groups.entries()].sort(
    ([left], [right]) => agentRank(left) - agentRank(right)
  );
}

function agentRank(agentName: string): number {
  const index = preferredAgentOrder.indexOf(agentName);
  return index === -1 ? preferredAgentOrder.length : index;
}
