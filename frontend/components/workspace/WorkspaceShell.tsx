"use client";

import { Code2, Cpu, Radio } from "lucide-react";
import type { FormEvent } from "react";
import React from "react";
import { useCallback, useEffect, useState } from "react";

import { ControlSidebar } from "@/components/workspace/ControlSidebar";
import { LanguageToggle } from "@/components/workspace/LanguageToggle";
import { ThemeToggle } from "@/components/workspace/ThemeToggle";
import { type WorkspaceTab, WorkspaceTabs } from "@/components/workspace/WorkspaceTabs";
import { useLanguage } from "@/hooks/useLanguage";
import { useReviewPolling } from "@/hooks/useReviewPolling";
import {
  createReview,
  deleteReview,
  getReview,
  getReviewAgentStates,
  getReviewFindings,
  listReviews
} from "@/lib/api";
import { getLocalizedStatusLabels, t } from "@/lib/i18n";
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
  const [agents, setAgents] = useState<ReviewAgentStateItem[]>([]);
  const [structuredLoading, setStructuredLoading] = useState(false);
  const [structuredError, setStructuredError] = useState<string | null>(null);
  const [structuredReloadKey, setStructuredReloadKey] = useState(0);
  const [language, setLanguage] = useLanguage();

  const statusLabels = getLocalizedStatusLabels(language);
  const isRunning = Boolean(review && !terminalStatuses.includes(review.status));

  const refreshHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      setHistory(await listReviews());
    } catch (err) {
      setHistoryError(err instanceof Error ? err.message : "Unable to load review history.");
    } finally {
      setHistoryLoading(false);
    }
  }, []);

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
    setError(message || null);
  }, []);

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
          setAgents(agentData.agents);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setStructuredError(err instanceof Error ? err.message : "Unable to load structured review data.");
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
      .catch(() => {
        // Silent fallback — the existing report remains visible
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
      setError(err instanceof Error ? err.message : "Unable to start review.");
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
      setError(err instanceof Error ? err.message : "Unable to delete review.");
    }
  }

  return (
    <main className="min-h-dvh bg-background">
      <header className="sticky top-0 z-20 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/85">
        <div className="mx-auto flex min-h-16 max-w-[1600px] items-center justify-between gap-2 px-4 sm:gap-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-foreground text-background shadow-sm">
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
            <span className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-border bg-card px-2 text-xs font-semibold sm:px-3">
              <Cpu className="h-3.5 w-3.5 text-primary" />
              {llmMode === "mimo" ? "MiMo" : "Mock"}
            </span>
            <span className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-border bg-card px-2 text-xs font-semibold sm:px-3">
              <Radio className={`h-3.5 w-3.5 ${isRunning ? "animate-pulse text-primary" : "text-muted-foreground"}`} />
              {review ? statusLabels[review.status] : taskId ? t(language, "header.queued") : t(language, "header.idle")}
            </span>
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
