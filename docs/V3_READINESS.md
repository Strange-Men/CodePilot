# V3 Readiness

CodePilot V2.6 stops at architecture foundations. It does not implement agents, LangGraph, MCP, OAuth, SaaS, or enterprise behavior.

## Ready Boundaries

- `ReviewContext` is the internal repository-analysis input. Its focused models can be routed or filtered without expanding the legacy flat context.
- `PromptTemplate`, `PromptSection`, and `PromptRenderer` isolate prompt policy from report orchestration.
- `StructuredReviewDraft` and `ReviewFinding` provide a provider-neutral internal review result.
- `MarkdownReviewAdapter` preserves the current frontend, API, persistence, and export contract.
- Parser Registry and `DependencyGraph` remain reusable analysis inputs.

## Stable Contracts

- The API response shape and SQLite schema remain unchanged.
- Reports retain Architecture Summary, Code Smells, Maintainability Issues, and Refactoring Suggestions in that order.
- Mock mode runs the complete review pipeline without credentials.
- `RepositoryContext` remains available for V2.5 extensions.

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
- Structured findings are currently populated from Markdown; no agent orchestration exists.
