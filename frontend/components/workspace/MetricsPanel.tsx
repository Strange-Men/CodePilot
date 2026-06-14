import { Activity, BarChart3, Database, ShieldAlert } from "lucide-react";
import React from "react";

import { EmptyState } from "@/components/workspace/EmptyState";
import type { ReviewAgentStateItem, ReviewFindingItem } from "@/lib/types";

type MetricsPanelProps = {
  agents: ReviewAgentStateItem[];
  findings: ReviewFindingItem[];
};

export function MetricsPanel({ agents, findings }: MetricsPanelProps) {
  if (!agents.length && !findings.length) {
    return (
      <EmptyState
        description="Structured metrics are unavailable for this legacy review. Use the Report tab for the original analysis."
        icon={BarChart3}
        title="Metrics are not recorded"
      />
    );
  }

  const evidenceCount = new Set(findings.flatMap((finding) => finding.evidence_ids)).size;
  const averageConfidence = findings.length
    ? findings.reduce((sum, finding) => sum + finding.confidence, 0) / findings.length
    : 0;
  const highRisk = findings.filter((finding) =>
    ["critical", "high"].includes(finding.severity.toLowerCase())
  ).length;
  const severity = severityCounts(findings);

  return (
    <div className="space-y-5" data-structured-metrics>
      <div>
        <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-primary">
          Review telemetry
        </p>
        <h2 className="mt-1 text-xl font-semibold tracking-tight">Metrics</h2>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard icon={ShieldAlert} label="Findings" value={String(findings.length)} />
        <MetricCard icon={Database} label="Evidence refs" value={String(evidenceCount)} />
        <MetricCard icon={Activity} label="Agent records" value={String(agents.length)} />
        <MetricCard
          icon={BarChart3}
          label="Avg confidence"
          value={findings.length ? `${Math.round(averageConfidence * 100)}%` : "n/a"}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <section className="rounded-xl border border-border bg-card p-5 shadow-panel">
          <h3 className="text-sm font-semibold">Severity distribution</h3>
          <div className="mt-5 space-y-4">
            {Object.entries(severity).map(([label, count]) => (
              <div key={label}>
                <div className="flex items-center justify-between text-xs">
                  <span className="capitalize text-muted-foreground">{label}</span>
                  <span className="font-mono font-semibold">{count}</span>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
                  <div
                    className={`h-full rounded-full ${severityBars[label]}`}
                    style={{ width: `${findings.length ? Math.max(4, (count / findings.length) * 100) : 0}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>
        <section className="rounded-xl border border-border bg-card p-5 shadow-panel">
          <h3 className="text-sm font-semibold">Risk signal</h3>
          <p className="mt-4 font-mono text-4xl font-semibold tracking-tight">{highRisk}</p>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Critical or high severity findings that should be triaged before routine cleanup.
          </p>
        </section>
      </div>
    </div>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value
}: {
  icon: typeof Activity;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-panel">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
        <Icon className="h-4 w-4 text-primary" />
      </div>
      <p className="mt-4 font-mono text-2xl font-semibold">{value}</p>
    </div>
  );
}

function severityCounts(findings: ReviewFindingItem[]): Record<string, number> {
  const counts = { critical: 0, high: 0, medium: 0, low: 0 };
  for (const finding of findings) {
    const severity = finding.severity.toLowerCase() as keyof typeof counts;
    if (severity in counts) counts[severity] += 1;
  }
  return counts;
}

const severityBars: Record<string, string> = {
  critical: "bg-red-500",
  high: "bg-orange-500",
  medium: "bg-amber-400",
  low: "bg-sky-500"
};
