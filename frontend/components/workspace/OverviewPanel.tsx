import { CheckCircle2, Clock3, GitBranch, ShieldAlert } from "lucide-react";
import React from "react";

import { Card } from "@/components/ui/card";
import { AgentTimeline } from "@/components/workspace/AgentTimeline";
import { EmptyState } from "@/components/workspace/EmptyState";
import { STATUS_LABELS } from "@/lib/report";
import type { ReviewAgentStateItem, ReviewFindingItem, ReviewResponse } from "@/lib/types";

type OverviewPanelProps = {
  agents: ReviewAgentStateItem[];
  findings: ReviewFindingItem[];
  review: ReviewResponse | null;
};

export function OverviewPanel({ agents, findings, review }: OverviewPanelProps) {
  if (!review) {
    return (
      <EmptyState
        description="Import a public GitHub repository from the control panel. CodePilot will map the repository, run four review agents, and assemble an evidence-grounded report."
        icon={GitBranch}
        title="Start a repository review"
      />
    );
  }

  const evidenceCount = new Set(findings.flatMap((finding) => finding.evidence_ids)).size;
  const completedAgents = review.progress?.completed_agents
    ?? agents.filter((agent) => agent.status === "completed").length;
  const highRisk = findings.filter((finding) =>
    ["critical", "high"].includes(finding.severity.toLowerCase())
  ).length;

  return (
    <div className="space-y-5">
      <section className="overflow-hidden rounded-xl border border-border bg-card shadow-panel">
        <div className="relative p-5 sm:p-6">
          <div className="workspace-grid pointer-events-none absolute inset-0 opacity-50" />
          <div className="relative">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-primary">
                  Current review
                </p>
                <h2 className="mt-2 break-all text-xl font-semibold tracking-tight sm:text-2xl">
                  {repositoryName(review.repo_url)}
                </h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                  {overviewMessage(review)}
                </p>
              </div>
              <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card/90 px-3 py-1.5 text-xs font-semibold">
                <span className={`h-2 w-2 rounded-full ${statusDot(review.status)}`} />
                {STATUS_LABELS[review.status]}
              </span>
            </div>
          </div>
        </div>
      </section>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryCard icon={CheckCircle2} label="Agents complete" value={`${completedAgents}/4`} />
        <SummaryCard icon={ShieldAlert} label="Findings" value={String(findings.length)} />
        <SummaryCard icon={Clock3} label="High-risk items" value={String(highRisk)} />
        <SummaryCard icon={GitBranch} label="Evidence refs" value={String(evidenceCount)} />
      </div>

      <Card className="p-5 sm:p-6">
        <AgentTimeline agents={agents} progress={review.progress} />
      </Card>

      {review.status === "failed" ? (
        <div className="rounded-xl border border-destructive/40 bg-destructive/5 p-5" role="alert">
          <p className="font-semibold text-destructive">Review interrupted</p>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {review.error || "The review stopped before completion. Start a new review after checking the repository and provider configuration."}
          </p>
        </div>
      ) : null}
    </div>
  );
}

function SummaryCard({
  icon: Icon,
  label,
  value
}: {
  icon: typeof CheckCircle2;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-panel">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
        <Icon className="h-4 w-4 text-primary" />
      </div>
      <p className="mt-3 font-mono text-2xl font-semibold">{value}</p>
    </div>
  );
}

function repositoryName(repoUrl: string): string {
  try {
    return new URL(repoUrl).pathname.split("/").filter(Boolean).slice(0, 2).join("/") || repoUrl;
  } catch {
    return repoUrl;
  }
}

function overviewMessage(review: ReviewResponse): string {
  if (review.status === "completed") {
    return "Review complete. Structured agent, finding, evidence, and metric data is ready across the workspace tabs.";
  }
  if (review.status === "failed") {
    return "The latest execution did not complete. Persisted progress remains visible for diagnosis.";
  }
  return review.progress?.current_phase || "Preparing the review pipeline.";
}

function statusDot(status: ReviewResponse["status"]): string {
  if (status === "completed") return "bg-emerald-500";
  if (status === "failed") return "bg-destructive";
  return "animate-pulse bg-primary";
}
