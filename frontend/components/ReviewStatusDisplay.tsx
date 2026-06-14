import React from "react";
import { Check, Circle, Download, LoaderCircle, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { getReviewExportUrl } from "@/lib/api";
import { STATUS_LABELS } from "@/lib/report";
import type {
  AgentProgressItem,
  ReviewProgressSnapshot,
  ReviewResponse,
  ReviewStatus
} from "@/lib/types";
import { cn } from "@/lib/utils";

type ReviewStatusDisplayProps = {
  error: string | null;
  isRunning: boolean;
  review: ReviewResponse | null;
  taskId: string | null;
};

export function ReviewStatusDisplay({ error, isRunning, review, taskId }: ReviewStatusDisplayProps) {
  const isFailed = review?.status === "failed";
  return (
    <div className="mt-5 space-y-3">
      <StatusRow label="Task" value={taskId || "Not started"} />
      <StatusRow label="Status" value={review ? STATUS_LABELS[review.status] : "Idle"} />
      {(isRunning || isFailed) && review ? <ProgressRail status={review.status} /> : null}
      {(isRunning || isFailed) && review?.progress ? <RuntimeAgentProgress progress={review.progress} /> : null}
      {isFailed ? (
        <div
          className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm font-medium text-destructive"
          data-review-status="failed"
          role="alert"
        >
          {review.error || error || "Review failed before completion."}
        </div>
      ) : error ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>
      ) : null}
      {review?.status === "completed" ? (
        <Button asChild className="w-full" variant="outline">
          <a href={getReviewExportUrl(review.task_id)}>
            <Download className="h-4 w-4" />
            Export Markdown
          </a>
        </Button>
      ) : null}
    </div>
  );
}

export function RuntimeAgentProgress({ progress }: { progress: ReviewProgressSnapshot }) {
  const currentAgent = progress.agents.find(
    (agent) => agent.agent_id === progress.current_agent_id
  );
  return (
    <section
      aria-label="Runtime agent progress"
      className="rounded-md border border-border bg-background p-3"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Current phase
          </p>
          <p className="mt-1 text-sm font-semibold">{progress.current_phase}</p>
        </div>
        <span className="rounded-full bg-muted px-2 py-1 text-xs font-medium">
          {progress.completed_agents}/{progress.total_agents} agents
        </span>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        Current agent: {currentAgent?.label || "Waiting for agent execution"}
      </p>
      <ol className="mt-3 space-y-2">
        {progress.agents.map((agent) => (
          <AgentProgressStep agent={agent} key={agent.agent_id} />
        ))}
      </ol>
    </section>
  );
}

function AgentProgressStep({ agent }: { agent: AgentProgressItem }) {
  const statusStyles = {
    pending: "border-border text-muted-foreground",
    running: "border-primary bg-primary/10 text-primary",
    completed: "border-emerald-300 bg-emerald-50 text-emerald-800",
    failed: "border-destructive/40 bg-destructive/10 text-destructive",
    skipped: "border-border bg-muted text-muted-foreground"
  };
  return (
    <li
      aria-current={agent.status === "running" ? "step" : undefined}
      className={cn(
        "flex items-center gap-2 rounded-md border px-2.5 py-2 text-xs",
        statusStyles[agent.status]
      )}
      data-agent-progress={agent.agent_id}
      data-status={agent.status}
    >
      <AgentStatusIcon status={agent.status} />
      <span className="min-w-0 flex-1 truncate font-medium">{agent.label}</span>
      <span className="capitalize">{agent.status}</span>
    </li>
  );
}

function AgentStatusIcon({ status }: { status: AgentProgressItem["status"] }) {
  if (status === "running") return <LoaderCircle className="h-3.5 w-3.5 animate-spin" />;
  if (status === "completed") return <Check className="h-3.5 w-3.5" />;
  if (status === "failed") return <X className="h-3.5 w-3.5" />;
  return <Circle className="h-3.5 w-3.5" />;
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md bg-background px-3 py-2 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="truncate font-medium">{value}</span>
    </div>
  );
}

function ProgressRail({ status }: { status: ReviewStatus }) {
  if (status === "failed") {
    return (
      <div
        aria-label="Review progress"
        className="flex items-center justify-center gap-2 rounded-sm bg-destructive px-3 py-1.5 text-xs font-medium text-destructive-foreground"
        data-status="failed"
      >
        <X className="h-3.5 w-3.5" />
        Review failed
      </div>
    );
  }

  const statuses: ReviewStatus[] = ["pending", "cloning", "parsing", "summarizing", "reviewing", "completed"];
  const activeIndex = statuses.indexOf(status);
  return (
    <div className="grid grid-cols-6 gap-1" aria-label="Review progress">
      {statuses.map((item, index) => (
        <div
          className={`h-2 rounded-sm ${index <= activeIndex ? "bg-primary" : "bg-muted"}`}
          key={item}
          title={STATUS_LABELS[item]}
        />
      ))}
    </div>
  );
}
