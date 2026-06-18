# Release Workflow

> Last updated: 2026-06-05
> Source of truth: `.harness/RELEASE_RULES.md`

Use this workflow when preparing a versioned release or deployment.

## Pre-Release

1. Confirm release scope in `.harness/ROADMAP.md`.
2. Verify `.harness/PROJECT_CONTEXT.md` reflects current stack, API, env vars, deployment, and test count.
3. Verify `.harness/ARCHITECTURE.md` matches current modules and endpoints.
4. Verify `.harness/TESTING.md` matches `pytest --collect-only -q`.
5. Verify `.harness/DECISION_LOG.md` includes significant decisions.
6. Run `.harness/HARNESS_AUDIT_RULES.md` checks.

## Hard Gates

```powershell
pytest tests/unit -v
pytest tests/integration -v
pytest
ruff check .
cd frontend
npm run build
```

When release scope affects runtime or deployment:

```powershell
docker-compose build
powershell -File scripts/smoke-backend.ps1
```

## Deployment

Deployment requires explicit approval.

| Component | Target | Verification |
|-----------|--------|--------------|
| Backend | Render Docker service | `/health` returns 200 and review flow works. |
| Frontend | Vercel Next.js app | App loads and can reach configured API base. |
| Local | Docker Compose | Both services start and connect. |

## Post-Release

- Update `.harness/PROJECT_CONTEXT.md` version and release notes.
- Update `.harness/ROADMAP.md`.
- Add release decision in `.harness/DECISION_LOG.md`.
- Update `docs/setup/DEPLOYMENT_REPORT.md` if deployment validation was performed.
