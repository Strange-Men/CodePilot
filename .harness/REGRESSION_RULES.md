# CodePilot - Regression Rules

> Harness version: v1.2
> Last updated: 2026-06-05

## Purpose

The regression harness prevents fixed production bugs from returning. Every real production bug that reaches users should become a numbered regression with a reproduction note, a test, and verification evidence.

## Workflow

```text
Bug
  -> Reproduce
  -> Regression Test
  -> Fix
  -> Verify
```

### 1. Bug

Capture the observed failure in user terms:

- Affected repository, input, or workflow.
- User-visible symptom.
- Error text or stack trace when available.
- Production/runtime context.

### 2. Reproduce

Reproduce locally before changing behavior whenever possible.

Minimum reproduction record:

- Command or script used.
- Exact failing path or module.
- Stack trace or controlled failure output.
- Why the failure matters.

If external network access blocks full reproduction, create the smallest local fixture that exercises the same failing code path and document the gap.

### 3. Regression Test

Add a test under `tests/regressions/` before or alongside the fix.

Rules:

- Name the file `test_regression_<number>_<short_name>.py`.
- Name the test `test_regression_<number>_<expected_behavior>`.
- Keep the fixture minimal and deterministic.
- Avoid real network, real LLM calls, and external services.
- Link the test to a numbered regression entry in this file.

### 4. Fix

Make the smallest safe product change that fixes the reproduced failure. Avoid architecture redesigns unless the regression proves the existing design is unsound.

### 5. Verify

Run:

```powershell
pytest tests/regressions -v
pytest
ruff check .
```

Run frontend build only when frontend files or shared frontend/backend contracts changed.

## Regression Registry

### Regression-001: tree-sitter non-ASCII byte offset parsing

- Status: Covered
- Date registered: 2026-06-05
- Production trigger: Reviewing `https://github.com/Strange-Men/EnterpriseAiDataAgent.git`.
- Observed failure: review task failed with `IndexError: list index out of range`.
- Root cause: `PythonParser._parse_with_tree_sitter()` parsed UTF-8 bytes but sliced the decoded Python string with tree-sitter byte offsets. Files with enough non-ASCII content before an import node could produce an empty string slice, then `splitlines()[0]` raised `IndexError`.
- Regression test: `tests/regressions/test_regression_001_tree_sitter_non_ascii.py`.
- Expected behavior: parser handles non-ASCII content before import statements and extracts imports without crashing.
- Verification: `pytest tests/regressions -v`, full `pytest`, and `ruff check .`.

## Examples

### Parser Regression

Use a small local Python file fixture instead of cloning a large repository:

```python
source.write_text(non_ascii_prefix + "import os\n", encoding="utf-8")
parsed = PythonParser().parse_file(temp_repo, source)
assert parsed.imports == ["import os"]
```

### API Regression

Use the FastAPI test client or `httpx.AsyncClient` with mocked services. Assert the status code, response shape, and user-facing error text.

### Task Runner Regression

Use fake clone, indexer, or report generator classes. Assert status progression and stored error/report state.

## Maintenance Rules

- Every production bug gets a numbered regression entry.
- Do not delete regression tests unless the corresponding feature is removed and the deletion is recorded here.
- Keep regression tests deterministic and fast.
- Keep large external repositories in `evaluation/`, not in regression tests.
- If a regression requires network access, prefer adding an evaluation target and a minimal local regression fixture.
- Update this file whenever a new regression test is added, renamed, or retired.

## Cross-References

- Evaluation harness: `evaluation/README.md`
- Test strategy: `.harness/TESTING.md`
- Release gates: `.harness/RELEASE_RULES.md`
