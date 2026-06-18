# Roadmap

CodePilot V3.5 is complete through evidence-grounded agents, tiered retrieval, CLI/CI/MCP/diff workflows,
human-readable reports, deterministic quality scoring, optional real-LLM evaluation, cost/latency metadata, and
regression artifacts.

V3.6 may now be planned, but is not implemented. Planning should use V3.5 evidence to decide whether fixed
orchestration has a real limitation before adding LangGraph.

- Candidate V3.6 scope: conditional routing or durable resume only when a measured workflow requires it.
- Continue to defer human approval, new agents, vector databases, auto-fix, GitHub App, and SaaS scope unless separately
  approved.

Still deferred:

- LangGraph or another orchestration dependency until conditional routing, durable resume, or human approval nodes exist.
- Vector databases or full RAG until deterministic retrieval no longer meets measured quality needs.
- GitHub App, auto-fix, auto-commit, private repositories, OAuth, SaaS, billing, RBAC, and enterprise features.

The migration and stable compatibility boundaries are documented in `docs/history/v3/V3_READINESS.md`.
