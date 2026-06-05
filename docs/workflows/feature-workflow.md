# Feature Workflow

> Last updated: 2026-06-05
> Source of truth: `.harness/WORKFLOW.md`

Use this workflow when adding or changing a user-facing capability.

## Steps

1. Define the user outcome and acceptance criteria.
2. Inspect current frontend, backend, models, services, parser, storage, and deployment impact.
3. Identify whether the feature changes the API contract, data model, parser behavior, LLM prompt, UI behavior, or deployment assumptions.
4. Record or obtain architecture approval for significant changes.
5. Implement the smallest coherent change.
6. Add unit and integration tests at the appropriate layer.
7. Run relevant validation commands.
8. Update Harness documents using `.harness/HARNESS_UPDATE_CHECKLIST.md`.
9. Review the diff against `.harness/ARCHITECTURE.md` and `.harness/GOAL.md`.
10. Release only through `.harness/RELEASE_RULES.md`.

## Required Checks

```powershell
pytest
ruff check .
cd frontend
npm run build
```

Run `docker-compose build` and `scripts/smoke-backend.ps1` when runtime, deployment, backend pipeline, or release readiness is affected.

## Harness Updates

Feature work commonly touches:

- `.harness/PROJECT_CONTEXT.md`
- `.harness/ARCHITECTURE.md`
- `.harness/TESTING.md`
- `.harness/ROADMAP.md`
- `.harness/DECISION_LOG.md`
- `.harness/WORKFLOW.md` if the process changes
