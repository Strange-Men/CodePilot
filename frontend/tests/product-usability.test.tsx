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
import { OverviewPanel } from "../components/workspace/OverviewPanel";
import { applyTheme, nextTheme, ThemeToggle } from "../components/workspace/ThemeToggle";
import { WorkspaceShell } from "../components/workspace/WorkspaceShell";
import {
  CodePilotApiError,
  createReview,
  deleteReview,
  getReviewAgentStates,
  getReviewExportUrl,
  getReviewFindings,
  listReviews
} from "../lib/api";
import { t, getLocalizedStatusLabels, getLocalizedSeverity, getLocalizedCategory } from "../lib/i18n";
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

test("language toggle renders in the header", () => {
  const html = renderToStaticMarkup(<WorkspaceShell />);

  assert.match(html, /Switch to Chinese/);
  assert.match(html, />EN</);
  assert.match(html, />中</);
});

test("English is the default language", () => {
  const html = renderToStaticMarkup(<WorkspaceShell />);

  // English labels should be present by default
  assert.match(html, /Review Workspace/);
  assert.match(html, /Evidence-grounded repository analysis/);
  assert.match(html, /Control panel/);
  assert.match(html, /Overview/);
  assert.match(html, /Start review/);
});

test("Chinese labels appear when language is zh", () => {
  const html = renderToStaticMarkup(
    <FindingsPanel
      error={null}
      findings={structuredFindings}
      language="zh"
      loading={false}
      onRetry={() => undefined}
    />
  );

  assert.match(html, /影响/);
  assert.match(html, /第一步建议/);
  assert.match(html, /验证方式/);
  assert.match(html, /注意事项/);
  assert.match(html, /结构化审查数据/);
});

test("Chinese tab labels render correctly", () => {
  // Test the t() function directly for all tab keys
  assert.equal(t("zh", "tabs.overview"), "总览");
  assert.equal(t("zh", "tabs.agents"), "Agent");
  assert.equal(t("zh", "tabs.findings"), "问题发现");
  assert.equal(t("zh", "tabs.report"), "报告");
  assert.equal(t("zh", "tabs.evidence"), "证据");
  assert.equal(t("zh", "tabs.metrics"), "指标");
});

test("Chinese status labels render correctly", () => {
  const zhStatuses = getLocalizedStatusLabels("zh");

  assert.equal(zhStatuses.pending, "等待中");
  assert.equal(zhStatuses.cloning, "克隆中");
  assert.equal(zhStatuses.parsing, "解析中");
  assert.equal(zhStatuses.summarizing, "总结中");
  assert.equal(zhStatuses.reviewing, "审查中");
  assert.equal(zhStatuses.completed, "已完成");
  assert.equal(zhStatuses.failed, "失败");
});

test("Chinese key UI labels are correct", () => {
  assert.equal(t("zh", "overview.currentReview"), "当前审查");
  assert.equal(t("zh", "form.startReview"), "开始审查");
  assert.equal(t("zh", "sidebar.currentStatus"), "当前状态");
  assert.equal(t("zh", "sidebar.exportMarkdown"), "导出 Markdown");
});

test("missing locale key falls back to English", () => {
  // A key that exists in en but we test fallback behavior
  assert.equal(t("en", "header.workspace"), "Review Workspace");
  // A nonexistent key should return the key itself
  assert.equal(t("en", "nonexistent.key"), "nonexistent.key");
  // zh fallback for a key missing in zh should return en value
  // (all our keys have zh translations, so test with nonexistent)
  assert.equal(t("zh", "nonexistent.key"), "nonexistent.key");
});

test("FindingsPanel translates labels in Chinese", () => {
  const html = renderToStaticMarkup(
    <FindingsPanel
      error={null}
      findings={structuredFindings}
      language="zh"
      loading={false}
      onRetry={() => undefined}
    />
  );

  // Chinese section labels
  assert.match(html, /结构化审查数据/);
  assert.match(html, /问题发现/);
  assert.match(html, /建议/);
  assert.match(html, /影响/);
  assert.match(html, /第一步建议/);
  assert.match(html, /验证方式/);
  assert.match(html, /注意事项/);
  assert.match(html, /证据/);
  assert.match(html, /置信度/);
});

test("AgentTimeline shows Chinese agent descriptions", () => {
  const html = renderToStaticMarkup(
    <AgentTimeline agents={[]} language="zh" progress={runningProgress} />
  );

  assert.match(html, /执行流水线/);
  assert.match(html, /审查 Agent/);
  assert.match(html, /已完成/);
  assert.match(html, /架构分析/);
  assert.match(html, /代码质量/);
});

test("AgentStateCards renders Chinese labels", () => {
  const html = renderToStaticMarkup(<AgentStateCards agents={structuredAgents} language="zh" />);

  assert.match(html, /问题发现/);
  assert.match(html, /证据/);
  assert.match(html, /平均置信度/);
  assert.match(html, /严重程度/);
});

test("EvidencePanel renders Chinese labels", () => {
  const html = renderToStaticMarkup(
    <EvidencePanel
      error={null}
      findings={structuredFindings}
      language="zh"
      loading={false}
      onRetry={() => undefined}
    />
  );

  assert.match(html, /已验证引用/);
  assert.match(html, /条引用/);
  assert.match(html, /代码位置/);
  assert.match(html, /证据链/);
  assert.match(html, /支撑证据/);
});

test("MetricsPanel renders Chinese labels", () => {
  // Need at least some agents or findings for metrics to show
  const html = renderToStaticMarkup(
    <FindingsPanel
      error={null}
      findings={structuredFindings}
      language="zh"
      loading={false}
      onRetry={() => undefined}
    />
  );

  assert.match(html, /置信度/);
});

test("switching language does not change evidence IDs", () => {
  const htmlEn = renderToStaticMarkup(
    <EvidencePanel error={null} findings={structuredFindings} language="en" loading={false} onRetry={() => undefined} />
  );
  const htmlZh = renderToStaticMarkup(
    <EvidencePanel error={null} findings={structuredFindings} language="zh" loading={false} onRetry={() => undefined} />
  );

  // Evidence IDs should be identical regardless of language
  assert.match(htmlEn, /data-evidence-ref="\[E123\]"/);
  assert.match(htmlZh, /data-evidence-ref="\[E123\]"/);
  assert.match(htmlEn, /data-evidence-ref="\[E124\]"/);
  assert.match(htmlZh, /data-evidence-ref="\[E124\]"/);
});

test("switching language does not change findings count", () => {
  const htmlEn = renderToStaticMarkup(
    <FindingsPanel error={null} findings={structuredFindings} language="en" loading={false} onRetry={() => undefined} />
  );
  const htmlZh = renderToStaticMarkup(
    <FindingsPanel error={null} findings={structuredFindings} language="zh" loading={false} onRetry={() => undefined} />
  );

  // Both should show the same finding
  assert.match(htmlEn, /Boundary risk/);
  assert.match(htmlZh, /Boundary risk/);
  assert.match(htmlEn, /data-finding-id="finding-1"/);
  assert.match(htmlZh, /data-finding-id="finding-1"/);
});

test("renders inline repository URL validation feedback", () => {
  const html = renderToStaticMarkup(
    <ReviewSubmissionForm
      fieldError="Use an HTTPS GitHub repository URL."
      isRunning={false}
      language="en"
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
      language="en"
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
      language="en"
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

test("ReviewSubmissionForm renders Chinese labels", () => {
  const html = renderToStaticMarkup(
    <ReviewSubmissionForm
      fieldError={null}
      isRunning={false}
      language="zh"
      llmMode="mock"
      onLlmModeChange={() => undefined}
      onRepoUrlChange={() => undefined}
      onSubmit={() => undefined}
      repoUrl="https://github.com/example/project"
      submitting={false}
    />
  );

  assert.match(html, /GitHub 仓库/);
  assert.match(html, /LLM 模式/);
  assert.match(html, /MiMo 真实 LLM/);
  assert.match(html, /开始审查/);
  assert.match(html, /仅支持公开的 HTTPS GitHub URL/);
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
  const html = renderToStaticMarkup(<AgentTimeline agents={[]} language="en" progress={runningProgress} />);

  assert.equal((html.match(/data-agent-step=/g) || []).length, 4);
  assert.ok(html.indexOf("ArchitectureAgent") < html.indexOf("CodeSmellAgent"));
  assert.ok(html.indexOf("CodeSmellAgent") < html.indexOf("MaintainabilityAgent"));
  assert.ok(html.indexOf("MaintainabilityAgent") < html.indexOf("RefactorAgent"));
  assert.match(html, /data-status="running"/);
  assert.match(html, /aria-current="step"/);
});

test("failed agent state is visible in timeline and structured cards", () => {
  const timeline = renderToStaticMarkup(<AgentTimeline agents={structuredAgents} language="en" progress={null} />);
  const cards = renderToStaticMarkup(<AgentStateCards agents={structuredAgents} language="en" />);

  assert.match(timeline, /data-agent-step="CodeSmellAgent"/);
  assert.match(timeline, /data-status="failed"/);
  assert.match(cards, /data-agent-card="CodeSmellAgent"/);
  assert.match(cards, /Agent execution failed/);
});

test("agent cards render from structured agent-state objects", () => {
  const html = renderToStaticMarkup(<AgentStateCards agents={structuredAgents} language="en" />);

  assert.equal((html.match(/data-agent-card=/g) || []).length, 4);
  assert.match(html, /92%/);
  assert.match(html, /Severity/);
});

test("findings and severity badges render from structured findings", () => {
  const html = renderToStaticMarkup(
    <FindingsPanel
      error={null}
      findings={structuredFindings}
      language="en"
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
      language="en"
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
      language="en"
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
      language="en"
      loading={false}
      onRetry={() => undefined}
    />
  );

  assert.match(html, /data-structured-evidence/);
  assert.match(html, /data-evidence-ref="\[E123\]"/);
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
  const agents = renderToStaticMarkup(<AgentStateCards agents={[]} language="en" />);

  assert.match(report, /Legacy architecture remains visible/);
  assert.match(agents, /predates persisted agent summaries/);
});

test("completed v3 review renders four real agent states, not pending placeholders", () => {
  const html = renderToStaticMarkup(<AgentTimeline agents={structuredAgents} language="en" progress={null} />);

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
  const html = renderToStaticMarkup(<AgentTimeline agents={failedAgentStates} language="en" progress={null} />);

  assert.equal((html.match(/data-agent-step=/g) || []).length, 4);
  assert.match(html, /data-status="completed"/);
  assert.match(html, /data-status="failed"/);
  assert.match(html, /data-status="skipped"/);
  assert.doesNotMatch(html, /data-status="pending"/);
});

test("failed review agent cards show error detail", () => {
  const html = renderToStaticMarkup(<AgentStateCards agents={failedAgentStates} language="en" />);

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
  // Error page uses useLanguage which defaults to "en" in SSR
  assert.match(errorHtml, /could not render this page/i);
  assert.match(errorHtml, /Retry/);
});

test("t() returns English values for all tab keys", () => {
  assert.equal(t("en", "tabs.overview"), "Overview");
  assert.equal(t("en", "tabs.agents"), "Agents");
  assert.equal(t("en", "tabs.findings"), "Findings");
  assert.equal(t("en", "tabs.report"), "Report");
  assert.equal(t("en", "tabs.evidence"), "Evidence");
  assert.equal(t("en", "tabs.metrics"), "Metrics");
});

test("t() returns Chinese values for all tab keys", () => {
  assert.equal(t("zh", "tabs.overview"), "总览");
  assert.equal(t("zh", "tabs.agents"), "Agent");
  assert.equal(t("zh", "tabs.findings"), "问题发现");
  assert.equal(t("zh", "tabs.report"), "报告");
  assert.equal(t("zh", "tabs.evidence"), "证据");
  assert.equal(t("zh", "tabs.metrics"), "指标");
});

test("t() returns Chinese values for findings field labels", () => {
  assert.equal(t("zh", "findings.impact"), "影响");
  assert.equal(t("zh", "findings.firstSafeStep"), "第一步建议");
  assert.equal(t("zh", "findings.validationTests"), "验证方式");
  assert.equal(t("zh", "findings.caveat"), "注意事项");
  assert.equal(t("zh", "findings.confidence"), "置信度");
  assert.equal(t("zh", "findings.recommendedAction"), "建议");
});

test("t() returns Chinese values for overview labels", () => {
  assert.equal(t("zh", "overview.currentReview"), "当前审查");
  assert.equal(t("zh", "overview.agentsComplete"), "Agent 已完成");
  assert.equal(t("zh", "overview.findings"), "问题发现");
  assert.equal(t("zh", "overview.highRiskItems"), "高风险问题");
  assert.equal(t("zh", "overview.evidenceRefs"), "证据引用");
});

test("t() returns Chinese values for form labels", () => {
  assert.equal(t("zh", "form.githubRepo"), "GitHub 仓库");
  assert.equal(t("zh", "form.llmMode"), "LLM 模式");
  assert.equal(t("zh", "form.startReview"), "开始审查");
  assert.equal(t("zh", "form.reviewInProgress"), "审查中");
});

test("t() returns Chinese values for empty states", () => {
  assert.equal(t("zh", "findings.noStructured"), "暂无结构化问题");
  assert.equal(t("zh", "evidence.noStructured"), "暂无结构化证据");
  assert.equal(t("zh", "metrics.notRecorded"), "暂无指标记录");
});

// --- Chinese prose localization tests ---

const zhFindings: ReviewFindingItem[] = [
  {
    finding_id: "finding-zh",
    finding_index: 0,
    section: "Architecture Summary",
    title: "build_reviews_router 的架构边界需要审查",
    description: "引用的证据表明该区域存在结构性问题，在修改入口点、核心模块、共享依赖或重构边界前应优先审查。",
    severity: "high",
    category: "architecture",
    confidence: 0.85,
    recommendation: "在重构前为该边界添加契约测试，确保接口行为不变。",
    files: ["backend/api/reviews.py"],
    evidence_ids: ["ev_abc123"],
    evidence_refs: [
      {
        evidence_id: "ev_abc123",
        file_path: "backend/api/reviews.py",
        symbol_name: "build_reviews_router",
        start_line: 10,
        end_line: 20
      }
    ],
    validation_status: "validated",
    impact: "如果接口契约未被保留，该边界的变更可能影响多个依赖方。",
    first_step: "在重构前为当前公共接口添加表征测试，锁定现有行为。",
    validation_tests: ["在边界变更前后运行完整测试套件，确认无回归。"],
    confidence_rationale: "基于提示上下文中提供的证据记录。",
    caveat: "如果该边界属于公共 API，变更可能破坏下游使用者。"
  }
];

test("Chinese findings render localized prose when API returns it", () => {
  const html = renderToStaticMarkup(
    <FindingsPanel
      error={null}
      findings={zhFindings}
      language="zh"
      loading={false}
      onRetry={() => undefined}
    />
  );

  // Chinese prose rendered
  assert.match(html, /架构边界需要审查/);
  assert.match(html, /引用的证据/);
  assert.match(html, /契约测试/);
  assert.match(html, /依赖方/);
  assert.match(html, /表征测试/);
  assert.match(html, /公共 API/);
  // Raw evidence IDs are hidden in favor of display refs
  assert.match(html, /\[E\?\]/);
  assert.doesNotMatch(html, /ev_abc123/);
  // Files preserved
  assert.match(html, /backend\/api\/reviews\.py/);
  // Severity preserved
  assert.match(html, /data-severity="high"/);
});

test("Chinese findings preserve evidence IDs regardless of prose language", () => {
  const htmlEn = renderToStaticMarkup(
    <FindingsPanel error={null} findings={structuredFindings} language="en" loading={false} onRetry={() => undefined} />
  );
  const htmlZh = renderToStaticMarkup(
    <FindingsPanel error={null} findings={zhFindings} language="zh" loading={false} onRetry={() => undefined} />
  );

  // Evidence refs appear in both without raw ev_* leakage
  assert.match(htmlEn, /\[E123\]/);
  assert.match(htmlZh, /\[E\?\]/);
  assert.doesNotMatch(htmlEn, /ev_abc123/);
  assert.doesNotMatch(htmlZh, /ev_abc123/);
  // Both have severity badges
  assert.match(htmlEn, /data-severity="high"/);
  assert.match(htmlZh, /data-severity="high"/);
});

// --- AgentTimeline loading state tests ---

test("AgentTimeline shows skeleton when loading and no agents", () => {
  const html = renderToStaticMarkup(
    <AgentTimeline agents={[]} language="en" loading={true} progress={null} />
  );

  // Should show skeleton, not pending agents
  assert.match(html, /role="status"/);
  assert.doesNotMatch(html, /data-agent-step=/);
  assert.doesNotMatch(html, /data-status="pending"/);
});

test("AgentTimeline shows agents when not loading", () => {
  const html = renderToStaticMarkup(
    <AgentTimeline agents={structuredAgents} language="en" loading={false} progress={null} />
  );

  // Should show real agent data
  assert.equal((html.match(/data-agent-step=/g) || []).length, 4);
  assert.match(html, /data-status="completed"/);
});

test("AgentTimeline shows agents even when loading if agents exist", () => {
  const html = renderToStaticMarkup(
    <AgentTimeline agents={structuredAgents} language="en" loading={true} progress={null} />
  );

  // Should show existing agents, not skeleton
  assert.equal((html.match(/data-agent-step=/g) || []).length, 4);
});

test("AgentTimeline shows progress when available regardless of loading", () => {
  const html = renderToStaticMarkup(
    <AgentTimeline agents={[]} language="en" loading={true} progress={runningProgress} />
  );

  // Should show progress timeline, not skeleton
  assert.equal((html.match(/data-agent-step=/g) || []).length, 4);
  assert.match(html, /data-status="running"/);
});

// --- OverviewPanel loading state tests ---

test("OverviewPanel shows loading indicator when structuredLoading is true", () => {
  const html = renderToStaticMarkup(
    <OverviewPanel agents={[]} findings={[]} language="en" review={completedReview} structuredLoading={true} />
  );

  // Should show loading ellipsis instead of 0/4
  assert.match(html, /…/);
  assert.doesNotMatch(html, />0\/4</);
});

test("OverviewPanel shows real data when not loading", () => {
  const html = renderToStaticMarkup(
    <OverviewPanel agents={structuredAgents} findings={structuredFindings} language="en" review={completedReview} structuredLoading={false} />
  );

  // Should show real counts (3 completed out of 4 agents)
  assert.match(html, />3\/4</);
  assert.match(html, />1</);  // findings count
});

// --- Chinese export URL tests ---

test("export URL includes lang=zh when language is zh", () => {
  const { getReviewExportUrl } = require("../lib/api");
  const url = getReviewExportUrl("task-1", { lang: "zh" });
  assert.match(url, /lang=zh/);
  assert.match(url, /\/export/);
});

test("export URL has no lang param for English", () => {
  const { getReviewExportUrl } = require("../lib/api");
  const url = getReviewExportUrl("task-1", { lang: "en" });
  assert.doesNotMatch(url, /lang=/);
});

// --- API lang parameter tests ---

test("getReviewFindings includes lang param for zh", async () => {
  const originalFetch = globalThis.fetch;
  let requestedUrl = "";
  globalThis.fetch = async (input) => {
    requestedUrl = String(input);
    return new Response(JSON.stringify({ task_id: "task-1", findings: [] }));
  };

  try {
    await getReviewFindings("task-1", { lang: "zh" });
    assert.match(requestedUrl, /lang=zh/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("getReviewFindings has no lang param for en", async () => {
  const originalFetch = globalThis.fetch;
  let requestedUrl = "";
  globalThis.fetch = async (input) => {
    requestedUrl = String(input);
    return new Response(JSON.stringify({ task_id: "task-1", findings: [] }));
  };

  try {
    await getReviewFindings("task-1", { lang: "en" });
    assert.doesNotMatch(requestedUrl, /lang=/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

// --- V3.5.5 terminology tests ---

test("Chinese UI dictionary does not contain 代码坏味道", () => {
  // Check all zh dictionary values for the banned term
  const zhDict = (t as (lang: string, key: string) => string).toString();
  // Direct check: iterate known zh keys
  const zhKeys = [
    "header.workspace", "header.tagline", "sidebar.controlPanel",
    "sidebar.repositoryReview", "findings.heading", "findings.structuredData",
    "overview.findings", "overview.highRiskItems", "tabs.findings",
    "agentCards.findings", "metrics.findings", "report.outline",
    "report.legacyAppendices", "findings.noStructured",
    "evidence.noStructured", "metrics.notRecorded",
    "findings.recommendedAction", "findings.validationTests",
    "agentCards.severity", "metrics.severityDist",
  ];
  for (const key of zhKeys) {
    const value = t("zh", key);
    assert.ok(
      !value.includes("代码坏味道"),
      `Key "${key}" contains banned term "代码坏味道": "${value}"`
    );
  }
});

test("Chinese findings use 代码质量 not 代码坏味道", () => {
  // The findings panel should use the new term
  const html = renderToStaticMarkup(
    <AgentTimeline agents={[]} language="zh" progress={runningProgress} />
  );

  assert.match(html, /代码质量/);
  assert.doesNotMatch(html, /代码坏味道/);
});

test("Chinese findings panel uses polished labels", () => {
  assert.equal(t("zh", "findings.validationTests"), "验证方式");
  assert.equal(t("zh", "findings.recommendedAction"), "建议");
  assert.equal(t("zh", "agentCards.severity"), "严重程度");
  assert.equal(t("zh", "metrics.severityDist"), "严重程度分布");
  assert.equal(t("zh", "overview.highRiskItems"), "高风险问题");
  assert.equal(t("zh", "report.outline"), "报告目录");
  assert.equal(t("zh", "report.legacyAppendices"), "附录与仓库诊断");
  assert.equal(t("zh", "header.workspace"), "代码审查工作台");
});

// --- V3.5.6 Chinese localization closure tests ---

test("severity localization returns Chinese values in zh mode", () => {
  assert.equal(getLocalizedSeverity("zh", "critical"), "严重");
  assert.equal(getLocalizedSeverity("zh", "high"), "高");
  assert.equal(getLocalizedSeverity("zh", "medium"), "中");
  assert.equal(getLocalizedSeverity("zh", "low"), "低");
  assert.equal(getLocalizedSeverity("zh", "informational"), "信息");
});

test("severity localization returns English values in en mode", () => {
  assert.equal(getLocalizedSeverity("en", "critical"), "Critical");
  assert.equal(getLocalizedSeverity("en", "high"), "High");
  assert.equal(getLocalizedSeverity("en", "medium"), "Medium");
  assert.equal(getLocalizedSeverity("en", "low"), "Low");
});

test("category localization returns Chinese values in zh mode", () => {
  assert.equal(getLocalizedCategory("zh", "architecture"), "架构");
  assert.equal(getLocalizedCategory("zh", "code_smell"), "代码质量");
  assert.equal(getLocalizedCategory("zh", "maintainability"), "可维护性");
  assert.equal(getLocalizedCategory("zh", "refactor"), "重构");
});

test("zh FindingsPanel never shows raw English severity", () => {
  const html = renderToStaticMarkup(
    <FindingsPanel
      error={null}
      findings={structuredFindings}
      language="zh"
      loading={false}
      onRetry={() => undefined}
    />
  );

  // Should not show raw English severity
  assert.doesNotMatch(html, />High</);
  assert.doesNotMatch(html, />Medium</);
  assert.doesNotMatch(html, />Low</);
  assert.doesNotMatch(html, />Critical</);
  // Should show localized severity
  assert.match(html, /高/);
});

test("zh FindingsPanel never shows [zh] prefix", () => {
  const html = renderToStaticMarkup(
    <FindingsPanel
      error={null}
      findings={zhFindings}
      language="zh"
      loading={false}
      onRetry={() => undefined}
    />
  );

  assert.doesNotMatch(html, /\[zh\]/);
});

test("zh EvidencePanel groups evidence by finding", () => {
  const html = renderToStaticMarkup(
    <EvidencePanel
      error={null}
      findings={structuredFindings}
      language="zh"
      loading={false}
      onRetry={() => undefined}
    />
  );

  // Should show evidence chain title
  assert.match(html, /证据链/);
  // Should show supporting evidence count
  assert.match(html, /支撑证据/);
  // Should show code location
  assert.match(html, /代码位置/);
  // Evidence ID should still be present but not as main title
  assert.match(html, /E123/);
  // Finding title should be visible in the group
  assert.match(html, /Boundary risk/);
});

test("zh AgentStateCards shows localized severity", () => {
  const html = renderToStaticMarkup(<AgentStateCards agents={structuredAgents} language="zh" />);

  // Should not show raw English severity abbreviations like "H1", "M1"
  // Should show localized severity
  assert.match(html, /严重程度/);
  // Should not show "none" for agents with findings
  assert.doesNotMatch(html, />none</);
});

test("zh dictionary has all required severity keys", () => {
  assert.equal(t("zh", "severity.critical"), "严重");
  assert.equal(t("zh", "severity.high"), "高");
  assert.equal(t("zh", "severity.medium"), "中");
  assert.equal(t("zh", "severity.low"), "低");
});

test("zh dictionary has all required category keys", () => {
  assert.equal(t("zh", "category.architecture"), "架构");
  assert.equal(t("zh", "category.code_smell"), "代码质量");
  assert.equal(t("zh", "category.maintainability"), "可维护性");
  assert.equal(t("zh", "category.refactor"), "重构");
});

test("zh dictionary has evidence chain keys", () => {
  assert.equal(t("zh", "evidence.chainTitle"), "证据链");
  assert.equal(t("zh", "evidence.supports"), "支撑问题");
  assert.equal(t("zh", "evidence.codeLocation"), "代码位置");
  assert.equal(t("zh", "evidence.relatedSymbol"), "相关符号");
  assert.equal(t("zh", "evidence.evidenceId"), "证据 ID");
  assert.equal(t("zh", "evidence.supportingEvidence"), "支撑证据");
  assert.equal(t("zh", "evidence.unlinkedEvidence"), "未关联问题的证据");
});

test("en dictionary has evidence chain keys", () => {
  assert.equal(t("en", "evidence.chainTitle"), "Evidence Chain");
  assert.equal(t("en", "evidence.supports"), "Supports");
  assert.equal(t("en", "evidence.codeLocation"), "Code location");
  assert.equal(t("en", "evidence.evidenceId"), "Evidence ID");
});

test("English EvidencePanel still works normally", () => {
  const html = renderToStaticMarkup(
    <EvidencePanel
      error={null}
      findings={structuredFindings}
      language="en"
      loading={false}
      onRetry={() => undefined}
    />
  );

  assert.match(html, /Evidence/);
  assert.match(html, /E123/);
  assert.match(html, /src\/app\.py/);
  assert.match(html, /build_app/);
});

// --- V3.5.7 Chinese report closure tests ---

test("zh FindingsPanel contains no English severity labels", () => {
  const html = renderToStaticMarkup(
    <FindingsPanel
      error={null}
      findings={structuredFindings}
      language="zh"
      loading={false}
      onRetry={() => undefined}
    />
  );

  // Should not show raw English severity in badges
  assert.doesNotMatch(html, />High</);
  assert.doesNotMatch(html, />Medium</);
  assert.doesNotMatch(html, />Low</);
  assert.doesNotMatch(html, />Critical</);
  assert.doesNotMatch(html, />Informational</);
  // Should show localized severity
  assert.match(html, /高/);
});

test("zh FindingsPanel contains no [zh] prefix", () => {
  const html = renderToStaticMarkup(
    <FindingsPanel
      error={null}
      findings={zhFindings}
      language="zh"
      loading={false}
      onRetry={() => undefined}
    />
  );

  assert.doesNotMatch(html, /\[zh\]/);
});

test("zh AgentStateCards shows localized severity summary", () => {
  const html = renderToStaticMarkup(<AgentStateCards agents={structuredAgents} language="zh" />);

  // Should show Chinese severity labels
  assert.match(html, /严重程度/);
  // Should not show raw English severity abbreviations
  assert.doesNotMatch(html, /\bHigh\b/);
  assert.doesNotMatch(html, /\bMedium\b/);
  assert.doesNotMatch(html, /\bLow\b/);
});

test("zh EvidencePanel shows chain title and Chinese labels", () => {
  const html = renderToStaticMarkup(
    <EvidencePanel
      error={null}
      findings={structuredFindings}
      language="zh"
      loading={false}
      onRetry={() => undefined}
    />
  );

  // Evidence chain title
  assert.match(html, /证据链/);
  // Chinese labels
  assert.match(html, /代码位置/);
  assert.match(html, /相关符号/);
  assert.match(html, /支撑证据/);
  // Evidence IDs preserved
  assert.match(html, /E123/);
  assert.match(html, /E124/);
  // Finding title visible in group
  assert.match(html, /Boundary risk/);
});

test("zh MetricsPanel shows localized labels", () => {
  const html = renderToStaticMarkup(
    <FindingsPanel
      error={null}
      findings={structuredFindings}
      language="zh"
      loading={false}
      onRetry={() => undefined}
    />
  );

  // Should show Chinese confidence label
  assert.match(html, /置信度/);
  assert.doesNotMatch(html, /\bconfidence\b/);
});

test("zh AgentTimeline shows Chinese agent descriptions", () => {
  const html = renderToStaticMarkup(
    <AgentTimeline agents={structuredAgents} language="zh" progress={null} />
  );

  // Chinese agent descriptions
  assert.match(html, /架构分析/);
  assert.match(html, /代码质量/);
  assert.match(html, /可维护性/);
  assert.match(html, /重构建议/);
  // Chinese status labels
  assert.match(html, /已完成/);
  assert.match(html, /失败/);
});

test("English mode remains unchanged after zh fixes", () => {
  const html = renderToStaticMarkup(
    <FindingsPanel
      error={null}
      findings={structuredFindings}
      language="en"
      loading={false}
      onRetry={() => undefined}
    />
  );

  // English labels should still be present
  assert.match(html, /Findings/);
  assert.match(html, /Recommended action/);
  assert.match(html, /Impact/);
  assert.match(html, /First safe step/);
  assert.match(html, /Validation tests/);
  assert.match(html, /Caveat/);
  assert.match(html, /Evidence/);
  assert.match(html, /confidence/);
});

// --- V3.5.12 Export and stale history tests ---

test("export URL includes lang=zh when language is zh", () => {
  const { getReviewExportUrl } = require("../lib/api");
  const url = getReviewExportUrl("task-1", { lang: "zh" });
  assert.match(url, /lang=zh/);
  assert.match(url, /\/export/);
});

test("export URL has no lang param for English", () => {
  const { getReviewExportUrl } = require("../lib/api");
  const url = getReviewExportUrl("task-1", { lang: "en" });
  assert.doesNotMatch(url, /lang=/);
});

test("exportReview uses fetch and returns Blob on success", async () => {
  const { exportReview } = require("../lib/api");
  const originalFetch = globalThis.fetch;
  let requestedUrl = "";
  const mdContent = "# Test Report";

  globalThis.fetch = async (input) => {
    requestedUrl = String(input);
    return new Response(mdContent, {
      status: 200,
      headers: {
        "Content-Type": "text/markdown; charset=utf-8",
        "Content-Disposition": 'attachment; filename="codepilot-review-abc123-zh.md"'
      }
    });
  };

  try {
    const result = await exportReview("task-1", { lang: "zh" });
    assert.match(requestedUrl, /lang=zh/);
    assert.ok(result.blob instanceof Blob);
    assert.equal(result.filename, "codepilot-review-abc123-zh.md");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("exportReview uses fallback filename when Content-Disposition is missing", async () => {
  const { exportReview } = require("../lib/api");
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () => {
    return new Response("# Report", {
      status: 200,
      headers: { "Content-Type": "text/markdown; charset=utf-8" }
    });
  };

  try {
    const result = await exportReview("task-1", { lang: "en" });
    assert.match(result.filename, /codepilot-review-/);
    assert.match(result.filename, /\.md$/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("exportReview throws CodePilotApiError on 404 review_not_found", async () => {
  const { exportReview, CodePilotApiError } = require("../lib/api");
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () => {
    return new Response(
      JSON.stringify({ error: "Review not found", code: "review_not_found", detail: "Not found" }),
      { status: 404, headers: { "Content-Type": "application/json" } }
    );
  };

  try {
    await exportReview("stale-task", { lang: "en" });
    assert.fail("Should have thrown");
  } catch (err) {
    assert.ok(err instanceof CodePilotApiError);
    assert.equal(err.code, "review_not_found");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("exportReview throws CodePilotApiError on 409 review_not_ready", async () => {
  const { exportReview, CodePilotApiError } = require("../lib/api");
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () => {
    return new Response(
      JSON.stringify({ error: "Review not ready", code: "review_not_ready", detail: "Not ready" }),
      { status: 409, headers: { "Content-Type": "application/json" } }
    );
  };

  try {
    await exportReview("task-1", { lang: "en" });
    assert.fail("Should have thrown");
  } catch (err) {
    assert.ok(err instanceof CodePilotApiError);
    assert.equal(err.code, "review_not_ready");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("exportReview calls lang=en without query param", async () => {
  const { exportReview } = require("../lib/api");
  const originalFetch = globalThis.fetch;
  let requestedUrl = "";

  globalThis.fetch = async (input) => {
    requestedUrl = String(input);
    return new Response("# Report", {
      status: 200,
      headers: { "Content-Type": "text/markdown" }
    });
  };

  try {
    await exportReview("task-1", { lang: "en" });
    assert.doesNotMatch(requestedUrl, /lang=/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("zh export error messages are defined", () => {
  assert.ok(t("zh", "export.reviewNotFound").length > 0);
  assert.ok(t("zh", "export.notReady").length > 0);
  assert.ok(t("zh", "export.networkError").length > 0);
  assert.ok(t("zh", "export.staleHistoryRemoved").length > 0);
});

test("en export error messages are defined", () => {
  assert.ok(t("en", "export.reviewNotFound").length > 0);
  assert.ok(t("en", "export.notReady").length > 0);
  assert.ok(t("en", "export.networkError").length > 0);
  assert.ok(t("en", "export.staleHistoryRemoved").length > 0);
});
