# CodePilot - Harness Update Checklist

> Harness version: v1.1
> Last updated: 2026-06-05

## Purpose

Keep Harness documents synchronized with repository reality after product, architecture, test, deployment, workflow, and process changes.

## Trigger Matrix

| Change Type | GOAL | PROJECT_CONTEXT | CLAUDE | AGENTS | WORKFLOW | TESTING | RELEASE_RULES | ARCHITECTURE | DECISION_LOG | ROADMAP | AUDIT_RULES |
|-------------|------|-----------------|--------|--------|----------|---------|---------------|--------------|--------------|---------|-------------|
| New feature implemented | Review | Update | No | No | Review | Update | Review | Update if structural | Add | Update | No |
| Bug fix | No | Review | No | No | No | Update if test added | No | Review | Add if significant | Review | No |
| Architecture change | Review | Update | Review | Review | Update | Review | Review | Update | Add | Update | Review |
| New dependency | No | Update | No | No | No | Review | Review | Update | Add | Review | No |
| Dependency removed | No | Update | No | No | No | Review | Review | Update | Add | Review | No |
| Deployment change | Review | Update | No | No | Update | Review | Update | Review | Add | Update | No |
| New environment variable | No | Update | No | No | No | No | Review | Review | Add if significant | No | No |
| API endpoint change | Review | Update | No | No | Update | Update | Review | Update | Add | Update | No |
| New test file or count change | No | Update | No | No | No | Update | Review | No | No | Review | No |
| Version release | Review | Update | No | No | Update | Update | Update | Review | Add | Update | Review |
| Technology swap | Review | Update | Update | Update | Update | Update | Update | Update | Add | Update | Review |
| Process change | No | Review | Update | Update | Update | No | Update | No | Add | No | Review |
| New placeholder directory | No | Update | No | No | No | No | No | Update | Review | Update | No |
| Runtime version change | Review | Update | No | No | No | Review | Update | Update | Add | Review | No |
| New agent type | Review | Update | Update | Update | Update | Update | Review | Update | Add | Update | Review |
| Agent workflow change | No | Review | Update | Update | Update | No | Review | Review | Add | Review | Review |
| Harness drift detected | Review | Update | Review | Review | Review | Review | Review | Review | Add if significant | Review | Review |

Legend:

- `Update`: document must be checked and changed when facts differ.
- `Review`: document must be read for impact but may not require edits.
- `No`: no expected update unless the specific change affects that document.

## Update Workflow

1. Classify the change using the trigger matrix.
2. Read the affected Harness documents.
3. Compare each claim against repository state.
4. Apply `HARNESS_AUDIT_RULES.md` for any suspected drift.
5. Update every affected document in the same change.
6. Verify cross-references.
7. Add or update `DECISION_LOG.md` for significant decisions.
8. Run appropriate validation commands.

## Repository Reality Checks

| Claim Type | Check Against |
|------------|---------------|
| Backend dependencies | `backend/requirements.txt`, `backend/requirements-dev.txt` |
| Frontend dependencies | `frontend/package.json`, `frontend/package-lock.json` |
| Runtime versions | `.python-version`, `runtime.txt`, Dockerfiles, CI |
| Environment variables | `backend/core/config.py`, `.env.example` |
| API contract | `backend/api/reviews.py`, `backend/models/review.py`, tests |
| Test count | `pytest --collect-only -q` |
| CI gates | `.github/workflows/ci.yml` |
| Deployment | `docs/setup/DEPLOYMENT.md`, `docs/setup/VERCEL_DEPLOYMENT.md`, Dockerfiles, `docker-compose.yml` |
| Architecture | Actual directory and module structure |

## Cross-Reference Checklist

- [ ] `GOAL.md` success criteria match `PROJECT_CONTEXT.md` and `ROADMAP.md`.
- [ ] `PROJECT_CONTEXT.md` stack and constraints match actual files.
- [ ] `ARCHITECTURE.md` modules and endpoints match code.
- [ ] `TESTING.md` count matches pytest collection.
- [ ] `RELEASE_RULES.md` gates match CI and scripts.
- [ ] `ROADMAP.md` completed items are supported by repository evidence.
- [ ] `DECISION_LOG.md` contains decisions referenced by architecture and roadmap.
- [ ] `WORKFLOW.md` includes current agent responsibilities.
- [ ] Root `CLAUDE.md` references all Harness documents.

## Self-Improvement Rules

Run a Harness review:

- After every release.
- After major architecture changes.
- When a Harness document is discovered stale.
- Quarterly if the project is actively maintained.

During review:

1. Remove duplicate or obsolete guidance.
2. Add missing trigger types to this checklist.
3. Split documents only when length blocks usefulness.
4. Merge documents only when separate files no longer carry distinct responsibility.
5. Record governance changes in `DECISION_LOG.md`.

## Quick Reference

| I Just... | Update These |
|-----------|--------------|
| Added a backend module | `PROJECT_CONTEXT.md`, `ARCHITECTURE.md`, `TESTING.md`, `DECISION_LOG.md` |
| Added an API endpoint | `PROJECT_CONTEXT.md`, `ARCHITECTURE.md`, `TESTING.md`, `WORKFLOW.md`, `DECISION_LOG.md` |
| Changed deployment | `PROJECT_CONTEXT.md`, `RELEASE_RULES.md`, `WORKFLOW.md`, `DECISION_LOG.md` |
| Added an env var | `PROJECT_CONTEXT.md`, `.env.example`, `DECISION_LOG.md` if significant |
| Added tests | `TESTING.md`, `PROJECT_CONTEXT.md` if count changes |
| Released a version | `PROJECT_CONTEXT.md`, `TESTING.md`, `RELEASE_RULES.md`, `ROADMAP.md`, `DECISION_LOG.md` |
| Changed agent roles | `CLAUDE.md`, `AGENTS.md`, `WORKFLOW.md`, `DECISION_LOG.md` |
| Found drift | Apply `HARNESS_AUDIT_RULES.md`; update affected docs |

## Cross-References

- Audit protocol: `HARNESS_AUDIT_RULES.md`
- Workflow: `WORKFLOW.md`
- Decision record: `DECISION_LOG.md`
