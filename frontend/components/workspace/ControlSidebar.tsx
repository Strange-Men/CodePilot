import { Download, ExternalLink, LoaderCircle, Radio } from "lucide-react";
import type { FormEvent } from "react";
import React from "react";

import { ReviewSubmissionForm } from "@/components/ReviewSubmissionForm";
import { Button } from "@/components/ui/button";
import { ReviewHistoryPanel } from "@/components/workspace/ReviewHistoryPanel";
import { getReviewExportUrl } from "@/lib/api";
import { STATUS_LABELS } from "@/lib/report";
import type { ReviewResponse } from "@/lib/types";

type ControlSidebarProps = {
  error: string | null;
  fieldError: string | null;
  history: ReviewResponse[];
  historyError: string | null;
  historyLoading: boolean;
  isRunning: boolean;
  llmMode: "mock" | "mimo";
  onDelete: (taskId: string) => Promise<void>;
  onHistoryRetry: () => void;
  onLlmModeChange: (mode: "mock" | "mimo") => void;
  onRepoUrlChange: (repoUrl: string) => void;
  onSelectReview: (review: ReviewResponse) => void;
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
  llmMode,
  onDelete,
  onHistoryRetry,
  onLlmModeChange,
  onRepoUrlChange,
  onSelectReview,
  onSubmit,
  repoUrl,
  review,
  selectedTaskId,
  submitting,
  taskId
}: ControlSidebarProps) {
  const currentTaskId = review?.task_id || taskId;

  return (
    <aside className="rounded-xl border border-border bg-card p-5 shadow-panel lg:sticky lg:top-24 lg:max-h-[calc(100dvh-7rem)] lg:overflow-y-auto">
      <div>
        <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-primary">
          Control panel
        </p>
        <h2 className="mt-1 text-lg font-semibold tracking-tight">Repository review</h2>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Import a public GitHub repository and run the evidence-grounded review pipeline.
        </p>
      </div>

      <div className="mt-5">
        <ReviewSubmissionForm
          fieldError={fieldError}
          isRunning={isRunning}
          llmMode={llmMode}
          onLlmModeChange={onLlmModeChange}
          onRepoUrlChange={onRepoUrlChange}
          onSubmit={onSubmit}
          repoUrl={repoUrl}
          submitting={submitting}
        />
      </div>

      <section aria-label="Current task status" className="mt-5 rounded-xl border border-border bg-panel p-4">
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs font-medium text-muted-foreground">Current status</span>
          {isRunning ? <LoaderCircle className="h-4 w-4 animate-spin text-primary" /> : <Radio className="h-4 w-4 text-muted-foreground" />}
        </div>
        <p className="mt-2 text-sm font-semibold">
          {review ? STATUS_LABELS[review.status] : taskId ? "Queued" : "Not started"}
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
        <Button asChild className="mt-4 w-full" variant="outline">
          <a href={getReviewExportUrl(review.task_id)}>
            <Download className="h-4 w-4" />
            Export Markdown
            <ExternalLink className="ml-auto h-3.5 w-3.5 text-muted-foreground" />
          </a>
        </Button>
      ) : null}

      <ReviewHistoryPanel
        error={historyError}
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
