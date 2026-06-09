# Roadmap

CodePilot V3.4 is complete through evidence-grounded agents, tiered retrieval, CLI/CI/MCP/diff workflows,
human-readable reports, agent visibility, actionable guidance, and deterministic report quality checks.

Next approved milestone:

- **V3.5 real-LLM evaluation platform:** versioned datasets, model/provider metadata, cost and latency comparison,
  rubric or human scoring, and regression reports.

Deferred beyond V3.5:

- LangGraph or another orchestration dependency until conditional routing, durable resume, or human approval nodes exist.
- Vector databases or full RAG until deterministic retrieval no longer meets measured quality needs.
- GitHub App, auto-fix, auto-commit, private repositories, OAuth, SaaS, billing, RBAC, and enterprise features.

The migration and stable compatibility boundaries are documented in `docs/V3_READINESS.md`.
