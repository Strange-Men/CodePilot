# CodePilot - Roadmap

> Harness version: v1.1
> Last updated: 2026-06-11

## Completed

### V1.0 - Production-Ready MVP

- [x] Public GitHub repository clone flow.
- [x] Python code discovery and parsing.
- [x] Repository context generation.
- [x] AI review report generation.
- [x] Deterministic mock LLM mode.
- [x] Fixed four-section report format.
- [x] REST API for submit, poll, and export.
- [x] Next.js frontend with progress polling and report rendering.
- [x] SQLite persistence.
- [x] Background review execution.

### V1.1 - Engineering Hardening

- [x] 44 collected pytest tests.
- [x] Ruff linting.
- [x] GitHub Actions CI on Windows.
- [x] Docker Compose local stack.
- [x] Vercel frontend deployment documentation.
- [x] Render Docker backend deployment documentation.
- [x] Python 3.11.11 runtime pinning.
- [x] Smoke test script for backend pipeline.

### V2.0-V2.6 - Repository Intelligence and Architecture Stabilization

- [x] Parser registry with Python, JavaScript, and TypeScript support.
- [x] File and repository metrics.
- [x] Internal dependency graph with fan-in/out, hubs, cycles, and orphans.
- [x] Calibrated file scoring, six file roles, and structural purpose inference.
- [x] Graph-aware prompt context and architecture summary guidance.
- [x] Deterministic rich Markdown report rendering.
- [x] OpenAI-compatible retry handling with exponential backoff.
- [x] Deterministic architecture overview, risk hotspots, onboarding guide, and refactoring candidates.
- [x] Combined Python, JavaScript, and TypeScript repository reviews.
- [x] Review history, structured API errors, and canonical GitHub URL validation.
- [x] Model-aware token counting, frontend error/loading states, and CI frontend tests.
- [x] Focused ReviewContext models with RepositoryContext compatibility.
- [x] Versioned prompt system and token-budget boundary.
- [x] Structured review findings with Markdown compatibility.
- [x] Shared prioritization, single-pass Python AST analysis, and graceful shutdown.
- [x] 187 collected pytest tests and enforced Harness audit.

### V3.0 - Evidence-Grounded Review MVP

- [x] Sandbox manifest with path traversal protection, symlink rejection, limits, and secret redaction.
- [x] Deep context, symbol index, evidence store, and evidence retrieval.
- [x] Structured LLM client, validation retry, ArchitectureAgent, and real LLM opt-in guard.
- [x] Basic multi-agent fan-out/fan-in with failure isolation and deduplication.
- [x] Mock-only V3 evaluation metrics, golden subset, hardening tests, and V3 documentation.

### V3.1 - Graph Orchestration and Structured Storage

- [x] Structured finding persistence with additive SQLite storage.
- [x] Agent state storage for per-agent intermediate results.
- [x] Graph-ready ReviewState for future LangGraph migration.
- [x] LangGraph deferred; ReviewState is migration-ready.
- [x] Inspectable agent results.

### V3.2 - Tiered Retrieval

- [x] Manifest, symbol, and snippet retrieval tiers.
- [x] Deterministic context compression.
- [x] Large repository analysis tiers and disclosure.
- [x] Persistable retrieval metrics without snippets.

### V3.3 - Developer Workflow Integration

- [x] CLI repository review with Markdown and JSON outputs.
- [x] CI report mode with safe default and optional severity gates.
- [x] Optional MCP server tools over the shared workflow/store layer.
- [x] Diff-aware review with changed-file and dependency-neighbor scope.
- [x] Network-free integration tests and workflow documentation.

### V3.4 - Report Quality and Agent Visibility

- [x] Repository classification with web framework, CLI, SDK, and mixed-language detection.
- [x] `HumanReadableReportComposer` producing bounded V3 reports with agent summaries and actionable guidance.
- [x] Agent visibility: per-agent status, finding counts, severity mix, confidence, and evidence counts.
- [x] Actionable recommendations with first-step, change-risk, evidence, and validation-test hints.
- [x] Deterministic report quality evaluation with 8 quality gates (network-free).
- [x] Report quality and agent visibility prioritized over LangGraph/V3.5 scope.
- [x] V3.4.1 patch: shared report constants, reduced classification false positives, evaluation report persistence, V3.4 artifact.

### V3.5 - Real LLM Evaluation and Quality Platform

- [x] Versioned datasets with deterministic local fixtures and optional public repositories.
- [x] Per-run registry with bounded report Markdown, safe finding/evidence counts, and agent summaries.
- [x] Five deterministic report quality dimensions with per-repository and aggregate scores.
- [x] Explicit `--real-llm` mode with provider/model metadata and graceful credential validation.
- [x] Per-agent token, call, and duration metadata plus per-repository runtime.
- [x] Optional exact-model pricing config; unknown pricing reports tokens without cost.
- [x] Stable run artifacts and deterministic comparison of metadata-compatible runs.
- [x] Mock mode remains the CI default; no credentials or network are required for local fixture tests.
- [x] LangGraph remains deferred.

## In Progress

V3.5 is complete. No V3.6 implementation is in progress.

V3.6 may be planned from measured V3.5 evidence. LangGraph is only justified if conditional routing, cyclic workflows,
checkpoint/resume, or human approval becomes a concrete requirement.

## Planned - V1.2

### Parser Improvements

- [ ] Add parser tests for decorators, nested classes, type aliases, `__all__`, and syntax edge cases.
- [ ] Improve file selection heuristics beyond entrypoint priority.
- [ ] Introduce a parser interface that can support non-Python languages later.

### Backend Hardening

- [x] Strengthen URL validation and user-facing error messages.
- [ ] Add basic rate limiting.
- [ ] Add cancellation support for in-progress reviews.
- [ ] Improve common failure handling for private repos, network timeouts, and invalid branches.

### UI Enhancements

- [x] Add review history from persisted tasks.
- [ ] Show more detailed progress states.
- [ ] Add report comparison for repeated reviews.
- [ ] Add dark mode if it fits the product direction.

## Planned - V2.0

### Multi-Language Analysis

- [x] Add language-agnostic parser registry.
- [x] Add JavaScript/TypeScript parser support.
- [ ] Add Go parser support.
- [ ] Add Rust parser support.
- [x] Detect repository language mix.

### Private Repository Support

- [ ] Add GitHub OAuth or token-based access.
- [ ] Store credentials securely.
- [ ] Add private repo error and permission handling.
- [ ] Consider GitHub App flow for PR review automation.

### Enhanced Analysis

- [x] Build dependency graph.
- [x] Compute code complexity metrics.
- [ ] Add basic security pattern scanning.
- [ ] Correlate findings with test coverage where available.

## Planned - V3.x

### Multi-Agent Review

- [x] Define specialized reviewer agent contracts.
- [x] Add orchestrator for routing context to agents.
- [x] Add per-agent quality, token, call, and duration evaluation.
- [ ] Add severity consensus beyond per-agent confidence.
- [ ] Add persisted audit trail for agent findings.

### Code Graph

- [x] Build lightweight call graph summary.
- [x] Build import/dependency graph.
- [ ] Add impact analysis.
- [ ] Use graph signals for prompt context selection.

### MCP Integration

- [x] Expose CodePilot as optional MCP tools.
- [x] Add an MCP-compatible IDE integration path.
- [ ] Support real-time analysis from editor context.

### Enterprise Direction

- [ ] Team workspaces.
- [ ] Custom review rules.
- [x] Configurable CLI-based CI report gates.
- [ ] Reporting dashboard.

### V3.6 Evaluation-Led Orchestration

- [ ] Analyze V3.5 run evidence for agent routing or recovery failures.
- [ ] Define measurable acceptance criteria before adding an orchestration dependency.
- [ ] Consider LangGraph only for conditional routing, cycles, durable resume, or approval nodes.
- [ ] Preserve `ReviewState`, the existing review engine, SQLite compatibility, and mock CI behavior.

## Technical Debt

| Item | Priority | Notes |
|------|----------|-------|
| Frontend browser tests | Medium | Component rendering tests exist, but no Playwright/Cypress workflow is configured. |
| Cross-language dependency semantics | Medium | Static imports are merged, but runtime relationships between Python and browser code are not inferred. |
| Database migrations | Low | Needed if SQLite schema evolves. |
| `py.typed` marker | Low | Useful for downstream type-aware tooling. |
| Frontend state management | Medium | Current page-level state is fine for MVP but will stretch with history/comparison. |
| Provider usage reconciliation | Low | V3.5 token counts are local estimates; provider invoice reconciliation is not implemented. |

## Ideas Parking Lot

- Streaming report generation with server-sent events.
- Report caching by repository and commit.
- Batch repository reviews.
- Custom report templates.
- PDF export.
- GitHub App integration.
- Human preference labels for selected benchmark reports.

## Cross-References

- Product scope: `GOAL.md`
- Current implementation: `PROJECT_CONTEXT.md`
- Architecture readiness: `ARCHITECTURE.md`
- Decisions backing roadmap: `DECISION_LOG.md`
