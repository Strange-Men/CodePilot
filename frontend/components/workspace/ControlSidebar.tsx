import { Download, ExternalLink, LoaderCircle, Radio } from "lucide-react";
import type { FormEvent } from "react";
import React, { useCallback, useState } from "react";

import { ReviewSubmissionForm } from "@/components/ReviewSubmissionForm";
import { Button } from "@/components/ui/button";
import { ReviewHistoryPanel } from "@/components/workspace/ReviewHistoryPanel";
import { exportReview, CodePilotApiError } from "@/lib/api";
import type { Language } from "@/lib/i18n";
import { getLocalizedStatusLabels, t } from "@/lib/i18n";
import type { ReviewResponse } from "@/lib/types";

type ControlSidebarProps = {
  error: string | null;
  fieldError: string | null;
  history: ReviewResponse[];
  historyError: string | null;
  historyLoading: boolean;
  isRunning: boolean;
  language: Language;
  llmMode: "mock" | "mimo";
  onDelete: (taskId: string) => Promise<void>;
  onHistoryRetry: () => void;
  onLlmModeChange: (mode: "mock" | "mimo") => void;
  onRepoUrlChange: (repoUrl: string) => void;
  onSelectReview: (review: ReviewResponse) => void;
  onStaleReview: (taskId: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  repoUrl: string;
  review: ReviewResponse | null;
  selectedTaskId: string | null;
  submitting: boolean;
  taskId: string | null;
};

export function ControlSidebar({
  error,
  fieldError,
  history,
  historyError,
  historyLoading,
  isRunning,
  language,
  llmMode,
  onDelete,
  onHistoryRetry,
  onLlmModeChange,
  onRepoUrlChange,
  onSelectReview,
  onStaleReview,
  onSubmit,
  repoUrl,
  review,
  selectedTaskId,
  submitting,
  taskId
}: ControlSidebarProps) {
  const currentTaskId = review?.task_id || taskId;
  const statusLabels = getLocalizedStatusLabels(language);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const handleExport = useCallback(async () => {
    if (!review || review.status !== "completed") return;
    setExporting(true);
    setExportError(null);
    try {
      const { blob, filename } = await exportReview(review.task_id, { lang: language });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      if (err instanceof CodePilotApiError) {
        if (err.code === "review_not_found") {
          setExportError(t(language, "export.reviewNotFound"));
          onStaleReview(review.task_id);
        } else if (err.code === "review_not_ready") {
          setExportError(t(language, "export.notReady"));
        } else {
          setExportError(err.detail || t(language, "export.networkError"));
        }
      } else {
        setExportError(t(language, "export.networkError"));
      }
    } finally {
      setExporting(false);
    }
  }, [review, language, onStaleReview]);

  return (
    <aside className="rounded-xl border border-border bg-card p-5 shadow-panel lg:sticky lg:top-24 lg:max-h-[calc(100dvh-7rem)] lg:overflow-y-auto">
      <div>
        <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-primary">
          {t(language, "sidebar.controlPanel")}
        </p>
        <h2 className="mt-1 text-lg font-semibold tracking-tight">{t(language, "sidebar.repositoryReview")}</h2>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          {t(language, "sidebar.description")}
        </p>
      </div>

      <div className="mt-5">
        <ReviewSubmissionForm
          fieldError={fieldError}
          isRunning={isRunning}
          language={language}
          llmMode={llmMode}
          onLlmModeChange={onLlmModeChange}
          onRepoUrlChange={onRepoUrlChange}
          onSubmit={onSubmit}
          repoUrl={repoUrl}
          submitting={submitting}
        />
      </div>

      <section aria-label={t(language, "sidebar.currentStatus")} className="mt-5 rounded-xl border border-border bg-panel p-4">
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs font-medium text-muted-foreground">{t(language, "sidebar.currentStatus")}</span>
          {isRunning ? <LoaderCircle className="h-4 w-4 animate-spin text-primary" /> : <Radio className="h-4 w-4 text-muted-foreground" />}
        </div>
        <p className="mt-2 text-sm font-semibold">
          {review ? statusLabels[review.status] : taskId ? t(language, "header.queued") : t(language, "sidebar.notStarted")}
        </p>
        {currentTaskId ? (
          <code className="mt-2 block truncate font-mono text-[11px] text-muted-foreground" title={currentTaskId}>
            {currentTaskId}
          </code>
        ) : null}
        {review?.progress ? (
          <div className="mt-3">
            <div className="flex items-center justify-between text-[11px] text-muted-foreground">
              <span>{review.progress.current_phase}</span>
              <span className="font-mono">
                {review.progress.completed_agents}/{review.progress.total_agents}
              </span>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-[width] duration-250"
                style={{
                  width: `${review.progress.total_agents
                    ? (review.progress.completed_agents / review.progress.total_agents) * 100
                    : 0}%`
                }}
              />
            </div>
          </div>
        ) : null}
      </section>

      {error ? (
        <div className="mt-4 rounded-xl border border-destructive/35 bg-destructive/5 p-4 text-sm leading-6 text-destructive" role="alert">
          {error}
        </div>
      ) : null}

      {review?.status === "completed" ? (
        <>
          <Button
            className="mt-4 w-full"
            disabled={exporting}
            onClick={() => void handleExport()}
            variant="outline"
          >
            {exporting ? (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            ) : (
              <Download className="h-4 w-4" />
            )}
            {t(language, "sidebar.exportMarkdown")}
          </Button>
          {exportError ? (
            <div className="mt-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-xs leading-5 text-destructive" role="alert">
              {exportError}
            </div>
          ) : null}
        </>
      ) : null}

      <ReviewHistoryPanel
        error={historyError}
        language={language}
        loading={historyLoading}
        onDelete={onDelete}
        onRetry={onHistoryRetry}
        onSelect={onSelectReview}
        reviews={history}
        selectedTaskId={selectedTaskId}
      />
    </aside>
  );
}
