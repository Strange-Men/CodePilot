# CodePilot - Testing Strategy

> Harness version: v1.2
> Last updated: 2026-06-09
> Verified with: `pytest` on 2026-06-09

## Current Test Inventory

`pytest` collected 299 tests: 298 passed, 1 skipped (`test_sandbox_rejects_paths_outside_repo`).

| Layer | Tests | Files | Purpose |
|-------|-------|-------|---------|
| Unit | 274 | 32 | Validate contexts, prompts, structured reviews, report composition and quality, review state, backend services, parsers, sandbox safety, evidence retrieval, structured LLM agents, multi-agent orchestration, V3 hardening, diff scope, lifecycle, API errors, LLM behavior, storage, and task runner. |
| Integration | 23 | 4 | Validate FastAPI history/errors, language review pipelines, CLI/CI workflows, MCP wrappers, and diff mode. |
| Regression | 1 | 1 | Lock production bug fixes so they do not recur. |
| Smoke | 1 script | 1 | Validate live backend clone -> parse -> review -> export pipeline. |
| Frontend | 10 | 2 | Validate Markdown and agent-card rendering, history, URL validation, API errors, and reliability fallbacks. |

## Unit Tests

| File | Collected Tests | Coverage |
|------|-----------------|----------|
| `tests/unit/test_api_errors.py` | 4 | Known, framework, and unexpected structured API error envelopes plus the internal smoke URL guard. |
| `tests/unit/test_clone_service.py` | 10 | Git URL validation, retry behavior, clone fallback, cleanup, readonly files. |
| `tests/unit/test_composite_parser.py` | 6 | Multi-language discovery limits, parser delegation, and unsupported extensions. |
| `tests/unit/test_dependency_graph.py` | 5 | Internal dependency resolution, fan-in/fan-out, hubs, orphans, cycles, and mixed JS/TS edges. |
| `tests/unit/test_evaluation_metrics.py` | 1 | Evaluation parser-stat aggregation and parse-issue detection. |
| `tests/unit/test_evaluation_run_eval.py` | 4 | Evaluation dataset results preserve parser stats and enforce source-file thresholds. |
| `tests/unit/test_indexer.py` | 8 | Repository/file metric propagation, role propagation, graph-aware rescoring, and structural purpose inference. |
| `tests/unit/test_insights.py` | 11 | Repository type, Flask-like framework precedence, generic Request/Response false-positive guard, production/test hotspots, onboarding order, refactoring candidates, and safe defaults. |
| `tests/unit/test_javascript_parser.py` | 9 | JavaScript/TypeScript discovery, imports, dependency imports, classes, functions, exports, metrics, prioritization, and malformed-source safety. |
| `tests/unit/test_llm_client.py` | 13 | OpenAI-compatible requests, retries, credentials, deterministic mock mode, and repository-evidence mock findings. |
| `tests/unit/test_main.py` | 1 | FastAPI lifespan drains the review runner during shutdown. |
| `tests/unit/test_parser_registry.py` | 4 | Default Python parser registration, explicit SourceParser inheritance, language normalization, missing parser errors. |
| `tests/unit/test_prioritization.py` | 3 | Shared importance ordering, role filtering, and production-first recommendation ordering. |
| `tests/unit/test_prompt_system.py` | 5 | Versioned sections, independent rendering, nested-context compatibility, and token budgets. |
| `tests/unit/test_python_parser.py` | 12 | Parsing, metrics, discovery, dependency imports, non-ASCII handling, and single-pass AST reuse. |
| `tests/unit/test_report_composer.py` | 3 | Human-readable sections, snippet-free evidence, agent summaries, bounded actions, and production-first guidance. |
| `tests/unit/test_report_generator.py` | 14 | Mock generation, malformed output, shared contract, formatting-preserving budgets, structural/graph context, edge prioritization, report appendices, ordering, and trailing newline. |
| `tests/unit/test_review_store.py` | 15 | DB initialization, WAL mode, CRUD, report preservation, structured finding persistence, agent state and graph state storage, safe evidence refs, internal inspection, and schema-neutral history queries. |
| `tests/unit/test_review_context.py` | 4 | Focused context defaults and flat compatibility round trips. |
| `tests/unit/test_review_state.py` | 1 | Graph-ready ReviewState safe snapshots exclude source snippets while preserving evidence lineage. |
| `tests/unit/test_review_task_runner.py` | 8 | Submit/run behavior, status progression, parser selection, V3 state persistence, and idempotent executor shutdown. |
| `tests/unit/test_scoring.py` | 32 | Importance labels, calibrated scoring, role modifiers, all six file roles, entry-point detection, and dependency-aware importance. |
| `tests/unit/test_token_counting.py` | 6 | Model encodings, Unicode, exact budgets, line preservation, unknown-model fallback, and missing-dependency runtime fallback. |
| `tests/unit/test_v3_2_retrieval.py` | 17 | Tiered retrieval, legacy compatibility, context compression, token budgeting, safe metadata, large repo tiers, and manifest-only low-priority files. |
| `tests/unit/test_v3_3_diff_scope.py` | 4 | Changed-file scope, dependency-neighbor expansion, candidate-path retrieval, and focused V3 report generation. |
| `tests/unit/test_v3_4_report_quality.py` | 2 | Deterministic classification, ranking, cycle, agent, actionability, grounding, bounds, and leakage quality gates. |
| `tests/unit/test_v3_sandbox_evidence.py` | 6 | Sandbox boundaries, secret redaction, deep context, stable evidence IDs, and lexical evidence retrieval. |
| `tests/unit/test_v3_structured_agent.py` | 5 | Structured LLM retries, evidence-only validation, ArchitectureAgent mock behavior, V3 single-agent report contract, and real LLM opt-in guard. |
| `tests/unit/test_v3_multi_agent.py` | 4 | Multi-agent failure isolation, conservative deduplication, per-section mock findings, and V3 multi-agent report rendering. |
| `tests/unit/test_v3_evaluation_metrics.py` | 4 | Hallucination, quality, per-agent, and deterministic retrieval evaluation metrics. |
| `tests/unit/test_v3_hardening_matrix.py` | 48 | Secret redaction, sandbox boundaries, evidence stability, structured validation, real LLM opt-in, and deduplication matrix coverage. |
| `tests/unit/test_structured_review.py` | 6 | Markdown parsing, structured findings, contract ordering, cycle compression, and lossless context-aware round trips. |

## Integration Tests

| File | Collected Tests | Coverage |
|------|-----------------|----------|
| `tests/integration/test_javascript_review_pipeline.py` | 1 | Local JavaScript repository review completes and the generated report uses JavaScript language labeling. |
| `tests/integration/test_multilanguage_review_pipeline.py` | 1 | Python, JavaScript, and TypeScript parsers merge into one insight-rich mock review. |
| `tests/integration/test_reviews_api.py` | 17 | Create, canonical URL validation, history, item reads, structured errors, and export behavior. |
| `tests/integration/test_v3_3_workflows.py` | 4 | CLI report outputs, configurable CI exit policy, fixture diff parsing, and safe MCP workflow wrappers. |

## Regression Tests

| File | Collected Tests | Coverage |
|------|-----------------|----------|
| `tests/regressions/test_regression_001_tree_sitter_non_ascii.py` | 1 | Regression-001: tree-sitter byte offsets with non-ASCII text before import nodes. |

## Smoke Test

| File | Coverage |
|------|----------|
| `scripts/smoke-backend.ps1` | Starts or targets a backend, creates a local git-served repository, submits a review, polls to completion, verifies Markdown export sections. |

## Tooling Configuration

| Tool | Version | Source |
|------|---------|--------|
| pytest | 8.3.4 | `backend/requirements-dev.txt` |
| ruff | 0.8.4 | `backend/requirements-dev.txt` |
| pytest paths | `tests` | `pyproject.toml` |
| Python path | `.` | `pyproject.toml` |
| ruff line length | 120 | `pyproject.toml` |
| ruff target | `py311` | `pyproject.toml` |

## Commands

```powershell
# Collect tests without running
pytest --collect-only -q

# Run all backend tests
pytest

# Run unit tests
pytest tests/unit -v

# Run integration tests
pytest tests/integration -v

# Run lint
ruff check .

# Run Harness audit
python scripts/audit_harness.py

# Run frontend component/API tests
cd frontend
npm test

# Build frontend
npm run build

# Run smoke test
powershell -File scripts/smoke-backend.ps1
```

## Testing Conventions

- Use `tmp_path` for filesystem tests.
- Mock external network and LLM calls in unit tests.
- Use mock LLM mode for deterministic integration coverage.
- Assert status lifecycle where task behavior changes.
- New endpoints require integration tests.
- New parser behavior requires focused parser tests.
- Bug fixes require regression tests unless the fix is documentation-only.

## Quality Gates

| Gate | Threshold | Enforced By |
|------|-----------|-------------|
| Unit tests | 100% pass | CI and release checklist |
| Integration tests | 100% pass | CI and release checklist |
| Ruff | 0 warnings | CI and release checklist |
| Frontend build | 0 errors | CI and release checklist |
| Frontend tests | 100% pass | CI and release checklist |
| Harness audit | 0 critical drift findings | CI and release checklist |
| Smoke test | Pass before release | Manual release checklist |

## Known Test Gaps

| Gap | Priority | Notes |
|-----|----------|-------|
| Frontend polling behavior | Medium | Rendering, history, validation, and API errors are covered; timer-driven polling still lacks focused fake-timer tests. |
| End-to-end browser tests | Low | No Playwright/Cypress setup. |
| Real LLM client live tests | Low | Requires external credentials and may be flaky/costly. |
| Performance tests | Low | V1.1 relies on functional and smoke coverage. |
| Deep JS/TS parser coverage | Medium | V2 MVP covers common imports, functions, classes, and exports; framework-specific syntax remains future work. |

## Cross-References

- Quality bar: `GOAL.md`
- Release gates: `RELEASE_RULES.md`
- Current repo facts: `PROJECT_CONTEXT.md`
- Test-related decisions: `DECISION_LOG.md`
