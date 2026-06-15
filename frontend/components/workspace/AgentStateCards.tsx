import { Activity, AlertTriangle, CheckCircle2, Database } from "lucide-react";
import React from "react";

import { EmptyState } from "@/components/workspace/EmptyState";
import type { Language } from "@/lib/i18n";
import { t } from "@/lib/i18n";
import type { ReviewAgentStateItem } from "@/lib/types";
import { cn } from "@/lib/utils";

export function AgentStateCards({ agents, language }: { agents: ReviewAgentStateItem[]; language: Language }) {
  if (!agents.length) {
    return (
      <EmptyState
        description={t(language, "agentCards.notRecordedDesc")}
        icon={Activity}
        title={t(language, "agentCards.notRecorded")}
      />
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {agents.map((agent) => (
        <article
          className="rounded-xl border border-border bg-card p-5 shadow-panel"
          data-agent-card={agent.agent_id}
          key={agent.agent_id}
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="font-mono text-xs font-semibold text-primary">A{agent.order}</p>
              <h3 className="mt-1 text-base font-semibold">{agent.agent_id}</h3>
            </div>
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold capitalize",
                agent.status === "failed"
                  ? "border-destructive/40 bg-destructive/10 text-destructive"
                  : "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300"
              )}
            >
              {agent.status === "failed" ? (
                <AlertTriangle className="h-3.5 w-3.5" />
              ) : (
                <CheckCircle2 className="h-3.5 w-3.5" />
              )}
              {t(language, `agentStatus.${agent.status}`)}
            </span>
          </div>

          <dl className="mt-5 grid grid-cols-2 gap-3">
            <Metric label={t(language, "agentCards.findings")} value={String(agent.findings_count)} />
            <Metric label={t(language, "agentCards.evidence")} value={String(agent.evidence_count)} />
            <Metric
              label={t(language, "agentCards.avgConfidence")}
              value={agent.average_confidence === null ? "n/a" : `${Math.round(agent.average_confidence * 100)}%`}
            />
            <Metric
              label={t(language, "agentCards.severity")}
              value={severitySummary(agent)}
            />
          </dl>
          {agent.error ? (
            <p className="mt-4 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
              {agent.error}
            </p>
          ) : null}
        </article>
      ))}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-panel px-3 py-2.5">
      <dt className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {label}
      </dt>
      <dd className="mt-1 font-mono text-sm font-semibold">{value}</dd>
    </div>
  );
}

function severitySummary(agent: ReviewAgentStateItem): string {
  const entries = Object.entries(agent.severity_mix).filter(([, count]) => count > 0);
  return entries.length ? entries.map(([severity, count]) => `${severity[0].toUpperCase()}${count}`).join(" ") : "none";
}
