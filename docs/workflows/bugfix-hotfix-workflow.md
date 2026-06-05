# Bugfix and Hotfix Workflow

> Last updated: 2026-06-05
> Source of truth: `.harness/WORKFLOW.md`

Use this workflow for ordinary bug fixes and urgent production hotfixes.

## Bugfix Steps

1. Reproduce the bug or document why reproduction is not feasible.
2. Identify the narrowest affected module.
3. Add a regression test when code changes.
4. Implement the smallest safe fix.
5. Run targeted tests and then the relevant full gates.
6. Update Harness docs if behavior, architecture, test count, or known constraints changed.
7. Record significant root-cause or process decisions in `.harness/DECISION_LOG.md`.

## Hotfix Steps

1. Preserve failure evidence.
2. Stop unrelated work.
3. Prefer rollback if a known-good deployment exists.
4. Patch only the verified cause.
5. Run focused validation first, then full gates as time permits.
6. Obtain deployment approval.
7. Verify `/health` and the affected user flow after deploy.
8. Record the hotfix decision and follow-up work.

## Validation

```powershell
pytest tests/unit -v
pytest tests/integration -v
ruff check .
```

Use `scripts/smoke-backend.ps1` for backend pipeline fixes and before release.

## Harness Updates

Bug fixes usually update `.harness/TESTING.md` if test counts change and `.harness/DECISION_LOG.md` if the fix exposes a meaningful design, deployment, or process decision.
