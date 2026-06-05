# CodePilot - Testing Strategy

> Harness version: v1.1
> Last updated: 2026-06-05
> Verified with: `pytest --collect-only -q` on 2026-06-05

## Current Test Inventory

`pytest --collect-only -q` collected 44 tests.

| Layer | Tests | Files | Purpose |
|-------|-------|-------|---------|
| Unit | 36 | 5 | Validate isolated backend services, parser, report generator, storage, and task runner. |
| Integration | 8 | 1 | Validate FastAPI review endpoints through HTTP request/response flow. |
| Smoke | 1 script | 1 | Validate live backend clone -> parse -> review -> export pipeline. |

## Unit Tests

| File | Collected Tests | Coverage |
|------|-----------------|----------|
| `tests/unit/test_clone_service.py` | 10 | Git URL validation, retry behavior, clone fallback, cleanup, readonly files. |
| `tests/unit/test_python_parser.py` | 8 | Valid, syntax-error, empty files, discovery filters, max file handling, path format. |
| `tests/unit/test_report_generator.py` | 8 | Mock generation, malformed LLM output, missing/extra sections, prompt budget, ordering, trailing newline. |
| `tests/unit/test_review_store.py` | 6 | DB initialization, WAL mode, CRUD, errors, report preservation, missing task. |
| `tests/unit/test_review_task_runner.py` | 4 | Submit behavior, successful run, failure path, status progression. |

## Integration Tests

| File | Collected Tests | Coverage |
|------|-----------------|----------|
| `tests/integration/test_reviews_api.py` | 8 | Create review, invalid payload, query, missing task, export, export conflict, failed review response. |

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
| Smoke test | Pass before release | Manual release checklist |

## Known Test Gaps

| Gap | Priority | Notes |
|-----|----------|-------|
| Frontend component tests | Medium | No React Testing Library or browser test setup yet. |
| End-to-end browser tests | Low | No Playwright/Cypress setup. |
| Real LLM client live tests | Low | Requires external credentials and may be flaky/costly. |
| Performance tests | Low | V1.1 relies on functional and smoke coverage. |
| Multi-language parser tests | Not applicable | Python-only is current product scope. |

## Cross-References

- Quality bar: `GOAL.md`
- Release gates: `RELEASE_RULES.md`
- Current repo facts: `PROJECT_CONTEXT.md`
- Test-related decisions: `DECISION_LOG.md`
