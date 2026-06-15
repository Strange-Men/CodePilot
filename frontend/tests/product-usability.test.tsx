import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import ErrorPage from "../app/error";
import Loading from "../app/loading";
import { ReportRenderer } from "../components/ReportRenderer";
import { ReviewSubmissionForm } from "../components/ReviewSubmissionForm";
import { AgentStateCards } from "../components/workspace/AgentStateCards";
import { AgentTimeline } from "../components/workspace/AgentTimeline";
import { EvidencePanel } from "../components/workspace/EvidencePanel";
import { FindingsPanel } from "../components/workspace/FindingsPanel";
import { applyTheme, nextTheme, ThemeToggle } from "../components/workspace/ThemeToggle";
import { WorkspaceShell } from "../components/workspace/WorkspaceShell";
import {
  CodePilotApiError,
  createReview,
  deleteReview,
  getReviewAgentStates,
  getReviewFindings,
  listReviews
} from "../lib/api";
import type {
  ReviewAgentStateItem,
  ReviewFindingItem,
  ReviewProgressSnapshot,
  ReviewResponse
} from "../lib/types";
import { validateGitHubRepositoryUrl } from "../lib/validation";

const completedReview: ReviewResponse = {
  task_id: "task-1",
  repo_url: "https://github.com/example/project",
  status: "completed",
  error: null,
  report_markdown: "# Executive Summary\nReview complete.\n# Architecture Summary\nStable boundaries.",
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

const structuredAgents: ReviewAgentStateItem[] = [
  {
    order: 1,
    agent_id: "ArchitectureAgent",
    label: "A1 ArchitectureAgent",
    status: "completed",
    findings_count: 1,
    evidence_count: 2,
    severity_mix: { critical: 0, high: 1, medium: 0, low: 0 },
    average_confidence: 0.92,
    error: null
  },
  {
    order: 2,
    agent_id: "CodeSmellAgent",
    label: "A2 CodeSmellAgent",
    status: "failed",
    findings_count: 0,
    evidence_count: 0,
    severity_mix: { critical: 0, high: 0, medium: 0, low: 0 },
    average_confidence: null,
    error: "Agent execution failed."
  },
  {
    order: 3,
    agent_id: "MaintainabilityAgent",
    label: "A3 MaintainabilityAgent",
    status: "completed",
    findings_count: 1,
    evidence_count: 1,
    severity_mix: { critical: 0, high: 0, medium: 1, low: 0 },
    average_confidence: 0.81,
    error: null
  },
  {
    order: 4,
    agent_id: "RefactorAgent",
    label: "A4 RefactorAgent",
    status: "completed",
    findings_count: 1,
    evidence_count: 1,
    severity_mix: { critical: 0, high: 0, medium: 0, low: 1 },
    average_confidence: 0.76,
    error: null
  }
];

const structuredFindings: ReviewFindingItem[] = [
  {
    finding_id: "finding-1",
    finding_index: 0,
    section: "Architecture Summary",
    title: "Boundary risk",
    description: "Transport and domain responsibilities are mixed.",
    severity: "high",
    category: "architecture",
    confidence: 0.92,
    recommendation: "Separate transport from domain orchestration.",
    files: ["src/app.py", "src/api.py"],
    evidence_ids: ["E123", "E124"],
    evidence_refs: [
      {
        evidence_id: "E123",
        file_path: "src/app.py",
        symbol_name: "build_app",
        start_line: 10,
        end_line: 24
      },
      {
        evidence_id: "E124",
        file_path: "src/api.py",
        symbol_name: null,
        start_line: 30,
        end_line: 35
      }
    ],
    validation_status: "validated",
    impact: "Changes to this boundary may affect multiple consumers.",
    first_step: "Add characterization tests before restructuring.",
    validation_tests: ["tests/test_blueprints.py", "tests/test_basic.py"],
    confidence_rationale: "Multiple evidence records confirm the pattern.",
    caveat: "Public API; preserve backward compatibility."
  }
];

test("validates canonical GitHub repository URLs", () => {
  assert.equal(validateGitHubRepositoryUrl("https://github.com/example/project"), null);
  assert.equal(validateGitHubRepositoryUrl("https://github.com/example/project.git"), null);
  assert.match(validateGitHubRepositoryUrl("https://gitlab.com/example/project") || "", /GitHub/);
  assert.match(validateGitHubRepositoryUrl("http://github.com/example/project") || "", /HTTPS/);
});

test("workspace shell renders the control sidebar and six workspace tabs", () => {
  const html = renderToStaticMarkup(<WorkspaceShell />);

  assert.match(html, /CodePilot/);
  assert.match(html, /Review Workspace/);
  assert.match(html, /Control panel/);
  for (const tab of ["Overview", "Agents", "Findings", "Report", "Evidence", "Metrics"]) {
    assert.match(html, new RegExp(`>${tab}<`));
  }
  assert.match(html, /role="tablist"/);
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

test("Mock and MiMo selector states remain available", () => {
  const mockHtml = renderToStaticMarkup(
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
  const mimoHtml = renderToStaticMarkup(
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

  assert.match(mockHtml, /Mock LLM/);
  assert.match(mockHtml, /No API key required/);
  assert.match(mimoHtml, /MiMo Real LLM/);
  assert.match(mimoHtml, /MIMO_API_KEY/);
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

test("frontend API client loads history and structured endpoints", async () => {
  const originalFetch = globalThis.fetch;
  const requestedUrls: string[] = [];
  globalThis.fetch = async (input) => {
    const url = String(input);
    requestedUrls.push(url);
    if (url.endsWith("/findings")) {
      return new Response(JSON.stringify({ task_id: "task-1", findings: structuredFindings }));
    }
    if (url.endsWith("/agent-states")) {
      return new Response(JSON.stringify({ task_id: "task-1", agents: structuredAgents }));
    }
    return new Response(JSON.stringify([completedReview]));
  };

  try {
    const history = await listReviews(10);
    const findings = await getReviewFindings("task-1");
    const agents = await getReviewAgentStates("task-1");
    assert.equal(history[0].task_id, "task-1");
    assert.equal(findings.findings[0].title, "Boundary risk");
    assert.equal(agents.agents[0].agent_id, "ArchitectureAgent");
    assert.ok(requestedUrls.some((url) => /\/api\/reviews\?limit=10$/.test(url)));
    assert.ok(requestedUrls.some((url) => /\/api\/reviews\/task-1\/findings$/.test(url)));
    assert.ok(requestedUrls.some((url) => /\/api\/reviews\/task-1\/agent-states$/.test(url)));
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("frontend API client handles DELETE 204 without parsing a body", async () => {
  const originalFetch = globalThis.fetch;
  let requestedMethod = "";
  let requestedUrl = "";
  globalThis.fetch = async (input, init) => {
    requestedUrl = String(input);
    requestedMethod = init?.method || "";
    return new Response(null, { status: 204 });
  };

  try {
    await deleteReview("task-1");
    assert.equal(requestedMethod, "DELETE");
    assert.match(requestedUrl, /\/api\/reviews\/task-1$/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("Start review preserves MiMo mode in the request", async () => {
  const originalFetch = globalThis.fetch;
  let sentBody: Record<string, unknown> = {};
  globalThis.fetch = async (_url, init) => {
    sentBody = JSON.parse(init?.body as string || "{}");
    return new Response(JSON.stringify({ task_id: "task-mimo", llm_mode: "mimo" }), { status: 202 });
  };

  try {
    const result = await createReview("https://github.com/example/project", "mimo");
    assert.equal(result.llm_mode, "mimo");
    assert.equal(sentBody.llm_mode, "mimo");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("missing MiMo key error remains visible to the client", async () => {
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

test("runtime timeline shows A1 through A4 with an obvious running step", () => {
  const html = renderToStaticMarkup(<AgentTimeline agents={[]} progress={runningProgress} />);

  assert.equal((html.match(/data-agent-step=/g) || []).length, 4);
  assert.ok(html.indexOf("ArchitectureAgent") < html.indexOf("CodeSmellAgent"));
  assert.ok(html.indexOf("CodeSmellAgent") < html.indexOf("MaintainabilityAgent"));
  assert.ok(html.indexOf("MaintainabilityAgent") < html.indexOf("RefactorAgent"));
  assert.match(html, /data-status="running"/);
  assert.match(html, /aria-current="step"/);
});

test("failed agent state is visible in timeline and structured cards", () => {
  const timeline = renderToStaticMarkup(<AgentTimeline agents={structuredAgents} progress={null} />);
  const cards = renderToStaticMarkup(<AgentStateCards agents={structuredAgents} />);

  assert.match(timeline, /data-agent-step="CodeSmellAgent"/);
  assert.match(timeline, /data-status="failed"/);
  assert.match(cards, /data-agent-card="CodeSmellAgent"/);
  assert.match(cards, /Agent execution failed/);
});

test("agent cards render from structured agent-state objects", () => {
  const html = renderToStaticMarkup(<AgentStateCards agents={structuredAgents} />);

  assert.equal((html.match(/data-agent-card=/g) || []).length, 4);
  assert.match(html, /92%/);
  assert.match(html, /Severity/);
});

test("findings and severity badges render from structured findings", () => {
  const html = renderToStaticMarkup(
    <FindingsPanel
      error={null}
      findings={structuredFindings}
      loading={false}
      onRetry={() => undefined}
    />
  );

  assert.match(html, /data-structured-findings/);
  assert.match(html, /Boundary risk/);
  assert.match(html, /data-severity="high"/);
  assert.match(html, /src\/app\.py/);
  assert.match(html, /Separate transport/);
});

test("findings panel renders useful fields when available", () => {
  const html = renderToStaticMarkup(
    <FindingsPanel
      error={null}
      findings={structuredFindings}
      loading={false}
      onRetry={() => undefined}
    />
  );

  assert.match(html, /Changes to this boundary may affect multiple consumers/);
  assert.match(html, /Add characterization tests before restructuring/);
  assert.match(html, /tests\/test_blueprints\.py/);
  assert.match(html, /tests\/test_basic\.py/);
  assert.match(html, /Public API; preserve backward compatibility/);
});

test("findings panel does not render empty useful field labels", () => {
  const minimalFindings: ReviewFindingItem[] = [
    {
      finding_id: "finding-minimal",
      finding_index: 0,
      section: "Code Smells",
      title: "Simple finding",
      description: "A simple finding.",
      severity: "low",
      category: null,
      confidence: 0.5,
      recommendation: null,
      files: [],
      evidence_ids: [],
      evidence_refs: [],
      validation_status: "validated",
      impact: null,
      first_step: null,
      validation_tests: [],
      confidence_rationale: null,
      caveat: null
    }
  ];

  const html = renderToStaticMarkup(
    <FindingsPanel
      error={null}
      findings={minimalFindings}
      loading={false}
      onRetry={() => undefined}
    />
  );

  assert.doesNotMatch(html, /Impact/);
  assert.doesNotMatch(html, /First safe step/);
  assert.doesNotMatch(html, /Validation tests/);
  assert.doesNotMatch(html, /Caveat/);
});

test("evidence IDs render from structured finding evidence references", () => {
  const html = renderToStaticMarkup(
    <EvidencePanel
      error={null}
      findings={structuredFindings}
      loading={false}
      onRetry={() => undefined}
    />
  );

  assert.match(html, /data-structured-evidence/);
  assert.match(html, /data-evidence-id="E123"/);
  assert.match(html, /src\/app\.py:10-24/);
  assert.match(html, /build_app/);
});

test("Report tab still renders Markdown content and an outline", () => {
  const html = renderToStaticMarkup(
    <ReportRenderer isRunning={false} reportMarkdown={completedReview.report_markdown} />
  );

  assert.match(html, /Report section navigation/);
  assert.match(html, /Review complete/);
  assert.match(html, /Stable boundaries/);
  assert.doesNotMatch(html, /data-agent-card=/);
});

test("old report fallback renders without structured data or agent summaries", () => {
  const report = renderToStaticMarkup(
    <ReportRenderer
      isRunning={false}
      reportMarkdown="# Architecture Summary\nLegacy architecture remains visible."
    />
  );
  const agents = renderToStaticMarkup(<AgentStateCards agents={[]} />);

  assert.match(report, /Legacy architecture remains visible/);
  assert.match(agents, /predates persisted agent summaries/);
});

test("completed v3 review renders four real agent states, not pending placeholders", () => {
  const html = renderToStaticMarkup(<AgentTimeline agents={structuredAgents} progress={null} />);

  assert.equal((html.match(/data-agent-step=/g) || []).length, 4);
  assert.match(html, /data-status="completed"/);
  assert.doesNotMatch(html, /data-status="pending"/);
  assert.match(html, /ArchitectureAgent/);
  assert.match(html, /CodeSmellAgent/);
  assert.match(html, /MaintainabilityAgent/);
  assert.match(html, /RefactorAgent/);
});

const failedAgentStates: ReviewAgentStateItem[] = [
  {
    order: 1,
    agent_id: "ArchitectureAgent",
    label: "A1 ArchitectureAgent",
    status: "completed",
    findings_count: 1,
    evidence_count: 2,
    severity_mix: { critical: 0, high: 1, medium: 0, low: 0 },
    average_confidence: 0.92,
    error: null
  },
  {
    order: 2,
    agent_id: "CodeSmellAgent",
    label: "A2 CodeSmellAgent",
    status: "failed",
    findings_count: 0,
    evidence_count: 0,
    severity_mix: { critical: 0, high: 0, medium: 0, low: 0 },
    average_confidence: null,
    error: "LLM read timeout after 180s"
  },
  {
    order: 3,
    agent_id: "MaintainabilityAgent",
    label: "A3 MaintainabilityAgent",
    status: "skipped",
    findings_count: 0,
    evidence_count: 0,
    severity_mix: { critical: 0, high: 0, medium: 0, low: 0 },
    average_confidence: null,
    error: null
  },
  {
    order: 4,
    agent_id: "RefactorAgent",
    label: "A4 RefactorAgent",
    status: "skipped",
    findings_count: 0,
    evidence_count: 0,
    severity_mix: { critical: 0, high: 0, medium: 0, low: 0 },
    average_confidence: null,
    error: null
  }
];

test("failed review shows completed and failed agents, not all pending", () => {
  const html = renderToStaticMarkup(<AgentTimeline agents={failedAgentStates} progress={null} />);

  assert.equal((html.match(/data-agent-step=/g) || []).length, 4);
  assert.match(html, /data-status="completed"/);
  assert.match(html, /data-status="failed"/);
  assert.match(html, /data-status="skipped"/);
  assert.doesNotMatch(html, /data-status="pending"/);
});

test("failed review agent cards show error detail", () => {
  const html = renderToStaticMarkup(<AgentStateCards agents={failedAgentStates} />);

  assert.match(html, /data-agent-card="CodeSmellAgent"/);
  assert.match(html, /LLM read timeout/);
  assert.match(html, /data-agent-card="ArchitectureAgent"/);
});

test("light and dark theme helpers toggle the root class and persist preference", () => {
  let dark = false;
  let persisted = "";
  const root = {
    classList: {
      toggle: (_name: string, enabled?: boolean) => {
        dark = Boolean(enabled);
        return dark;
      }
    }
  };
  const storage = {
    setItem: (_key: string, value: string) => {
      persisted = value;
    }
  };

  assert.equal(nextTheme("light"), "dark");
  applyTheme("dark", root as Pick<HTMLElement, "classList">, storage);
  assert.equal(dark, true);
  assert.equal(persisted, "dark");
  assert.match(renderToStaticMarkup(<ThemeToggle />), /Switch to dark theme/);
});

test("route loading and error states remain actionable", () => {
  const loadingHtml = renderToStaticMarkup(<Loading />);
  const errorHtml = renderToStaticMarkup(
    <ErrorPage error={new Error("render failed")} reset={() => undefined} />
  );

  assert.match(loadingHtml, /Loading CodePilot workspace/);
  assert.match(errorHtml, /could not render this page/);
  assert.match(errorHtml, /Retry/);
});
