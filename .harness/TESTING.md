# CodePilot - Testing Strategy

> Harness version: v1.2
> Last updated: 2026-06-07
> Verified with: `pytest --collect-only -q` on 2026-06-07

## Current Test Inventory

`pytest --collect-only -q` collected 115 tests.

| Layer | Tests | Files | Purpose |
|-------|-------|-------|---------|
| Unit | 105 | 13 | Validate isolated backend services, parsers, repository intelligence, LLM behavior, report generation, evaluation metrics, storage, and task runner. |
| Integration | 9 | 2 | Validate FastAPI review endpoints and JS/TS review pipeline completion. |
| Regression | 1 | 1 | Lock production bug fixes so they do not recur. |
| Smoke | 1 script | 1 | Validate live backend clone -> parse -> review -> export pipeline. |

## Unit Tests

| File | Collected Tests | Coverage |
|------|-----------------|----------|
| `tests/unit/test_clone_service.py` | 10 | Git URL validation, retry behavior, clone fallback, cleanup, readonly files. |
| `tests/unit/test_dependency_graph.py` | 4 | Internal dependency resolution, fan-in/fan-out, hubs, fan-in-based orphans, and cycle detection for Python and TypeScript. |
| `tests/unit/test_evaluation_metrics.py` | 1 | Evaluation parser-stat aggregation and parse-issue detection. |
| `tests/unit/test_evaluation_run_eval.py` | 4 | Evaluation dataset results preserve parser stats and enforce source-file thresholds. |
| `tests/unit/test_indexer.py` | 3 | Repository/file metric propagation, role propagation, graph metrics, and graph-aware rescoring. |
| `tests/unit/test_javascript_parser.py` | 9 | JavaScript/TypeScript discovery, imports, dependency imports, classes, functions, exports, metrics, prioritization, and malformed-source safety. |
| `tests/unit/test_llm_client.py` | 12 | OpenAI-compatible requests, transient retries, exponential backoff, retry limits, permanent failures, credentials, and deterministic mock mode. |
| `tests/unit/test_parser_registry.py` | 4 | Default Python parser registration, explicit SourceParser inheritance, language normalization, missing parser errors. |
| `tests/unit/test_python_parser.py` | 11 | Valid, syntax-error, empty files, metrics, dependency imports, discovery filters, max-file handling, path format, and non-ASCII parsing. |
| `tests/unit/test_report_generator.py` | 12 | Mock generation, malformed output, shared contract, formatting-preserving budgets, role grouping, report appendices, ordering, and trailing newline. |
| `tests/unit/test_review_store.py` | 6 | DB initialization, WAL mode, CRUD, errors, report preservation, missing task. |
| `tests/unit/test_review_task_runner.py` | 6 | Submit behavior, successful run, failure path, status progression, parser registry handoff, JS parser selection. |
| `tests/unit/test_scoring.py` | 23 | Importance labels, normalized scoring, path modifiers, entry-point detection, and dependency-aware importance. |

## Integration Tests

| File | Collected Tests | Coverage |
|------|-----------------|----------|
| `tests/integration/test_javascript_review_pipeline.py` | 1 | Local JavaScript repository review completes and the generated report uses JavaScript language labeling. |
| `tests/integration/test_reviews_api.py` | 8 | Create review, invalid payload, query, missing task, export, export conflict, failed review response. |

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

# Build frontend
cd frontend
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
| Harness audit | 0 critical drift findings | CI and release checklist |
| Smoke test | Pass before release | Manual release checklist |

## Known Test Gaps

| Gap | Priority | Notes |
|-----|----------|-------|
| Frontend component tests | Medium | No React Testing Library or browser test setup yet. |
| End-to-end browser tests | Low | No Playwright/Cypress setup. |
| Real LLM client live tests | Low | Requires external credentials and may be flaky/costly. |
| Performance tests | Low | V1.1 relies on functional and smoke coverage. |
| Deep JS/TS parser coverage | Medium | V2 MVP covers common imports, functions, classes, and exports; framework-specific syntax remains future work. |

## Cross-References

- Quality bar: `GOAL.md`
- Release gates: `RELEASE_RULES.md`
- Current repo facts: `PROJECT_CONTEXT.md`
- Test-related decisions: `DECISION_LOG.md`
