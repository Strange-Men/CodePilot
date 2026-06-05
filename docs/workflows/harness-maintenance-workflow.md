# Harness Maintenance Workflow

> Last updated: 2026-06-05
> Source of truth: `.harness/HARNESS_UPDATE_CHECKLIST.md`

Use this workflow whenever repository facts or governance rules may have changed.

## Steps

1. Classify the change using `.harness/HARNESS_UPDATE_CHECKLIST.md`.
2. Read every document marked `Update` or `Review`.
3. Check claims against repository files, tests, CI, deployment docs, and source code.
4. Apply `.harness/HARNESS_AUDIT_RULES.md` if drift is suspected.
5. Update all affected documents together.
6. Verify cross-references.
7. Add a decision log entry for significant governance, architecture, deployment, or process changes.
8. Run validation appropriate to the change.

## Common Checks

```powershell
pytest --collect-only -q
ruff check .
```

For documentation-only Harness installs, `pytest --collect-only -q` is enough to verify test-count claims without changing application behavior.

## Cross-Reference Targets

- `.harness/GOAL.md`
- `.harness/PROJECT_CONTEXT.md`
- `.harness/ARCHITECTURE.md`
- `.harness/TESTING.md`
- `.harness/RELEASE_RULES.md`
- `.harness/ROADMAP.md`
- `.harness/DECISION_LOG.md`
- `.harness/WORKFLOW.md`
- `.harness/HARNESS_AUDIT_RULES.md`
