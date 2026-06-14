import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { ReportRenderer } from "../components/ReportRenderer";
import { ReviewHistory } from "../components/ReviewHistory";
import { ReviewStatusDisplay, RuntimeAgentProgress } from "../components/ReviewStatusDisplay";
import { ReviewSubmissionForm } from "../components/ReviewSubmissionForm";
import ErrorPage from "../app/error";
import Loading from "../app/loading";
import {
  CodePilotApiError,
  createReview,
  deleteReview,
  getReviewAgentStates,
  getReviewFindings,
  listReviews
} from "../lib/api";
import type { ReviewProgressSnapshot, ReviewResponse } from "../lib/types";
import { validateGitHubRepositoryUrl } from "../lib/validation";

let llmModeCalls: string[] = [];
let lastCreateReviewMode: string | undefined;

const completedReview: ReviewResponse = {
  task_id: "task-1",
  repo_url: "https://github.com/example/project",
  status: "completed",
  error: null,
  report_markdown: "# Architecture Summary\nDone.",
  export_path: "reports/task-1.md"
};

const runningProgress: ReviewProgressSnapshot = {
  current_phase: "Running CodeSmellAgent",
  current_agent_id: "CodeSmellAgent",
  total_agents: 4,
  completed_agents: 1,
  agents: [
    { order: 1, label: "A1 ArchitectureAgent", agent_id: "ArchitectureAgent", status: "completed", findings_count: 1, evidence_count: 2, error: null },
    { order: 2, label: "A2 CodeSmellAgent", agent_id: "CodeSmellAgent", status: "running", findings_count: null, evidence_count: null, error: null },
    { order: 3, label: "A3 MaintainabilityAgent", agent_id: "MaintainabilityAgent", status: "pending", findings_count: null, evidence_count: null, error: null },
    { order: 4, label: "A4 RefactorAgent", agent_id: "RefactorAgent", status: "pending", findings_count: null, evidence_count: null, error: null }
  ]
};

const failedProgress: ReviewProgressSnapshot = {
  ...runningProgress,
  current_phase: "Review failed",
  completed_agents: 1,
  agents: runningProgress.agents.map((agent) =>
    agent.agent_id === "CodeSmellAgent"
      ? { ...agent, status: "failed", error: "Agent execution failed." }
      : agent
  )
};

const agentReport = [
  "# Executive Summary",
  "Original executive summary remains visible.",
  "# Agent Summary",
  "| Agent | Status | Findings | Severity Mix | Avg Confidence | Evidence |",
  "| --- | --- | ---: | --- | ---: | ---: |",
  "| ArchitectureAgent | completed | 1 | high=1 | 0.92 | 2 |",
  "| CodeSmellAgent | completed | 1 | medium=1 | 0.81 | 1 |",
  "| MaintainabilityAgent | completed | 1 | low=1 | 0.75 | 1 |",
  "| RefactorAgent | completed | 1 | informational=1 | 0.68 | 1 |",
  "# Agent Findings",
  "Findings are grouped by the agent that produced them.",
  "## ArchitectureAgent",
  "| Severity | Finding | Confidence | Files | Evidence |",
  "| --- | --- | ---: | --- | --- |",
  "| high | Boundary risk | 0.92 | `src/app.py`, `src/api.py` | `E123`, `E124` |",
  "## CodeSmellAgent",
  "| Severity | Finding | Confidence | Files | Evidence |",
  "| --- | --- | ---: | --- | --- |",
  "| medium | Duplicate validation | 0.81 | `src/forms.py` | `E200` |",
  "## MaintainabilityAgent",
  "| Severity | Finding | Confidence | Files | Evidence |",
  "| --- | --- | ---: | --- | --- |",
  "| low | Dense module | 0.75 | `src/service.py` | `E300` |",
  "## RefactorAgent",
  "| Severity | Finding | Confidence | Files | Evidence |",
  "| --- | --- | ---: | --- | --- |",
  "| informational | Extract helper | 0.68 | `src/utils.py` | `E400` |",
  "# Architecture Summary",
  "Original architecture narrative.",
  "# Code Smells",
  "Original smell narrative.",
  "# Maintainability Issues",
  "Original maintainability narrative.",
  "# Refactoring Suggestions",
  "Original refactoring narrative.",
  "# Evidence Appendix",
  "Only validated references are shown."
].join("\n");

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
      llmMode="mock"
      onLlmModeChange={() => undefined}
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

test("frontend API client loads structured review findings", async () => {
  const originalFetch = globalThis.fetch;
  let requestedUrl = "";
  globalThis.fetch = async (input) => {
    requestedUrl = String(input);
    return new Response(JSON.stringify({ task_id: "task-1", findings: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  };

  try {
    const result = await getReviewFindings("task-1");
    assert.deepEqual(result, { task_id: "task-1", findings: [] });
    assert.match(requestedUrl, /\/api\/reviews\/task-1\/findings$/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("frontend API client loads structured review agent states", async () => {
  const originalFetch = globalThis.fetch;
  let requestedUrl = "";
  globalThis.fetch = async (input) => {
    requestedUrl = String(input);
    return new Response(JSON.stringify({ task_id: "task-1", agents: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" }
    });
  };

  try {
    const result = await getReviewAgentStates("task-1");
    assert.deepEqual(result, { task_id: "task-1", agents: [] });
    assert.match(requestedUrl, /\/api\/reviews\/task-1\/agent-states$/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("frontend API client handles review deletion with an empty 204 response", async () => {
  const originalFetch = globalThis.fetch;
  let requestedUrl = "";
  let requestedMethod = "";
  globalThis.fetch = async (input, init) => {
    requestedUrl = String(input);
    requestedMethod = init?.method || "";
    return new Response(null, { status: 204 });
  };

  try {
    await deleteReview("task-1");
    assert.match(requestedUrl, /\/api\/reviews\/task-1$/);
    assert.equal(requestedMethod, "DELETE");
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

test("LLM mode selector renders with Mock as default", () => {
  const html = renderToStaticMarkup(
    <ReviewSubmissionForm
      fieldError={null}
      isRunning={false}
      llmMode="mock"
      onLlmModeChange={() => undefined}
      onRepoUrlChange={() => undefined}
      onSubmit={() => undefined}
      repoUrl="https://github.com/example/project"
      submitting={false}
    />
  );

  assert.match(html, /LLM Mode/);
  assert.match(html, /Mock LLM/);
  assert.match(html, /MiMo Real LLM/);
  assert.match(html, /deterministic mock output/);
  assert.match(html, /No API key required/);
});

test("selecting MiMo updates helper text", () => {
  const html = renderToStaticMarkup(
    <ReviewSubmissionForm
      fieldError={null}
      isRunning={false}
      llmMode="mimo"
      onLlmModeChange={() => undefined}
      onRepoUrlChange={() => undefined}
      onSubmit={() => undefined}
      repoUrl="https://github.com/example/project"
      submitting={false}
    />
  );

  assert.match(html, /MiMo Real LLM selected|backend MiMo configuration/);
  assert.match(html, /MIMO_API_KEY/);
});

test("Start Review sends llm_mode mimo", async () => {
  const originalFetch = globalThis.fetch;
  let sentBody: Record<string, unknown> = {};
  globalThis.fetch = async (_url, init) => {
    sentBody = JSON.parse(init?.body as string || "{}");
    return new Response(
      JSON.stringify({ task_id: "task-mimo", llm_mode: "mimo" }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  };

  try {
    const result = await createReview("https://github.com/example/project", "mimo");
    assert.equal(result.task_id, "task-mimo");
    assert.equal(result.llm_mode, "mimo");
    assert.equal(sentBody.llm_mode, "mimo");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("missing-key backend error is displayed", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({
        error: "LLM configuration error",
        code: "llm_config_error",
        detail: "MiMo API key is not configured. Set MIMO_API_KEY in backend .env."
      }),
      { status: 400, headers: { "Content-Type": "application/json" } }
    );

  try {
    await assert.rejects(
      createReview("https://github.com/example/project", "mimo"),
      (error: unknown) =>
        error instanceof CodePilotApiError
        && error.code === "llm_config_error"
        && error.message.includes("MIMO_API_KEY")
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("old report rendering still works without llm_mode metadata", () => {
  const html = renderToStaticMarkup(
    <ReviewHistory
      error={null}
      loading={false}
      onSelect={() => undefined}
      reviews={[completedReview]}
      selectedTaskId="task-1"
    />
  );

  assert.match(html, /example\/project/);
  assert.match(html, /Completed/);
});

test("renders four agent contribution cards from Agent Summary", () => {
  const html = renderToStaticMarkup(
    <ReportRenderer isRunning={false} reportMarkdown={agentReport} />
  );

  assert.match(html, /Agent Contribution/);
  assert.equal((html.match(/data-agent-card=/g) || []).length, 4);
  assert.match(html, /ArchitectureAgent/);
  assert.match(html, /CodeSmellAgent/);
  assert.match(html, /MaintainabilityAgent/);
  assert.match(html, /RefactorAgent/);
  assert.match(html, /Severity mix/);
  assert.match(html, /Avg confidence/);
});

test("groups findings by agent and displays evidence IDs near findings", () => {
  const html = renderToStaticMarkup(
    <ReportRenderer isRunning={false} reportMarkdown={agentReport} />
  );

  assert.equal((html.match(/data-agent-findings-group=/g) || []).length, 4);
  assert.match(html, /Boundary risk/);
  assert.match(html, /Affected files:/);
  assert.match(html, /src\/app\.py/);
  assert.match(html, /Evidence:/);
  assert.match(html, />E123<\/code>/);
  assert.match(html, />E124<\/code>/);
});

test("keeps original markdown visible with the agent visualization", () => {
  const html = renderToStaticMarkup(
    <ReportRenderer isRunning={false} reportMarkdown={agentReport} />
  );

  assert.match(html, /Original executive summary remains visible/);
  assert.match(html, /Original architecture narrative/);
  assert.match(html, /Only validated references are shown/);
});

test("old reports without Agent Summary render with a graceful fallback", () => {
  const html = renderToStaticMarkup(
    <ReportRenderer
      isRunning={false}
      reportMarkdown={[
        "# Architecture Summary",
        "Legacy architecture remains visible.",
        "# Code Smells",
        "No findings.",
        "# Maintainability Issues",
        "No findings.",
        "# Refactoring Suggestions",
        "No findings."
      ].join("\n")}
    />
  );

  assert.match(html, /Agent details are not available for this review/);
  assert.match(html, /Legacy architecture remains visible/);
});

test("runtime agent progress renders four ordered agents and the active step", () => {
  const html = renderToStaticMarkup(<RuntimeAgentProgress progress={runningProgress} />);

  assert.match(html, /Running CodeSmellAgent/);
  assert.match(html, /Current agent: A2 CodeSmellAgent/);
  assert.equal((html.match(/data-agent-progress=/g) || []).length, 4);
  assert.match(html, /data-status="completed"/);
  assert.match(html, /data-status="running"/);
  assert.match(html, /data-status="pending"/);
  assert.match(html, /aria-current="step"/);
});

test("missing runtime progress falls back to the existing status display", () => {
  const review: ReviewResponse = {
    ...completedReview,
    status: "parsing",
    report_markdown: null,
    export_path: null
  };
  const html = renderToStaticMarkup(
    <ReviewStatusDisplay error={null} isRunning review={review} taskId={review.task_id} />
  );

  assert.match(html, /Parsing/);
  assert.match(html, /aria-label="Review progress"/);
  assert.doesNotMatch(html, /Runtime agent progress/);
});

test("failed review renders a visually explicit failed progress state", () => {
  const review: ReviewResponse = {
    ...completedReview,
    status: "failed",
    error: "Review execution failed.",
    report_markdown: null,
    export_path: null
  };
  const html = renderToStaticMarkup(
    <ReviewStatusDisplay error={null} isRunning={false} review={review} taskId={review.task_id} />
  );

  assert.match(html, /data-review-status="failed"/);
  assert.match(html, /data-status="failed"/);
  assert.match(html, /Review execution failed/);
});

test("failed agent status remains visible after review polling stops", () => {
  const review: ReviewResponse = {
    ...completedReview,
    status: "failed",
    error: "Review execution failed.",
    report_markdown: null,
    export_path: null,
    progress: failedProgress
  };
  const html = renderToStaticMarkup(
    <ReviewStatusDisplay error={null} isRunning={false} review={review} taskId={review.task_id} />
  );

  assert.match(html, /Runtime agent progress/);
  assert.match(html, /data-agent-progress="CodeSmellAgent"/);
  assert.match(html, /data-status="failed"/);
});

test("failed review without progress falls back to a safe message", () => {
  const review: ReviewResponse = {
    ...completedReview,
    status: "failed",
    error: null,
    report_markdown: null,
    export_path: null,
    progress: null
  };
  const html = renderToStaticMarkup(
    <ReviewStatusDisplay error={null} isRunning={false} review={review} taskId={review.task_id} />
  );

  assert.match(html, /Review failed before completion/);
  assert.doesNotMatch(html, /Runtime agent progress/);
});

test("completed review hides runtime progress and keeps final contribution cards", () => {
  const html = renderToStaticMarkup(
    <>
      <ReviewStatusDisplay
        error={null}
        isRunning={false}
        review={{ ...completedReview, progress: runningProgress }}
        taskId={completedReview.task_id}
      />
      <ReportRenderer isRunning={false} reportMarkdown={agentReport} />
    </>
  );

  assert.doesNotMatch(html, /Runtime agent progress/);
  assert.equal((html.match(/data-agent-card=/g) || []).length, 4);
});
