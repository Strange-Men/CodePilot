import { Activity } from "lucide-react";
import React from "react";

import { StatusBadge } from "@/components/ui/status-badge";
import { EmptyState } from "@/components/workspace/EmptyState";
import type { Language } from "@/lib/i18n";
import { getLocalizedSeverity, t } from "@/lib/i18n";
import type { ReviewAgentStateItem } from "@/lib/types";

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
            <StatusBadge label={t(language, `agentStatus.${agent.status}`)} status={agent.status} />
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
              value={severitySummary(agent, language)}
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

function severitySummary(agent: ReviewAgentStateItem, language: Language): string {
  const entries = Object.entries(agent.severity_mix).filter(([, count]) => count > 0);
  if (!entries.length) return language === "zh" ? "无" : "none";
  return entries
    .map(([severity, count]) => `${getLocalizedSeverity(language, severity)}${count}`)
    .join(" ");
}
