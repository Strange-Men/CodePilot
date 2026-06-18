# V3 Readiness

CodePilot V3.4 implements evidence-grounded review, developer workflow integration, human-readable report composition,
agent visibility, actionable guidance, and deterministic report quality checks. It still excludes LangGraph, OAuth,
SaaS, private repo support, GitHub App behavior, and enterprise features.

## Ready Boundaries

- `ReviewContext` is the internal repository-analysis input. Its focused models can be routed or filtered without expanding the legacy flat context.
- `PromptTemplate`, `PromptSection`, and `PromptRenderer` isolate prompt policy from report orchestration.
- `StructuredReviewDraft` and `ReviewFinding` provide a provider-neutral internal review result.
- `MarkdownReviewAdapter` preserves the current frontend, API, persistence, and export contract.
- Parser Registry and `DependencyGraph` remain reusable analysis inputs.
- `SandboxManifest`, `EvidenceStore`, `EvidenceRetriever`, and `DeepContextEngine` provide V3 grounding.
- `AgentOrchestrator` fans out internal agents and deduplicates validated structured findings.
- `ReviewWorkflow`, `backend.cli`, and optional `backend.mcp_server` expose the pipeline to CLI, CI, MCP, and diff-aware review workflows.
- `HumanReadableReportComposer` presents validated findings without changing the persisted Markdown or four-section contract.
- `evaluation.report_quality` provides mock-only quality regression checks that do not require credentials or network access.

## Stable Contracts

- The API response shape and SQLite schema remain unchanged.
- Reports retain Architecture Summary, Code Smells, Maintainability Issues, and Refactoring Suggestions in that order.
- Mock mode runs the complete review pipeline without credentials.
- `RepositoryContext` remains available for V2.5 extensions.
- Diff-aware review scope is additive and only narrows V3 evidence retrieval when explicitly requested.

## Future Migration Sequence

1. Define any future reviewer interface in terms of `ReviewContext -> StructuredReviewDraft`.
2. Keep provider or orchestration details behind that interface.
3. Merge and deduplicate structured findings before Markdown adaptation.
4. Add persistence only after a versioned schema and API migration are approved.
5. Retire `RepositoryContext` only in a separately approved breaking release.

## Known Limitations

- Complexity and JavaScript/TypeScript parsing are heuristic.
- Dependency resolution is static and does not infer cross-runtime calls.
- Review jobs are in-process and are not durable across process restarts.
- Real LLM evaluation is manual and optional; CI remains mock-only.
- MCP serving requires the optional MCP SDK; the pure workflow tools remain testable without it.
- Test-file matching for validation guidance is name-based and does not infer dynamic test coverage.
