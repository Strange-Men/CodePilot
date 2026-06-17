"use client";

import { Code2, Cpu } from "lucide-react";
import type { FormEvent } from "react";
import React from "react";
import { useCallback, useEffect, useState } from "react";

import { ControlSidebar } from "@/components/workspace/ControlSidebar";
import { StatusBadge } from "@/components/ui/status-badge";
import { LanguageToggle } from "@/components/workspace/LanguageToggle";
import { ThemeToggle } from "@/components/workspace/ThemeToggle";
import { type WorkspaceTab, WorkspaceTabs } from "@/components/workspace/WorkspaceTabs";
import { useLanguage } from "@/hooks/useLanguage";
import { useReviewPolling } from "@/hooks/useReviewPolling";
import {
  CodePilotApiError,
  createReview,
  deleteReview,
  getReview,
  getReviewAgentStates,
  getReviewFindings,
  listReviews
} from "@/lib/api";
import { getLocalizedStatusLabels, type Language, t } from "@/lib/i18n";
import { terminalStatuses } from "@/lib/report";
import type { ReviewAgentStateItem, ReviewFindingItem, ReviewResponse } from "@/lib/types";
import { validateGitHubRepositoryUrl } from "@/lib/validation";

export function WorkspaceShell() {
  const [repoUrl, setRepoUrl] = useState("https://github.com/pallets/flask");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [review, setReview] = useState<ReviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [history, setHistory] = useState<ReviewResponse[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [llmMode, setLlmMode] = useState<"mock" | "mimo">("mock");
  const [activeTab, setActiveTab] = useState<WorkspaceTab>("overview");
  const [findings, setFindings] = useState<ReviewFindingItem[]>([]);
  const [evidenceDisplayMap, setEvidenceDisplayMap] = useState<Record<string, string>>({});
  const [agents, setAgents] = useState<ReviewAgentStateItem[]>([]);
  const [structuredLoading, setStructuredLoading] = useState(false);
  const [structuredError, setStructuredError] = useState<string | null>(null);
  const [structuredReloadKey, setStructuredReloadKey] = useState(0);
  const [language, setLanguage] = useLanguage();

  const statusLabels = getLocalizedStatusLabels(language);
  const isRunning = Boolean(review && !terminalStatuses.includes(review.status));
  const headerStatus = review?.status || (taskId ? "queued" : "idle");
  const headerStatusLabel = review ? statusLabels[review.status] : taskId ? t(language, "header.queued") : t(language, "header.idle");

  const refreshHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      setHistory(await listReviews());
    } catch (err) {
      setHistoryError(friendlyErrorMessage(err, language, t(language, "history.loadError")));
    } finally {
      setHistoryLoading(false);
    }
  }, [language]);

  useEffect(() => {
    const repoFromQuery = new URLSearchParams(window.location.search).get("repo_url");
    if (repoFromQuery) setRepoUrl(repoFromQuery);
    void refreshHistory();
  }, [refreshHistory]);

  const handleReview = useCallback((data: ReviewResponse) => {
    setReview(data);
    if (terminalStatuses.includes(data.status)) void refreshHistory();
  }, [refreshHistory]);

  const handlePollingError = useCallback((message: string) => {
    setError(message ? friendlyErrorMessage(message, language) : null);
  }, [language]);

  useReviewPolling({ taskId, onReview: handleReview, onError: handlePollingError });

  useEffect(() => {
    if (!review || !terminalStatuses.includes(review.status)) {
      setFindings([]);
      setAgents([]);
      setStructuredError(null);
      setStructuredLoading(false);
      return;
    }

    let cancelled = false;
    setStructuredLoading(true);
    setStructuredError(null);
    Promise.all([
      getReviewFindings(review.task_id, { lang: language }),
      getReviewAgentStates(review.task_id)
    ])
      .then(([findingData, agentData]) => {
        if (!cancelled) {
          setFindings(findingData.findings);
          setEvidenceDisplayMap(findingData.evidence_display_map || {});
          setAgents(agentData.agents);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          if (err instanceof CodePilotApiError && err.code === "review_not_found") {
            handleStaleReview(review.task_id);
          } else {
            setStructuredError(friendlyErrorMessage(err, language, t(language, "tabs.structuredDataLoadError")));
          }
        }
      })
      .finally(() => {
        if (!cancelled) setStructuredLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [review?.task_id, review?.status, structuredReloadKey, language]);

  // Re-fetch localized report when language changes for completed reviews
  useEffect(() => {
    if (!review || !terminalStatuses.includes(review.status)) return;

    let cancelled = false;
    getReview(review.task_id, { lang: language })
      .then((localizedReview) => {
        if (!cancelled && localizedReview.report_markdown) {
          setReview((prev) =>
            prev && prev.task_id === localizedReview.task_id
              ? { ...prev, report_markdown: localizedReview.report_markdown }
              : prev
          );
        }
      })
      .catch((err) => {
        if (!cancelled && err instanceof CodePilotApiError && err.code === "review_not_found") {
          handleStaleReview(review.task_id);
        }
        // Other errors: silent fallback — the existing report remains visible
      });
    return () => {
      cancelled = true;
    };
  }, [language, review?.task_id, review?.status]);

  async function submitReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validateGitHubRepositoryUrl(repoUrl);
    setFieldError(validationError);
    if (validationError) return;

    setSubmitting(true);
    setError(null);
    setReview(null);
    setTaskId(null);
    setFindings([]);
    setAgents([]);
    setActiveTab("overview");

    try {
      const data = await createReview(repoUrl, llmMode);
      setTaskId(data.task_id);
      void refreshHistory();
    } catch (err) {
      setError(friendlyErrorMessage(err, language, t(language, "error.startReviewFailed")));
    } finally {
      setSubmitting(false);
    }
  }

  function selectHistoricalReview(historicalReview: ReviewResponse) {
    setTaskId(null);
    setReview(historicalReview);
    setRepoUrl(historicalReview.repo_url);
    setError(historicalReview.error);
    setFieldError(null);
    setStructuredLoading(true);
    setStructuredError(null);
    setStructuredReloadKey((key) => key + 1);
    setActiveTab("overview");
  }

  function changeRepoUrl(value: string) {
    setRepoUrl(value);
    if (fieldError) setFieldError(validateGitHubRepositoryUrl(value));
  }

  async function removeReview(taskToDelete: string) {
    setError(null);
    try {
      await deleteReview(taskToDelete);
      setHistory((current) => current.filter((item) => item.task_id !== taskToDelete));
      if (review?.task_id === taskToDelete) {
        setReview(null);
        setTaskId(null);
        setFindings([]);
        setAgents([]);
        setActiveTab("overview");
      }
    } catch (err) {
      setError(friendlyErrorMessage(err, language, t(language, "error.deleteReviewFailed")));
    }
  }

  function handleStaleReview(staleTaskId: string) {
    setHistory((current) => current.filter((item) => item.task_id !== staleTaskId));
    if (review?.task_id === staleTaskId) {
      setReview(null);
      setTaskId(null);
      setFindings([]);
      setAgents([]);
      setActiveTab("overview");
    }
  }

  return (
    <main className="min-h-dvh bg-background">
      <header className="sticky top-0 z-20 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/85">
        <div className="mx-auto flex min-h-16 max-w-[1600px] items-center justify-between gap-2 px-4 sm:gap-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary shadow-sm">
              <Code2 className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="truncate text-base font-semibold tracking-tight">CodePilot</h1>
                <span className="hidden font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground sm:inline">
                  {t(language, "header.workspace")}
                </span>
              </div>
              <p className="hidden truncate text-xs text-muted-foreground sm:block">
                {t(language, "header.tagline")}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="inline-flex min-h-9 items-center gap-1.5 rounded-full border border-border bg-card px-2 text-xs font-semibold sm:px-3">
              <Cpu className="h-3.5 w-3.5 text-primary" />
              {llmMode === "mimo" ? "MiMo" : "Mock"}
            </span>
            <StatusBadge label={headerStatusLabel} pulse={isRunning} status={headerStatus} />
            <LanguageToggle language={language} onLanguageChange={setLanguage} />
            <ThemeToggle />
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1600px] gap-5 px-4 py-5 sm:px-6 lg:grid-cols-[340px_minmax(0,1fr)]">
        <ControlSidebar
          error={error}
          fieldError={fieldError}
          history={history}
          historyError={historyError}
          historyLoading={historyLoading}
          isRunning={isRunning}
          language={language}
          llmMode={llmMode}
          onDelete={removeReview}
          onHistoryRetry={() => void refreshHistory()}
          onLlmModeChange={setLlmMode}
          onRepoUrlChange={changeRepoUrl}
          onSelectReview={selectHistoricalReview}
          onStaleReview={handleStaleReview}
          onSubmit={submitReview}
          repoUrl={repoUrl}
          review={review}
          selectedTaskId={review?.task_id || taskId}
          submitting={submitting}
          taskId={taskId}
        />
        <WorkspaceTabs
          activeTab={activeTab}
          agents={agents}
          findings={findings}
          evidenceDisplayMap={evidenceDisplayMap}
          isRunning={isRunning}
          language={language}
          onRetryStructuredData={() => setStructuredReloadKey((key) => key + 1)}
          onTabChange={setActiveTab}
          review={review}
          structuredError={structuredError}
          structuredLoading={structuredLoading}
        />
      </div>
    </main>
  );
}

function friendlyErrorMessage(error: unknown, language: Language, fallback?: string): string {
  const code = error instanceof CodePilotApiError ? error.code : undefined;
  const raw = error instanceof Error ? error.message : typeof error === "string" ? error : fallback || "";
  const lower = raw.toLowerCase();

  if (code === "review_not_found") return t(language, "error.reviewNoLongerAvailable");
  if (code === "review_not_ready") return t(language, "export.notReady");
  if (code === "llm_config_error" || lower.includes("api key") || lower.includes("unauthorized")) {
    return t(language, "error.providerAuth");
  }
  if (lower.includes("timeout") || lower.includes("network") || lower.includes("econnrefused")) {
    return t(language, "error.providerNetwork");
  }
  if (lower.includes("429") || lower.includes("rate limit")) {
    return t(language, "error.providerRateLimit");
  }
  return fallback || raw || t(language, "error.generic");
}
