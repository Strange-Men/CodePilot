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
import type { Language } from "@/lib/i18n";
import { t } from "@/lib/i18n";
import type { ReviewAgentStateItem, ReviewFindingItem, ReviewResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

export type WorkspaceTab = "overview" | "agents" | "findings" | "report" | "evidence" | "metrics";

type WorkspaceTabsProps = {
  activeTab: WorkspaceTab;
  agents: ReviewAgentStateItem[];
  findings: ReviewFindingItem[];
  isRunning: boolean;
  language: Language;
  onRetryStructuredData: () => void;
  onTabChange: (tab: WorkspaceTab) => void;
  review: ReviewResponse | null;
  structuredError: string | null;
  structuredLoading: boolean;
};

const tabConfigs = [
  { id: "overview" as WorkspaceTab, key: "tabs.overview", icon: LayoutDashboard },
  { id: "agents" as WorkspaceTab, key: "tabs.agents", icon: Bot },
  { id: "findings" as WorkspaceTab, key: "tabs.findings", icon: ShieldAlert },
  { id: "report" as WorkspaceTab, key: "tabs.report", icon: FileText },
  { id: "evidence" as WorkspaceTab, key: "tabs.evidence", icon: FileSearch },
  { id: "metrics" as WorkspaceTab, key: "tabs.metrics", icon: BarChart3 }
];

export function WorkspaceTabs({
  activeTab,
  agents,
  findings,
  isRunning,
  language,
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
    if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabConfigs.length) % tabConfigs.length;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabConfigs.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = tabConfigs.length - 1;
    onTabChange(tabConfigs[nextIndex].id);
    document.getElementById(`workspace-tab-${tabConfigs[nextIndex].id}`)?.focus();
  }

  return (
    <section className="min-w-0">
      <div
        aria-label={t(language, "tabs.workspaceSections")}
        className="grid grid-cols-3 gap-1 rounded-xl border border-border bg-card p-1 shadow-panel sm:grid-cols-6"
        role="tablist"
      >
        {tabConfigs.map((tab, index) => {
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
              <span>{t(language, tab.key)}</span>
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
          language,
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
  language,
  onRetryStructuredData,
  review,
  structuredError,
  structuredLoading
}: Omit<WorkspaceTabsProps, "onTabChange">) {
  if (activeTab === "overview") {
    return <OverviewPanel agents={agents} findings={findings} language={language} review={review} />;
  }
  if (!review) {
    return (
      <EmptyState
        description={t(language, "tabs.noReviewDescription")}
        icon={tabConfigs.find((tab) => tab.id === activeTab)?.icon || LayoutDashboard}
        title={t(language, "tabs.noReviewSelected")}
      />
    );
  }
  if (activeTab === "agents") {
    return (
      <div className="space-y-5">
        <div className="rounded-xl border border-border bg-card p-5 shadow-panel sm:p-6">
          <AgentTimeline agents={agents} language={language} progress={review.progress} />
        </div>
        {isRunning ? (
          <EmptyState
            description={t(language, "tabs.agentSummariesProcessingDesc")}
            icon={Bot}
            title={t(language, "tabs.agentSummariesProcessing")}
          />
        ) : structuredLoading ? (
          <div className="grid gap-4 lg:grid-cols-2" role="status">
            {Array.from({ length: 4 }, (_, index) => (
              <div className="skeleton h-56 rounded-xl" key={index} />
            ))}
            <span className="sr-only">{t(language, "tabs.loadingAgentStates")}</span>
          </div>
        ) : structuredError ? (
          <EmptyState
            actionLabel={t(language, "tabs.retryAgentStates")}
            description={structuredError}
            icon={Bot}
            onAction={onRetryStructuredData}
            title={t(language, "tabs.agentSummariesLoadError")}
          />
        ) : (
          <AgentStateCards agents={agents} language={language} />
        )}
      </div>
    );
  }
  if (activeTab === "findings") {
    if (isRunning) {
      return (
        <EmptyState
          description={t(language, "tabs.findingsValidatedDesc")}
          icon={ShieldAlert}
          title={t(language, "tabs.findingsBeingValidated")}
        />
      );
    }
    return (
      <FindingsPanel
        error={structuredError}
        findings={findings}
        language={language}
        loading={structuredLoading}
        onRetry={onRetryStructuredData}
      />
    );
  }
  if (activeTab === "report") {
    return <ReportPanel isRunning={isRunning} language={language} reportMarkdown={review?.report_markdown} />;
  }
  if (activeTab === "evidence") {
    if (isRunning) {
      return (
        <EmptyState
          description={t(language, "tabs.evidenceCollectedDesc")}
          icon={FileSearch}
          title={t(language, "tabs.evidenceBeingCollected")}
        />
      );
    }
    return (
      <EvidencePanel
        error={structuredError}
        findings={findings}
        language={language}
        loading={structuredLoading}
        onRetry={onRetryStructuredData}
      />
    );
  }
  if (isRunning) {
    return (
      <EmptyState
        description={t(language, "tabs.metricsProcessingDesc")}
        icon={BarChart3}
        title={t(language, "tabs.metricsStillProcessing")}
      />
    );
  }
  if (structuredLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" role="status">
        {Array.from({ length: 4 }, (_, index) => (
          <div className="skeleton h-28 rounded-xl" key={index} />
        ))}
        <span className="sr-only">{t(language, "tabs.loadingReviewMetrics")}</span>
      </div>
    );
  }
  if (structuredError) {
    return (
      <EmptyState
        actionLabel={t(language, "tabs.retryMetrics")}
        description={structuredError}
        icon={BarChart3}
        onAction={onRetryStructuredData}
        title={t(language, "tabs.metricsLoadError")}
      />
    );
  }
  return <MetricsPanel agents={agents} findings={findings} language={language} />;
}
