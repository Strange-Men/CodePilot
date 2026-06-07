"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Github } from "lucide-react";

import { ReportRenderer } from "@/components/ReportRenderer";
import { ReviewStatusDisplay } from "@/components/ReviewStatusDisplay";
import { ReviewSubmissionForm } from "@/components/ReviewSubmissionForm";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useReviewPolling } from "@/hooks/useReviewPolling";
import { createReview } from "@/lib/api";
import { terminalStatuses } from "@/lib/report";
import type { ReviewResponse } from "@/lib/types";

export default function Home() {
  const [repoUrl, setRepoUrl] = useState("https://github.com/pallets/flask");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [review, setReview] = useState<ReviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const isRunning = Boolean(review && !terminalStatuses.includes(review.status));

  useEffect(() => {
    const repoFromQuery = new URLSearchParams(window.location.search).get("repo_url");
    if (repoFromQuery) {
      setRepoUrl(repoFromQuery);
    }
  }, []);

  const handleReview = useCallback((data: ReviewResponse) => {
    setReview(data);
  }, []);

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
    setSubmitting(true);
    setError(null);
    setReview(null);
    setTaskId(null);

    try {
      const data = await createReview(repoUrl);
      setTaskId(data.task_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to start review.");
    } finally {
      setSubmitting(false);
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
              isRunning={isRunning}
              onRepoUrlChange={setRepoUrl}
              onSubmit={submitReview}
              repoUrl={repoUrl}
              submitting={submitting}
            />
            <ReviewStatusDisplay error={error} isRunning={isRunning} review={review} taskId={taskId} />
          </CardContent>
        </Card>

        <div className="space-y-5">
          <ReportRenderer isRunning={isRunning} reportMarkdown={review?.report_markdown} />
        </div>
      </section>
    </main>
  );
}
