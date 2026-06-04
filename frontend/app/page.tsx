"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { Download, Github, Loader2, Play, RefreshCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type ReviewStatus = "pending" | "cloning" | "parsing" | "summarizing" | "reviewing" | "completed" | "failed";

type ReviewResponse = {
  task_id: string;
  repo_url: string;
  status: ReviewStatus;
  error: string | null;
  report_markdown: string | null;
  export_path: string | null;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
const STATUS_LABELS: Record<ReviewStatus, string> = {
  pending: "Pending",
  cloning: "Cloning",
  parsing: "Parsing",
  summarizing: "Summarizing",
  reviewing: "Reviewing",
  completed: "Completed",
  failed: "Failed"
};

const orderedSections = [
  "Architecture Summary",
  "Code Smells",
  "Maintainability Issues",
  "Refactoring Suggestions"
];

export default function Home() {
  const [repoUrl, setRepoUrl] = useState("https://github.com/pallets/flask");
  const [taskId, setTaskId] = useState<string | null>(null);
  const [review, setReview] = useState<ReviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const isRunning = review && !["completed", "failed"].includes(review.status);

  useEffect(() => {
    const repoFromQuery = new URLSearchParams(window.location.search).get("repo_url");
    if (repoFromQuery) {
      setRepoUrl(repoFromQuery);
    }
  }, []);

  useEffect(() => {
    if (!taskId) return;

    let cancelled = false;
    async function poll() {
      try {
        const response = await fetch(`${API_BASE}/api/reviews/${taskId}`);
        if (!response.ok) throw new Error(await response.text());
        const data = (await response.json()) as ReviewResponse;
        if (!cancelled) {
          setReview(data);
          setError(data.error);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to fetch review status.");
      }
    }

    poll();
    const timer = window.setInterval(poll, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [taskId]);

  const sections = useMemo(() => parseReport(review?.report_markdown || ""), [review?.report_markdown]);

  async function submitReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setReview(null);
    setTaskId(null);

    try {
      const response = await fetch(`${API_BASE}/api/reviews`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: repoUrl })
      });
      if (!response.ok) throw new Error(await response.text());
      const data = (await response.json()) as { task_id: string };
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
              Clone a public GitHub repository, index Python code, generate concise repository context, and export a focused review report.
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
            <form className="space-y-3" onSubmit={submitReview}>
              <Input
                aria-label="GitHub repository URL"
                value={repoUrl}
                onChange={(event) => setRepoUrl(event.target.value)}
                placeholder="https://github.com/user/repo"
              />
              <Button className="w-full" disabled={submitting || Boolean(isRunning)} type="submit">
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                Start Review
              </Button>
            </form>

            <div className="mt-5 space-y-3">
              <StatusRow label="Task" value={taskId || "Not started"} />
              <StatusRow label="Status" value={review ? STATUS_LABELS[review.status] : "Idle"} />
              {isRunning ? <ProgressRail status={review.status} /> : null}
              {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div> : null}
              {review?.status === "completed" ? (
                <Button asChild className="w-full" variant="outline">
                  <a href={`${API_BASE}/api/reviews/${review.task_id}/export`}>
                    <Download className="h-4 w-4" />
                    Export Markdown
                  </a>
                </Button>
              ) : null}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-5">
          {review?.report_markdown ? (
            orderedSections.map((section) => (
              <Card key={section}>
                <CardHeader>
                  <CardTitle>{section}</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="whitespace-pre-wrap text-sm leading-6 text-foreground">{sections[section] || "No findings returned."}</div>
                </CardContent>
              </Card>
            ))
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Review Report</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex min-h-[280px] flex-col items-center justify-center gap-3 rounded-md border border-dashed border-border bg-background p-8 text-center">
                  {isRunning ? <RefreshCcw className="h-8 w-8 animate-spin text-primary" /> : <Github className="h-8 w-8 text-muted-foreground" />}
                  <p className="max-w-md text-sm leading-6 text-muted-foreground">
                    {isRunning
                      ? "CodePilot is cloning, parsing, summarizing, and reviewing the repository."
                      : "Start a review to see the generated architecture, smell, maintainability, and refactoring sections here."}
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </section>
    </main>
  );
}

function StatusRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md bg-background px-3 py-2 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="truncate font-medium">{value}</span>
    </div>
  );
}

function ProgressRail({ status }: { status: ReviewStatus }) {
  const statuses: ReviewStatus[] = ["pending", "cloning", "parsing", "summarizing", "reviewing", "completed"];
  const activeIndex = statuses.indexOf(status);
  return (
    <div className="grid grid-cols-6 gap-1" aria-label="Review progress">
      {statuses.map((item, index) => (
        <div
          className={`h-2 rounded-sm ${index <= activeIndex ? "bg-primary" : "bg-muted"}`}
          key={item}
          title={STATUS_LABELS[item]}
        />
      ))}
    </div>
  );
}

function parseReport(markdown: string): Record<string, string> {
  const sections: Record<string, string> = {};
  let current = "";

  for (const line of markdown.split("\n")) {
    const heading = line.replace(/^#+\s*/, "").trim();
    if (orderedSections.includes(heading)) {
      current = heading;
      sections[current] = "";
      continue;
    }
    if (current) {
      sections[current] = `${sections[current]}${line}\n`;
    }
  }

  return sections;
}
