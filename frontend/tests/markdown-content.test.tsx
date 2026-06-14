import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { MarkdownContent } from "../components/MarkdownContent";
import { ReportRenderer } from "../components/ReportRenderer";
import { parseReport } from "../lib/report";

test("renders GFM tables and highlighted fenced code", () => {
  const html = renderToStaticMarkup(
    <MarkdownContent>
      {"| File | Score |\n| --- | ---: |\n| app.py | 100 |\n\n```python\nif ready:\n    run()\n```"}
    </MarkdownContent>
  );

  assert.match(html, /<table>/);
  assert.match(html, /<td>app\.py<\/td>/);
  assert.match(html, /class="hljs language-python"/);
  assert.match(html, /class="hljs-keyword"/);
});

test("parses optional repository intelligence appendices separately", () => {
  const sections = parseReport(
    "# Repository Insights\nInsights.\n\n# Repository Metrics\nMetrics.\n\n"
      + "# Architecture Graph\nGraph.\n\n# Architecture Summary\nArchitecture."
  );

  assert.equal(sections["Repository Insights"].trim(), "Insights.");
  assert.equal(sections["Repository Metrics"].trim(), "Metrics.");
  assert.equal(sections["Architecture Graph"].trim(), "Graph.");
  assert.equal(sections["Architecture Summary"].trim(), "Architecture.");
});

test("renders markdown report sections without creating structured agent cards", () => {
  const markdown = [
    "# Executive Summary",
    "Summary.",
    "# Agent Summary",
    "| Agent | Status | Findings |",
    "| --- | --- | ---: |",
    "| ArchitectureAgent | completed | 1 |",
    "# Agent Findings",
    "## ArchitectureAgent",
    "| Severity | Finding |",
    "| --- | --- |",
    "| medium | Boundary risk |",
    "# Architecture Summary",
    "Architecture.",
    "# Code Smells",
    "None.",
    "# Maintainability Issues",
    "None.",
    "# Refactoring Suggestions",
    "None."
  ].join("\n");

  const html = renderToStaticMarkup(
    <ReportRenderer isRunning={false} reportMarkdown={markdown} />
  );

  assert.match(html, /Agent Summary/);
  assert.match(html, /ArchitectureAgent/);
  assert.match(html, /Boundary risk/);
  assert.ok(html.indexOf("Executive Summary") < html.indexOf("Architecture Summary"));
  assert.doesNotMatch(html, /data-agent-card=/);
  assert.doesNotMatch(html, /data-structured-findings/);
});
