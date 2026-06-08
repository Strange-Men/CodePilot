# CodePilot V3.0 Architecture

CodePilot V3.0 keeps the V2.6 API, SQLite schema, frontend contract, parser registry, mock mode, `ReviewContext`, and four-section report output intact. The new work is additive inside the backend review path.

## Flow

```text
clone repo
-> SandboxManifest builds the only V3 file entry point
-> parsers consume manifest redacted content
-> RepositoryIndexer builds ReviewContext + DeepContextSummary + EvidenceRecord list
-> EvidenceRetriever selects per-agent evidence bundles
-> StructuredLLMClient requests JSON findings
-> FindingValidator resolves evidence_id to file/lines/snippet
-> AgentOrchestrator deduplicates validated findings
-> MarkdownReviewAdapter preserves four sections and appendices
```

## Evidence IDs

`evidence_id` values are stable hashes of normalized file path, line range, and redacted snippet. LLM output is allowed to cite only `evidence_ids`; backend code resolves file paths, line ranges, and snippets from `EvidenceStore`.

## Feature Flags

- `REVIEW_ENGINE=v2` keeps the existing V2.6 report path and remains the default.
- `REVIEW_ENGINE=v3_single_agent` enables `ArchitectureAgent`.
- `REVIEW_ENGINE=v3_multi_agent` enables Architecture, CodeSmell, Maintainability, and Refactor agents.
- `USE_MOCK_LLM=true` remains default and needs no credentials.
- `ENABLE_REAL_LLM=true` is required in addition to `USE_MOCK_LLM=false` before the OpenAI-compatible client can run.

## Limitations

V3.0 does not add LangGraph, vector DB, MCP, Anthropic, PR review, CLI, OAuth, SaaS, billing, RBAC, or enterprise features. JS/TS context remains best-effort lexical extraction.
