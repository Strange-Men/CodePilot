# CodePilot V3 Architecture

CodePilot V3.1 keeps the V2.6 API, frontend contract, parser registry, mock mode, `ReviewContext`, and four-section report output intact. It adds graph-ready runtime state and additive SQLite tables for validated structured findings, safe evidence references, and per-agent execution state.

## Flow

```text
clone repo
-> SandboxManifest builds the only V3 file entry point
-> parsers consume manifest redacted content
-> RepositoryIndexer builds ReviewContext + DeepContextSummary + EvidenceRecord list
-> EvidenceRetriever selects per-agent evidence bundles
-> StructuredLLMClient requests JSON findings
-> FindingValidator resolves evidence_id to file/lines/snippet
-> AgentOrchestrator consumes and produces ReviewState
-> validated findings and agent states are persisted without source snippets
-> MarkdownReviewAdapter preserves four sections and appendices
```

## Evidence IDs

`evidence_id` values are stable hashes of normalized file path, line range, and redacted snippet. LLM output is allowed to cite only `evidence_ids`; backend code resolves file paths, line ranges, and snippets from `EvidenceStore`.

Persisted evidence records contain only `evidence_id`, file path, line range, kind, and symbols. Source snippets are intentionally excluded from SQLite and inspectable state snapshots.

## ReviewState

`ReviewState` is the graph-ready execution aggregate. It contains the runtime `ReviewContext`, per-agent evidence bundles, agent results, validated findings, isolated errors, and orchestration metadata.

`ReviewState.safe_snapshot()` converts runtime state into a persistable representation:

- repository context is reduced to metadata and summary fields;
- evidence bundles become lists of `evidence_id` values;
- evidence records become snippet-free references;
- agent findings retain their validator-produced evidence lineage.

The stable `EvidenceGroundedAgent.review(context)` protocol remains unchanged. `AgentOrchestrator.review(context)` is also retained as the compatibility entry point and delegates to `AgentOrchestrator.run(state)`.

## LangGraph Decision

LangGraph is deferred for V3.1. The current graph is a fixed sequence of four independent agents followed by deterministic deduplication. There are no conditional branches, cycles, human approval nodes, distributed workers, or checkpoint-resume requirements that justify an orchestration dependency.

The project should reconsider LangGraph only when at least one of these becomes a real requirement:

- conditional routing based on validated findings;
- resumable execution across process restarts;
- human-in-the-loop review nodes;
- branching or cyclic agent workflows;
- durable distributed execution.

Until then, `ReviewState` and `AgentOrchestrator.run(state)` provide the required graph boundary with lower dependency and migration cost.

## Feature Flags

- `REVIEW_ENGINE=v2` keeps the existing V2.6 report path and remains the default.
- `REVIEW_ENGINE=v3_single_agent` enables `ArchitectureAgent`.
- `REVIEW_ENGINE=v3_multi_agent` enables Architecture, CodeSmell, Maintainability, and Refactor agents.
- `USE_MOCK_LLM=true` remains default and needs no credentials.
- `ENABLE_REAL_LLM=true` is required in addition to `USE_MOCK_LLM=false` before the OpenAI-compatible client can run.

## Limitations

V3.1 does not add LangGraph, vector DB, retrieval/RAG, MCP, CLI, CI/PR integration, OAuth, SaaS, billing, RBAC, or enterprise features. JS/TS context remains best-effort lexical extraction.

## V3.2 Retrieval Note

V3.2 keeps the V3.1 contracts and upgrades retrieval inside `EvidenceRetriever` with manifest, symbol, and snippet tiers, deterministic context compression, large repo mode, and additive retrieval metrics. The stronger RAG decision is documented in `docs/V3_2_RETRIEVAL.md`; V3.2 intentionally does not add vector DBs, LangChain, LangGraph, or new agents.

## V3.3 Workflow Integration Note

V3.3 adds developer workflow entry points without changing the review engine:

- `backend.cli` exposes `review`, `ci`, and `diff` commands.
- `backend.workflows.ReviewWorkflow` synchronously wraps `ReviewPipeline`, `ReviewStore`, and persisted structured artifacts.
- `backend.mcp_server` optionally registers MCP tools when the MCP SDK is installed.
- `ReviewScope` narrows V3 evidence retrieval to changed files and dependency neighbors for diff-aware reviews.

The API, SQLite schema, `report_markdown`, `ReportResult`, four-section report contract, V2 path, V3.0/V3.1/V3.2 paths, evidence lineage, structured finding persistence, agent state storage, and `ReviewState` remain compatible.

## V3.4 Report Quality Note

V3.4 adds `HumanReadableReportComposer` after validated V3 findings are produced. It builds an additive overview,
agent summary, action plan, and snippet-free evidence appendix while retaining the original four sections and
`report_markdown` export contract. V2 continues to use `MarkdownReviewAdapter`.

Repository insights now classify common repository types with web-framework precedence over CLI signals, prioritize
production code in user-facing recommendations, separate test hotspots, and render long dependency cycles as bounded
groups. Deterministic report quality checks live in `evaluation/report_quality.py`.
