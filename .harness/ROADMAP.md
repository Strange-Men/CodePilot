# CodePilot - Roadmap

> Harness version: v1.1
> Last updated: 2026-06-07

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

### V2.0-V2.4 - Repository Intelligence

- [x] Parser registry with Python, JavaScript, and TypeScript support.
- [x] File and repository metrics.
- [x] Internal dependency graph with fan-in/out, hubs, cycles, and orphans.
- [x] Calibrated file scoring, six file roles, and structural purpose inference.
- [x] Graph-aware prompt context and architecture summary guidance.
- [x] Deterministic rich Markdown report rendering.
- [x] OpenAI-compatible retry handling with exponential backoff.
- [x] 131 collected pytest tests and enforced Harness audit.

## In Progress

V2.4 quality verification and release preparation.

## Future Development Priorities

1. Repository Intelligence.
2. Code Review Quality.
3. Refactor Capability.
4. Multi-Language Support.

Infrastructure work should only be planned when it directly enables these priorities.

## Planned - V1.2

### Parser Improvements

- [ ] Add parser tests for decorators, nested classes, type aliases, `__all__`, and syntax edge cases.
- [ ] Improve file selection heuristics beyond entrypoint priority.
- [ ] Introduce a parser interface that can support non-Python languages later.

### Backend Hardening

- [ ] Strengthen URL validation and user-facing error messages.
- [ ] Add basic rate limiting.
- [ ] Add cancellation support for in-progress reviews.
- [ ] Improve common failure handling for private repos, network timeouts, and invalid branches.

### UI Enhancements

- [ ] Add review history from persisted tasks.
- [ ] Show more detailed progress states.
- [ ] Add report comparison for repeated reviews.
- [ ] Add dark mode if it fits the product direction.

## Planned - V2.0

### Multi-Language Analysis

- [x] Add language-agnostic parser registry.
- [x] Add JavaScript/TypeScript parser support.
- [ ] Add Go parser support.
- [ ] Add Rust parser support.
- [ ] Detect repository language mix.

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

## Planned - V3.0

### Multi-Agent Review

- [ ] Define specialized reviewer agent contracts.
- [ ] Add orchestrator for routing context to agents.
- [ ] Add severity consensus and deduplication.
- [ ] Add audit trail for agent findings.

### Code Graph

- [ ] Build call graph.
- [x] Build import/dependency graph.
- [ ] Add impact analysis.
- [ ] Use graph signals for prompt context selection.

### MCP Integration

- [ ] Expose CodePilot as an MCP tool.
- [ ] Add IDE integration path.
- [ ] Support real-time analysis from editor context.

### Enterprise Direction

- [ ] Team workspaces.
- [ ] Custom review rules.
- [ ] CI/CD review gates.
- [ ] Reporting dashboard.

## Technical Debt

| Item | Priority | Notes |
|------|----------|-------|
| Frontend browser tests | Medium | Component rendering tests exist, but no Playwright/Cypress workflow is configured. |
| Consistent API error schema | Medium | Current errors are FastAPI defaults. |
| Database migrations | Low | Needed if SQLite schema evolves. |
| `py.typed` marker | Low | Useful for downstream type-aware tooling. |
| Frontend state management | Medium | Current page-level state is fine for MVP but will stretch with history/comparison. |

## Ideas Parking Lot

- Streaming report generation with server-sent events.
- Report caching by repository and commit.
- Batch repository reviews.
- Custom report templates.
- PDF export.
- CLI entry point.
- GitHub App integration.
- LLM cost tracking.

## Cross-References

- Product scope: `GOAL.md`
- Current implementation: `PROJECT_CONTEXT.md`
- Architecture readiness: `ARCHITECTURE.md`
- Decisions backing roadmap: `DECISION_LOG.md`
