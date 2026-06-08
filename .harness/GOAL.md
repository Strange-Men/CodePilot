# CodePilot - Project Goal

> Harness version: v1.2
> Last updated: 2026-06-08

## Mission

Build and maintain an AI Code Review & Refactor Agent for Large Repositories: a production-quality tool that helps developers understand repositories, generate professional code review reports, and identify practical refactoring opportunities.

## Success Criteria

1. A developer pastes a public GitHub URL and receives a structured, actionable code review within 60 seconds for a typical 50-file Python repository.
2. The review covers four fixed dimensions: Architecture Summary, Code Smells, Maintainability Issues, and Refactoring Suggestions.
3. The system handles Python, JavaScript, TypeScript, and mixed repositories up to 300 analyzed files without crashing or exceeding the configured prompt token budget.
4. The tool is deployable on free-tier infrastructure with a Vercel frontend and Render Docker backend after platform setup.
5. Mock mode enables a complete end-to-end demo without API credentials.

CodePilot V2.6 completes the 2.x series with stabilized context, prompt, structured-review, parser, and lifecycle boundaries. Further work belongs to separately approved V3 scope.

## Non-Goals

- Private repository support; OAuth or token access is deferred to V2.0 or later.
- Language analysis beyond Python and JavaScript/TypeScript; additional languages are deferred to later V2/V3 work.
- Real-time collaborative review or inline commenting.
- IDE plugin or CLI-only mode.
- Self-hosted LLM inference; CodePilot uses mock mode or an OpenAI-compatible API endpoint.

## North Star Metric

Time from "paste URL" to "readable report" is under 60 seconds for a typical public 50-file Python repository.

## Quality Bar

- 198 automated pytest tests and 9 frontend tests pass.
- Ruff linting is clean with zero warnings.
- Frontend builds without TypeScript errors.
- Docker Compose can bring up both services with one command.
- Smoke test verifies clone, parse, review, store, and export flow.

Code review quality and refactor capability are the primary quality concerns. Harness docs are updated only when code changes make them factually stale — not as a routine activity.

## Cross-References

- Current implementation facts: `PROJECT_CONTEXT.md`
- Architecture and invariants: `ARCHITECTURE.md`
- Quality gates: `RELEASE_RULES.md`
- Roadmap alignment: `ROADMAP.md`
- Decision history: `DECISION_LOG.md`
