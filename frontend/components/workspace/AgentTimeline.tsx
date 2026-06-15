import { Check, Circle, LoaderCircle, Minus, X } from "lucide-react";
import React from "react";

import type { Language } from "@/lib/i18n";
import { t } from "@/lib/i18n";
import type {
  AgentProgressItem,
  AgentProgressStatus,
  ReviewAgentStateItem,
  ReviewProgressSnapshot
} from "@/lib/types";
import { cn } from "@/lib/utils";

const plannedAgents = [
  { agent_id: "ArchitectureAgent", label: "A1 ArchitectureAgent", order: 1 },
  { agent_id: "CodeSmellAgent", label: "A2 CodeSmellAgent", order: 2 },
  { agent_id: "MaintainabilityAgent", label: "A3 MaintainabilityAgent", order: 3 },
  { agent_id: "RefactorAgent", label: "A4 RefactorAgent", order: 4 }
];

type AgentTimelineProps = {
  agents: ReviewAgentStateItem[];
  language: Language;
  loading?: boolean;
  progress?: ReviewProgressSnapshot | null;
};

const agentDescKeys: Record<string, string> = {
  ArchitectureAgent: "架构分析",
  CodeSmellAgent: "代码坏味道",
  MaintainabilityAgent: "可维护性",
  RefactorAgent: "重构建议"
};

export function AgentTimeline({ agents, language, loading, progress }: AgentTimelineProps) {
  const steps = timelineSteps(agents, progress);
  const showSkeleton = loading && !agents.length && !progress;

  return (
    <section aria-labelledby="agent-timeline-title">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-primary">
            {t(language, "timeline.executionPipeline")}
          </p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight" id="agent-timeline-title">
            {t(language, "timeline.reviewAgents")}
          </h2>
        </div>
        {progress ? (
          <span className="font-mono text-xs text-muted-foreground">
            {progress.completed_agents}/{progress.total_agents} {t(language, "timeline.complete")}
          </span>
        ) : null}
      </div>

      {showSkeleton ? (
        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4" role="status">
          {Array.from({ length: 4 }, (_, index) => (
            <div className="skeleton h-32 rounded-xl" key={index} />
          ))}
          <span className="sr-only">{t(language, "tabs.loadingAgentStates")}</span>
        </div>
      ) : (
        <ol
          aria-label={t(language, "timeline.reviewAgents")}
          className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4"
        >
          {steps.map((agent, index) => (
            <li
              aria-current={agent.status === "running" ? "step" : undefined}
              className={cn(
                "relative min-h-32 rounded-xl border bg-card p-4 transition-colors duration-200",
                statusStyles[agent.status]
              )}
              data-agent-step={agent.agent_id}
              data-status={agent.status}
              key={agent.agent_id}
            >
              {index < steps.length - 1 ? (
                <span
                  aria-hidden="true"
                  className="absolute -right-3 top-7 hidden h-px w-3 bg-border xl:block"
                />
              ) : null}
              <div className="flex items-start justify-between gap-3">
                <span className="font-mono text-xs font-semibold text-muted-foreground">
                  A{agent.order}
                </span>
                <StatusIcon status={agent.status} />
              </div>
              <p className="mt-5 break-words text-sm font-semibold">{agent.agent_id}</p>
              {language === "zh" ? (
                <p className="mt-0.5 text-xs text-muted-foreground">{agentDescKeys[agent.agent_id] || agent.agent_id}</p>
              ) : null}
              <div className="mt-2 flex items-center justify-between gap-2">
                <span className="text-xs capitalize text-muted-foreground">{t(language, `agentStatus.${agent.status}`)}</span>
                {agent.findings_count !== null ? (
                  <span className="font-mono text-xs text-muted-foreground">
                    {agent.findings_count} {t(language, "timeline.findings")}
                  </span>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

const statusStyles: Record<AgentProgressStatus, string> = {
  pending: "border-border text-foreground",
  running: "border-primary/60 bg-primary/5 shadow-[0_0_0_1px_hsl(var(--primary)/0.12)]",
  completed: "border-emerald-300/70 bg-emerald-50/70 dark:border-emerald-800 dark:bg-emerald-950/30",
  failed: "border-destructive/60 bg-destructive/5",
  skipped: "border-border bg-muted/40 text-muted-foreground"
};

function StatusIcon({ status }: { status: AgentProgressStatus }) {
  const base = "h-5 w-5";
  if (status === "running") {
    return (
      <span className="relative flex h-8 w-8 items-center justify-center rounded-full bg-primary/15 text-primary">
        <span className="absolute inset-0 animate-pulse rounded-full border border-primary/40" />
        <LoaderCircle className={cn(base, "animate-spin")} />
      </span>
    );
  }
  if (status === "completed") {
    return <Check className={cn(base, "text-emerald-600 dark:text-emerald-400")} />;
  }
  if (status === "failed") return <X className={cn(base, "text-destructive")} />;
  if (status === "skipped") return <Minus className={cn(base, "text-muted-foreground")} />;
  return <Circle className={cn(base, "text-muted-foreground")} />;
}

function timelineSteps(
  agents: ReviewAgentStateItem[],
  progress?: ReviewProgressSnapshot | null
): AgentProgressItem[] {
  if (progress?.agents.length) return [...progress.agents].sort((left, right) => left.order - right.order);

  if (agents.length) {
    const byId = new Map(agents.map((agent) => [agent.agent_id, agent]));
    return plannedAgents.map((planned) => {
      const persisted = byId.get(planned.agent_id);
      return {
        ...planned,
        status: normalizeStatus(persisted?.status),
        findings_count: persisted?.findings_count ?? null,
        evidence_count: persisted?.evidence_count ?? null,
        error: persisted?.error ?? null
      };
    });
  }

  return plannedAgents.map((agent) => ({
    ...agent,
    status: "pending",
    findings_count: null,
    evidence_count: null,
    error: null
  }));
}

function normalizeStatus(status?: string): AgentProgressStatus {
  return ["pending", "running", "completed", "failed", "skipped"].includes(status || "")
    ? status as AgentProgressStatus
    : "skipped";
}
