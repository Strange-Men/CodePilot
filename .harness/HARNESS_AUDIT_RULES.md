# CodePilot - Harness Audit Rules

> Harness version: v1.2
> Last updated: 2026-06-05

## Purpose

Prevent Harness documents from drifting away from repository reality. Harness docs guide decisions, so stale claims must be detected and corrected quickly.

## Core Principle

Repository reality wins over outdated documentation.

Harness documents are authoritative only after their claims have been checked against source files, tests, configuration, and current repository state.

## Audit Protocol

Before any significant Harness update:

1. Identify the claims being touched.
2. Check each claim against repository evidence.
3. Classify mismatches by severity.
4. Correct stale docs.
5. Record significant drift in `DECISION_LOG.md`.
6. Verify cross-references after edits.

## Automated Enforcement

Run the lightweight audit script before release and in CI:

```powershell
python scripts/audit_harness.py --output harness-audit.json
```

The script emits machine-readable JSON and exits with status `1` when it finds critical Harness drift. CI treats that exit code as a hard gate.

## What to Check

| Harness Document | Compare Against |
|------------------|-----------------|
| `GOAL.md` | Current product behavior, roadmap, release rules. |
| `PROJECT_CONTEXT.md` | `frontend/package.json`, backend requirements, `.env.example`, `backend/core/config.py`, CI, deployment docs. |
| `ARCHITECTURE.md` | Actual `backend/`, `frontend/`, scripts, API route code, models. |
| `TESTING.md` | `pytest --collect-only -q`, test files, smoke script. |
| `RELEASE_RULES.md` | `.github/workflows/ci.yml`, scripts, Docker files, deployment docs. |
| `ROADMAP.md` | Codebase, tests, decision log, completed release evidence. |
| `DECISION_LOG.md` | Architecture, deployment, runtime, and process state. |
| `CLAUDE.md` / `AGENTS.md` | Current approved role design and workflow. |
| `WORKFLOW.md` | Role docs, release rules, actual development process. |

## Drift Severity

| Severity | Definition | Required Action |
|----------|------------|-----------------|
| Critical | Could cause a wrong implementation, release, security, or deployment decision. | Fix immediately before continuing. |
| Minor | Inaccurate but unlikely to cause wrong decisions. | Fix in current Harness update when practical. |
| Informational | Formatting, wording, or cosmetic inconsistency. | Fix opportunistically. |

## Drift Examples

- `TESTING.md` says 44 tests but pytest collects a different number.
- `PROJECT_CONTEXT.md` lists a dependency version not present in lock/requirements files.
- `ARCHITECTURE.md` documents an endpoint that no longer exists.
- `ROADMAP.md` marks a feature planned when it has shipped.
- `RELEASE_RULES.md` lists gates not reflected in CI or scripts.

## Audit Report

Create `.harness/HARNESS_AUDIT_REPORT.md` when significant unresolved drift is found or when a release audit needs a persisted trail.

Format:

```markdown
# Harness Audit Report

> Date: YYYY-MM-DD
> Auditor: Claude | Codex
> Trigger: <reason>

## Summary

- Documents audited: N
- Mismatches found: N
- Critical: N
- Minor: N
- Informational: N

## Findings

| Document | Claim | Reality | Severity | Resolution |
|----------|-------|---------|----------|------------|

## Post-Audit

- [ ] All critical findings resolved
- [ ] Decision log updated if needed
- [ ] Cross-references verified
```

Audit reports are working artifacts; remove or supersede them after all findings are resolved unless the user wants them retained.

## Current Audit Baseline

During Harness v1.1 installation on 2026-06-05:

- `pytest --collect-only -q` collected 44 tests.
- Backend API routes matched `ARCHITECTURE.md` and `PROJECT_CONTEXT.md`.
- CI matched `RELEASE_RULES.md` for ruff, pytest, and frontend build.
- Missing v1.1 files (`WORKFLOW.md`, `HARNESS_AUDIT_RULES.md`) were installed.
- Stale role rules in `CLAUDE.md` and `AGENTS.md` were corrected to match approved v1.1 design.

No unresolved critical drift remains from this install.

During Harness v1.2 enforcement on 2026-06-05:

- `scripts/audit_harness.py` was added as the machine-readable audit gate.
- CI was updated to run the audit and fail on critical Harness drift.
- `pytest --collect-only -q` collected 46 tests after regression harness installation.

## Cross-References

- Update triggers: `HARNESS_UPDATE_CHECKLIST.md`
- Decisions: `DECISION_LOG.md`
- Workflow: `WORKFLOW.md`
