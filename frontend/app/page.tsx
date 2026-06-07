"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Github } from "lucide-react";

import { ReportRenderer } from "@/components/ReportRenderer";
import { ReviewHistory } from "@/components/ReviewHistory";
import { ReviewStatusDisplay } from "@/components/ReviewStatusDisplay";
import { ReviewSubmissionForm } from "@/components/ReviewSubmissionForm";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useReviewPolling } from "@/hooks/useReviewPolling";
import { createReview, listReviews } from "@/lib/api";
import { terminalStatuses } from "@/lib/report";
import type { ReviewResponse } from "@/lib/types";
import { validateGitHubRepositoryUrl } from "@/lib/validation";

export default function Home() {
  const [repoUrl, setRepoUrl] = useState("https://github.com/pallets/flask");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [review, setReview] = useState<ReviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [history, setHistory] = useState<ReviewResponse[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);

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
    if (repoFromQuery) {
      setRepoUrl(repoFromQuery);
    }
    void refreshHistory();
  }, [refreshHistory]);

  const handleReview = useCallback((data: ReviewResponse) => {
    setReview(data);
    if (terminalStatuses.includes(data.status)) {
      void refreshHistory();
    }
  }, [refreshHistory]);

  const handlePollingError = useCallback((message: string) => {
    setError(message || null);
  }, []);

  useReviewPolling({
    taskId,
    onReview: handleReview,
    onError: handlePollingError
  });

  async function submitReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validateGitHubRepositoryUrl(repoUrl);
    setFieldError(validationError);
    if (validationError) return;

    setSubmitting(true);
    setError(null);
    setReview(null);
    setTaskId(null);

    try {
      const data = await createReview(repoUrl);
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
  }

  function changeRepoUrl(value: string) {
    setRepoUrl(value);
    if (fieldError) {
      setFieldError(validateGitHubRepositoryUrl(value));
    }
  }

  return (
    <main className="min-h-screen">
      <section className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-6xl flex-col gap-5 px-5 py-7 md:flex-row md:items-end md:justify-between">
          <div className="max-w-2xl">
            <div className="mb-3 inline-flex items-center gap-2 rounded-md border border-border bg-background px-3 py-1 text-sm text-muted-foreground">
              <Github className="h-4 w-4" />
              AI Code Review Agent
            </div>
            <h1 className="text-3xl font-semibold tracking-normal md:text-4xl">CodePilot</h1>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Clone a public GitHub repository, index supported source code, generate concise repository context, and export a focused review report.
            </p>
          </div>
          <div className="text-sm text-muted-foreground">Mock LLM ready by default</div>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-5 px-5 py-6 lg:grid-cols-[380px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Repository Import</CardTitle>
          </CardHeader>
          <CardContent>
            <ReviewSubmissionForm
              fieldError={fieldError}
              isRunning={isRunning}
              onRepoUrlChange={changeRepoUrl}
              onSubmit={submitReview}
              repoUrl={repoUrl}
              submitting={submitting}
            />
            <ReviewStatusDisplay error={error} isRunning={isRunning} review={review} taskId={taskId} />
          </CardContent>
        </Card>

        <div className="space-y-5">
          <ReviewHistory
            error={historyError}
            loading={historyLoading}
            onSelect={selectHistoricalReview}
            reviews={history}
            selectedTaskId={review?.task_id || taskId}
          />
          <ReportRenderer isRunning={isRunning} reportMarkdown={review?.report_markdown} />
        </div>
      </section>
    </main>
  );
}
