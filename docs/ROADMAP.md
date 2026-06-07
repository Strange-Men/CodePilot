# Roadmap

CodePilot V2.6 completes the 2.x architecture stabilization work. It intentionally avoids agents, orchestration frameworks, MCP, authentication, SaaS, and enterprise features.

Completed V2.6 foundations:

- Focused `ReviewContext` models with a flat `RepositoryContext` compatibility adapter.
- Versioned prompt templates, sections, rendering, and token budgeting.
- Structured review drafts with lossless Markdown adaptation.
- Shared prioritization and source-selection helpers.
- Single-pass Python AST analysis and graceful task-runner shutdown.

Future work requires a separately approved V3 plan. The migration boundary is documented in `docs/V3_READINESS.md`; no V3 runtime is implemented.
