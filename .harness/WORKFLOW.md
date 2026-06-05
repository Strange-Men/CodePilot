# CodePilot - AI Engineering Workflow

> Harness version: v1.1
> Last updated: 2026-06-05

## Purpose

Define how user ideas move from request to implementation, validation, review, release, deployment, and Harness maintenance.

## Agent Responsibility Summary

| Area | Claude | Codex | User |
|------|--------|-------|------|
| Product direction | Recommends | Provides implementation input | Decides |
| Architecture | Designs and approves | Implements within design | Approves major shifts |
| Implementation | Bounded fixes/refactors/tests | Primary implementer | Requests or approves |
| Testing | Defines strategy and audits | Writes/runs tests | Accepts risk if needed |
| Release | Audits and recommends | Executes approved release steps | Approves release/deploy |
| Harness | Owns governance | Updates when instructed or syncing facts | Approves major governance changes |

## Standard Development Loop

```text
User request
  -> scope and repository inspection
  -> design or implementation plan
  -> code/docs change
  -> targeted validation
  -> Harness update if needed
  -> final summary with files and verification
```

For significant feature work:

```text
Idea -> Claude specification -> Codex implementation -> Codex validation
     -> Claude review -> Codex fixes -> release audit -> approved deployment
```

## Feature Workflow

Trigger: user requests a new feature or enhancement.

1. Clarify product outcome and non-goals.
2. Inspect current code and architecture.
3. Identify API, data, parser, LLM, frontend, deployment, and test impacts.
4. Claude records or approves the design for significant changes.
5. Codex implements in small, scoped changes.
6. Codex adds tests at the right level.
7. Codex runs validation gates.
8. Update Harness docs using `HARNESS_UPDATE_CHECKLIST.md`.
9. Claude reviews correctness, maintainability, security, and architecture.
10. Release only after hard gates pass and user approval is clear.

## Bug Fix Workflow

Trigger: user reports a defect or a defect is found during work.

1. Reproduce or explain why reproduction is not feasible.
2. Add a regression test when application code changes.
3. Implement the smallest safe fix.
4. Run targeted tests and relevant full gates.
5. Update `DECISION_LOG.md` if the bug reveals a significant design or process issue.
6. Update Harness docs if behavior, tests, or architecture changed.

## Hotfix Workflow

Trigger: production-impacting bug requiring urgent release.

1. Preserve evidence of the failure.
2. Create a minimal fix path.
3. Add or adjust regression coverage if feasible.
4. Run the fastest meaningful validation set first, then full gates where possible.
5. Claude reviews the change and release risk.
6. User approves deployment.
7. Codex deploys and verifies `/health` plus affected flow.
8. Record hotfix rationale in `DECISION_LOG.md`.

## Release Workflow

Trigger: planned version is ready for release.

1. Confirm roadmap scope is complete.
2. Run hard gates from `RELEASE_RULES.md`.
3. Run Harness audit for version, test count, architecture, and decisions.
4. Update `PROJECT_CONTEXT.md`, `TESTING.md`, `ROADMAP.md`, and `DECISION_LOG.md`.
5. Prepare release commit and tag if requested.
6. Deploy only after explicit approval.
7. Verify deployment health and smoke flow.
8. Update deployment report if deployment was performed.

## Emergency Workflow

Trigger: security incident, data corruption risk, broken production deployment, or severe availability failure.

1. Stop non-essential changes.
2. Identify blast radius.
3. Prefer rollback when a known-good state exists.
4. Preserve logs and reproduction details.
5. Patch only the smallest verified cause.
6. Run focused validation.
7. Record the incident and follow-up work in `DECISION_LOG.md` and `ROADMAP.md`.

## Workflow Rules

- Documentation-only tasks must not modify application logic.
- API contract changes require architecture, test, workflow, and decision updates.
- Deployment commands require explicit user approval.
- Harness drift must be corrected before relying on stale claims.
- Mock mode must remain usable for demos and CI.
- Windows PowerShell scripts remain first-class workflows.

## Cross-References

- Role rules: `CLAUDE.md`, `AGENTS.md`
- Quality gates: `RELEASE_RULES.md`
- Test strategy: `TESTING.md`
- Harness update triggers: `HARNESS_UPDATE_CHECKLIST.md`
- Audit rules: `HARNESS_AUDIT_RULES.md`
