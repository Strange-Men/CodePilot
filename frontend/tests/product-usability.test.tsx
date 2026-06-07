import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ReviewHistory } from "../components/ReviewHistory";
import { ReviewSubmissionForm } from "../components/ReviewSubmissionForm";
import ErrorPage from "../app/error";
import Loading from "../app/loading";
import { CodePilotApiError, createReview, listReviews } from "../lib/api";
import type { ReviewResponse } from "../lib/types";
import { validateGitHubRepositoryUrl } from "../lib/validation";

const completedReview: ReviewResponse = {
  task_id: "task-1",
  repo_url: "https://github.com/example/project",
  status: "completed",
  error: null,
  report_markdown: "# Architecture Summary\nDone.",
  export_path: "reports/task-1.md"
};

test("validates canonical GitHub repository URLs", () => {
  assert.equal(validateGitHubRepositoryUrl("https://github.com/example/project"), null);
  assert.equal(validateGitHubRepositoryUrl("https://github.com/example/project.git"), null);
  assert.match(validateGitHubRepositoryUrl("https://gitlab.com/example/project") || "", /GitHub/);
  assert.match(validateGitHubRepositoryUrl("http://github.com/example/project") || "", /HTTPS/);
  assert.match(validateGitHubRepositoryUrl("https://github.com/example/project/issues") || "", /HTTPS/);
});

test("renders review history and selected state", () => {
  const html = renderToStaticMarkup(
    <ReviewHistory
      error={null}
      loading={false}
      onSelect={() => undefined}
      reviews={[completedReview]}
      selectedTaskId="task-1"
    />
  );

  assert.match(html, /Review History/);
  assert.match(html, /example\/project/);
  assert.match(html, /Completed/);
  assert.match(html, /aria-pressed="true"/);
});

test("renders history loading and empty states", () => {
  const loading = renderToStaticMarkup(
    <ReviewHistory
      error={null}
      loading
      onSelect={() => undefined}
      reviews={[]}
      selectedTaskId={null}
    />
  );
  const empty = renderToStaticMarkup(
    <ReviewHistory
      error={null}
      loading={false}
      onSelect={() => undefined}
      reviews={[]}
      selectedTaskId={null}
    />
  );

  assert.match(loading, /Loading previous reviews/);
  assert.match(empty, /will appear here/);
});

test("renders inline repository URL validation feedback", () => {
  const html = renderToStaticMarkup(
    <ReviewSubmissionForm
      fieldError="Use an HTTPS GitHub repository URL."
      isRunning={false}
      onRepoUrlChange={() => undefined}
      onSubmit={() => undefined}
      repoUrl="invalid"
      submitting={false}
    />
  );

  assert.match(html, /aria-invalid="true"/);
  assert.match(html, /repo-url-error/);
  assert.match(html, /Use an HTTPS GitHub repository URL/);
});

test("frontend API client surfaces structured error detail", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({
        error: "Invalid request",
        code: "validation_error",
        detail: "repo_url: Use an HTTPS GitHub repository URL."
      }),
      { status: 422, headers: { "Content-Type": "application/json" } }
    );

  try {
    await assert.rejects(
      createReview("invalid"),
      (error: unknown) =>
        error instanceof CodePilotApiError
        && error.code === "validation_error"
        && error.message.includes("repo_url")
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("frontend API client loads review history", async () => {
  const originalFetch = globalThis.fetch;
  let requestedUrl = "";
  globalThis.fetch = async (input) => {
    requestedUrl = String(input);
    return new Response(JSON.stringify([completedReview]), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  };

  try {
    const history = await listReviews(10);
    assert.equal(history[0].task_id, "task-1");
    assert.match(requestedUrl, /\/api\/reviews\?limit=10$/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("renders route loading and error fallbacks", () => {
  const loadingHtml = renderToStaticMarkup(<Loading />);
  const errorHtml = renderToStaticMarkup(
    <ErrorPage error={new Error("render failed")} reset={() => undefined} />
  );

  assert.match(loadingHtml, /Loading CodePilot/);
  assert.match(errorHtml, /could not render this page/);
  assert.match(errorHtml, /Retry/);
});
