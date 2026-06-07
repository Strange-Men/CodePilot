# CodePilot - Release Rules

> Harness version: v1.2
> Last updated: 2026-06-07

## Release Lifecycle

```text
Idea -> Design -> Implement -> Test -> Review -> Audit -> Commit/Tag -> Deploy -> Verify
```

Primary ownership:

- Claude: design review, architecture approval, quality audit, release recommendation.
- Codex: implementation, test execution, deployment execution after approval, verification evidence.
- User: final product priority, release approval, deployment approval.

## Versioning

Format: `v<MAJOR>.<MINOR>.<PATCH>`.

| Segment | Increment When |
|---------|----------------|
| MAJOR | Breaking changes, architecture replacement, incompatible API changes. |
| MINOR | New features, significant capability expansion, deployment target changes. |
| PATCH | Bug fixes, documentation, small config changes, dependency maintenance. |

Current project version: V2.5.

## Hard Gates

A release cannot ship unless every applicable hard gate passes.

| Gate | Command | Threshold |
|------|---------|-----------|
| Unit tests | `pytest tests/unit -v` | 100% pass |
| Integration tests | `pytest tests/integration -v` | 100% pass |
| Full test suite | `pytest` | 100% pass |
| Ruff lint | `ruff check .` | 0 warnings |
| Harness audit | `python scripts/audit_harness.py` | 0 critical drift findings |
| Frontend tests | `cd frontend && npm test` | 100% pass |
| Frontend build | `cd frontend && npm run build` | 0 errors |
| Docker build | `docker-compose build` | 0 errors when runtime/deploy files changed |
| Smoke test | `powershell -File scripts/smoke-backend.ps1` | Full pipeline pass before release |

CI currently enforces `ruff check .`, `pytest`, `python scripts/audit_harness.py --output harness-audit.json`, `npm test`, and `npm run build`.

## Soft Gates

| Gate | Expected Standard | Exception Handling |
|------|-------------------|-------------------|
| New code has tests | Yes | Record accepted gap in `DECISION_LOG.md`. |
| Docs updated | Yes for user-facing or architecture changes | Record accepted gap in `DECISION_LOG.md`. |
| No new security findings | Yes | Record risk and mitigation in `DECISION_LOG.md`. |
| Harness synchronized | Yes | Run `HARNESS_UPDATE_CHECKLIST.md`. |

## Pre-Release Checklist

- [ ] `GOAL.md` still matches product direction.
- [ ] `PROJECT_CONTEXT.md` reflects current stack, env vars, deployment, and test count.
- [ ] `ARCHITECTURE.md` reflects current modules and API contract.
- [ ] `TESTING.md` matches `pytest --collect-only -q`.
- [ ] `ROADMAP.md` has completed items marked and next work accurate.
- [ ] `DECISION_LOG.md` includes all significant decisions.
- [ ] `HARNESS_AUDIT_RULES.md` audit has no unresolved critical drift.
- [ ] `python scripts/audit_harness.py` reports zero critical drift findings.
- [ ] Hard gates pass.

## Release Checklist

- [ ] Commit is cleanly scoped.
- [ ] Commit message follows convention.
- [ ] Version/tag decision is clear.
- [ ] Deployment approval is explicit.
- [ ] Frontend deployment is verified if frontend changed.
- [ ] Backend deployment is verified if backend/runtime changed.
- [ ] `/health` returns 200 after backend deployment.
- [ ] Smoke flow succeeds against intended target.

## Rollback Rules

| Scenario | Action |
|----------|--------|
| Health check fails after deploy | Roll back immediately and investigate. |
| Smoke test fails after deploy | Roll back unless failure is confirmed external/transient and user approves holding. |
| API contract regression | Roll back or hotfix before further release work. |
| Data corruption risk | Stop deployment, preserve evidence, restore from known-good state. |
| Security vulnerability introduced | Roll back or patch immediately. |
| Performance regression over 50% on core flow | Roll back or document user-approved mitigation. |

## Hotfix Rules

1. Reproduce the failure.
2. Add or update a regression test when code changes.
3. Implement the smallest safe fix.
4. Run targeted tests and full release gates as time permits.
5. Record the hotfix rationale in `DECISION_LOG.md`.
6. Deploy only after approval.
7. Verify health and affected flow.

## Deployment Targets

| Component | Target | Method |
|-----------|--------|--------|
| Frontend | Vercel | Git-connected deployment configured in platform UI. |
| Backend | Render | Docker deployment using `Dockerfile.backend`, configured in platform UI. |
| Local | Docker Compose | `docker-compose up`. |

## Cross-References

- Workflow details: `WORKFLOW.md`
- Current deployment facts: `PROJECT_CONTEXT.md`
- Test strategy: `TESTING.md`
- Decision record: `DECISION_LOG.md`
- Harness audit: `HARNESS_AUDIT_RULES.md`
