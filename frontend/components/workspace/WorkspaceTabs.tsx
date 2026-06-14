"use client";

import {
  BarChart3,
  Bot,
  FileSearch,
  FileText,
  LayoutDashboard,
  ShieldAlert
} from "lucide-react";
import type { KeyboardEvent } from "react";
import React from "react";

import { AgentStateCards } from "@/components/workspace/AgentStateCards";
import { AgentTimeline } from "@/components/workspace/AgentTimeline";
import { EmptyState } from "@/components/workspace/EmptyState";
import { EvidencePanel } from "@/components/workspace/EvidencePanel";
import { FindingsPanel } from "@/components/workspace/FindingsPanel";
import { MetricsPanel } from "@/components/workspace/MetricsPanel";
import { OverviewPanel } from "@/components/workspace/OverviewPanel";
import { ReportPanel } from "@/components/workspace/ReportPanel";
import type { ReviewAgentStateItem, ReviewFindingItem, ReviewResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

export type WorkspaceTab = "overview" | "agents" | "findings" | "report" | "evidence" | "metrics";

type WorkspaceTabsProps = {
  activeTab: WorkspaceTab;
  agents: ReviewAgentStateItem[];
  findings: ReviewFindingItem[];
  isRunning: boolean;
  onRetryStructuredData: () => void;
  onTabChange: (tab: WorkspaceTab) => void;
  review: ReviewResponse | null;
  structuredError: string | null;
  structuredLoading: boolean;
};

const tabs = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "agents", label: "Agents", icon: Bot },
  { id: "findings", label: "Findings", icon: ShieldAlert },
  { id: "report", label: "Report", icon: FileText },
  { id: "evidence", label: "Evidence", icon: FileSearch },
  { id: "metrics", label: "Metrics", icon: BarChart3 }
] satisfies { id: WorkspaceTab; label: string; icon: typeof LayoutDashboard }[];

export function WorkspaceTabs({
  activeTab,
  agents,
  findings,
  isRunning,
  onRetryStructuredData,
  onTabChange,
  review,
  structuredError,
  structuredLoading
}: WorkspaceTabsProps) {
  function handleKeys(event: KeyboardEvent<HTMLButtonElement>, currentIndex: number) {
    if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    let nextIndex = currentIndex;
    if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = tabs.length - 1;
    onTabChange(tabs[nextIndex].id);
    document.getElementById(`workspace-tab-${tabs[nextIndex].id}`)?.focus();
  }

  return (
    <section className="min-w-0">
      <div
        aria-label="Review workspace sections"
        className="grid grid-cols-3 gap-1 rounded-xl border border-border bg-card p-1 shadow-panel sm:grid-cols-6"
        role="tablist"
      >
        {tabs.map((tab, index) => {
          const Icon = tab.icon;
          return (
            <button
              aria-controls={`workspace-panel-${tab.id}`}
              aria-selected={activeTab === tab.id}
              className={cn(
                "flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-lg px-2 text-xs font-semibold transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                activeTab === tab.id
                  ? "bg-foreground text-background shadow-sm"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
              id={`workspace-tab-${tab.id}`}
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              onKeyDown={(event) => handleKeys(event, index)}
              role="tab"
              tabIndex={activeTab === tab.id ? 0 : -1}
              type="button"
            >
              <Icon className="h-4 w-4" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      <div
        aria-labelledby={`workspace-tab-${activeTab}`}
        className="mt-5"
        id={`workspace-panel-${activeTab}`}
        role="tabpanel"
      >
        {renderPanel({
          activeTab,
          agents,
          findings,
          isRunning,
          onRetryStructuredData,
          review,
          structuredError,
          structuredLoading
        })}
      </div>
    </section>
  );
}

function renderPanel({
  activeTab,
  agents,
  findings,
  isRunning,
  onRetryStructuredData,
  review,
  structuredError,
  structuredLoading
}: Omit<WorkspaceTabsProps, "onTabChange">) {
  if (activeTab === "overview") {
    return <OverviewPanel agents={agents} findings={findings} review={review} />;
  }
  if (!review) {
    return (
      <EmptyState
        description="Start or select a review to populate this workspace section."
        icon={tabs.find((tab) => tab.id === activeTab)?.icon || LayoutDashboard}
        title="No review selected"
      />
    );
  }
  if (activeTab === "agents") {
    return (
      <div className="space-y-5">
        <div className="rounded-xl border border-border bg-card p-5 shadow-panel sm:p-6">
          <AgentTimeline agents={agents} progress={review.progress} />
        </div>
        {isRunning ? (
          <EmptyState
            description="Persisted counts, confidence, and severity summaries become available after the agent pipeline completes."
            icon={Bot}
            title="Agent summaries are still processing"
          />
        ) : structuredLoading ? (
          <div className="grid gap-4 lg:grid-cols-2" role="status">
            {Array.from({ length: 4 }, (_, index) => (
              <div className="skeleton h-56 rounded-xl" key={index} />
            ))}
            <span className="sr-only">Loading persisted agent states</span>
          </div>
        ) : structuredError ? (
          <EmptyState
            actionLabel="Retry agent states"
            description={structuredError}
            icon={Bot}
            onAction={onRetryStructuredData}
            title="Agent summaries could not be loaded"
          />
        ) : (
          <AgentStateCards agents={agents} />
        )}
      </div>
    );
  }
  if (activeTab === "findings") {
    if (isRunning) {
      return (
        <EmptyState
          description="Findings appear here after the agents finish validation and the review reaches a terminal state."
          icon={ShieldAlert}
          title="Findings are being validated"
        />
      );
    }
    return (
      <FindingsPanel
        error={structuredError}
        findings={findings}
        loading={structuredLoading}
        onRetry={onRetryStructuredData}
      />
    );
  }
  if (activeTab === "report") {
    return <ReportPanel isRunning={isRunning} reportMarkdown={review?.report_markdown} />;
  }
  if (activeTab === "evidence") {
    if (isRunning) {
      return (
        <EmptyState
          description="Validated file, symbol, and line references appear after the review completes."
          icon={FileSearch}
          title="Evidence is being collected"
        />
      );
    }
    return (
      <EvidencePanel
        error={structuredError}
        findings={findings}
        loading={structuredLoading}
        onRetry={onRetryStructuredData}
      />
    );
  }
  if (isRunning) {
    return (
      <EmptyState
        description="Review metrics finalize when structured findings and persisted agent states are available."
        icon={BarChart3}
        title="Metrics are still processing"
      />
    );
  }
  if (structuredLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" role="status">
        {Array.from({ length: 4 }, (_, index) => (
          <div className="skeleton h-28 rounded-xl" key={index} />
        ))}
        <span className="sr-only">Loading review metrics</span>
      </div>
    );
  }
  if (structuredError) {
    return (
      <EmptyState
        actionLabel="Retry metrics"
        description={structuredError}
        icon={BarChart3}
        onAction={onRetryStructuredData}
        title="Metrics could not be loaded"
      />
    );
  }
  return <MetricsPanel agents={agents} findings={findings} />;
}
