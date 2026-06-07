# CodePilot - AI Engineering Workflow

> Harness version: v1.2
> Last updated: 2026-06-05

## Purpose

Define how user ideas move from request to implementation, validation, review, release, deployment, and Harness maintenance.

## Participants

| Participant | Role |
|-------------|------|
| Human | Product direction, final approval |
| Claude | Architecture, review, QA, release approval |
| Codex | Implementation, testing, refactoring, deployment preparation |

## Handoff Rules

A handoff is a specific moment with a specific artifact. Ownership transfers explicitly, not gradually.

| From | To | Trigger | Artifact | Blocking |
|------|----|---------|----------|----------|
| Human → Claude | Human states a request | Request text | Yes — Claude scopes before Codex touches code |
| Claude → Codex | Design approved or scope clarified | Design spec or fix scope | Yes — Codex waits for spec |
| Codex → Claude | Implementation complete, gates pass | Summary with files changed, test results, gate output | Yes — Claude reviews before release |
| Claude → Human | Review complete | Review summary with risk assessment | Yes — Human approves before deploy |
| Codex → Claude | Architecture conflict or ambiguity found | Escalation message with options | Yes — Claude resolves before Codex continues |
| Claude → Codex | Review finds issues | Specific required changes | Yes — Codex fixes before re-submitting |

## Escalation Rules

Escalation is a structured handoff back to Claude with a decision Claude must make.

| Trigger | Who Escalates | Claude Decides |
|---------|---------------|----------------|
| Implementation requires architecture change | Codex | Accept deviation, redesign, or reject |
| Pre-existing test failure found | Codex | Fix now, defer, or document gap |
| Ambiguous requirement with ≥2 valid interpretations | Codex | Choose interpretation or clarify with Human |
| Deployment environment differs from docs | Codex | Accept deviation, fix docs, or stop |
| Release gate fails | Either | Block release, accept risk with docs, or fix |
| Harness drift detected | Either | Severity classification and fix priority |
| Security finding in new code | Codex | Severity and fix priority |
| Human changes direction mid-implementation | Human → Claude | Re-scope, pivot, or reject |
| Performance regression detected | Codex | Accept, optimize, or document |

Escalation format:

```
ESCALATION: [one-line summary]
Context: [what was being done]
Conflict: [what doesn't fit]
Options: [2-3 concrete options with trade-offs]
Recommendation: [Codex's preferred option, if any]
```

Claude responds with a decision. Codex does not proceed until the decision is received.

## Anti-Patterns

| Anti-Pattern | Description | Prevention |
|--------------|-------------|------------|
| Ghost handoff | Codex starts before Claude scopes | Every workflow starts with Claude scoping |
| Review vacuum | Codex finishes but Claude never reviews | Codex submits summary; Claude must acknowledge |
| Scope creep by stealth | Codex adds unrequested changes | Flag as escalation, not side commits |
| Harness drift by omission | Code changes without checking Harness docs | Run update checklist after every non-trivial change |
| Release without evaluation | Release with only unit tests passing | v1.2 requires evaluation harness pass |
| Rollback indecision | Health check fails but team debates | Rollback is default; holding requires Human approval |
| Escalation without options | "This is ambiguous" with no interpretations | Escalation must include 2-3 options |
| Audit theater | Audit runs but findings unresolved | Critical drift blocks release |
| Silent gate skip | Gate "temporarily" skipped without recording | Every skip requires decision log entry |
| Handoff without verification | Claude approves without running gates | Review includes gate verification |

## Standard Development Loop

```text
Human request
  -> Claude scopes and inspects repository
  -> Claude produces design spec or fix scope
  -> Handoff: Claude → Codex
  -> Codex implements, tests, runs gates
  -> Handoff: Codex → Claude (summary + gate results)
  -> Claude reviews correctness, security, architecture
  -> Claude updates Harness if needed
  -> Handoff: Claude → Human (review summary)
  -> Human approves or requests changes
```

## New Feature Workflow

Trigger: Human requests a new feature or enhancement.

### Phase 1: Scoping (Claude)

1. Clarify product outcome and non-goals with Human.
2. Inspect current code and architecture.
3. Identify API, data, parser, LLM, frontend, deployment, and test impacts.
4. Record design decisions in `DECISION_LOG.md` for significant changes.
5. Produce a design spec: what changes, what modules, what tests, what risks.

### Phase 2: Implementation (Codex)

6. Receive design spec from Claude.
7. Implement in small, scoped changes following existing patterns.
8. Add tests at the right level (unit for modules, integration for endpoints).
9. Run validation gates: `ruff check .`, `pytest`, `npm test`, and `npm run build` when applicable.
10. Update Harness docs using `HARNESS_UPDATE_CHECKLIST.md`.
11. Submit summary to Claude: files changed, tests added, gate results, Harness updates.

### Phase 3: Review (Claude)

12. Review for correctness, security, maintainability, architecture alignment.
13. Verify gates passed (do not trust summary alone).
14. Run `HARNESS_UPDATE_CHECKLIST.md` to verify Harness is current.
15. If issues found: return specific required changes to Codex (return to Phase 2).
16. If approved: update `ROADMAP.md`, recommend release to Human.

### Phase 4: Release (Human)

17. Human approves release.
18. Execute Release Workflow.

## Bug Fix Workflow

Trigger: Human reports a defect or a defect is found during work.

### Phase 1: Triage (Claude)

1. Reproduce or explain why reproduction is not feasible.
2. Classify severity: Critical (blocks users), Major (degrades experience), Minor (cosmetic/edge).
3. Determine if this is a hotfix (see Emergency Hotfix Workflow) or a standard fix.
4. Define fix scope: smallest safe change, what module, what test needed.

### Phase 2: Fix (Codex)

5. Receive fix scope from Claude.
6. Add a regression test under `tests/regressions/` (numbered, per `REGRESSION_RULES.md`).
7. Implement the smallest safe fix.
8. Run targeted tests and relevant full gates.
9. Submit summary to Claude: fix description, regression test, gate results.

### Phase 3: Review (Claude)

10. Review fix correctness and regression coverage.
11. Verify gates passed.
12. Update `DECISION_LOG.md` if the bug reveals a significant design or process issue.
13. Update Harness docs if behavior, tests, or architecture changed.
14. Approve or request changes.

## Release Workflow

Trigger: planned version is ready for release.

### Phase 1: Pre-Release Audit (Claude)

1. Confirm roadmap scope for this version is complete.
2. Run automated harness audit script (when available) to verify document-reality alignment.
3. Run evaluation harness: `python evaluation/run_eval.py`.
4. Verify evaluation report shows zero Critical failures.
5. Run hard gates from `RELEASE_RULES.md`:

| Gate | Command | Threshold |
|------|---------|-----------|
| Unit tests | `pytest tests/unit -v` | 100% pass |
| Integration tests | `pytest tests/integration -v` | 100% pass |
| Full test suite | `pytest` | 100% pass |
| Ruff lint | `ruff check .` | 0 warnings |
| Frontend build | `cd frontend && npm run build` | 0 errors |
| Frontend tests | `cd frontend && npm test` | 100% pass |
| Docker build | `docker-compose build` | 0 errors when runtime/deploy files changed |
| Smoke test | `powershell -File scripts/smoke-backend.ps1` | Full pipeline pass |
| Evaluation | `python evaluation/run_eval.py` | 0 Critical failures |

6. Run Harness audit per `HARNESS_AUDIT_RULES.md`.
7. Update `PROJECT_CONTEXT.md`, `TESTING.md`, `ROADMAP.md`, and `DECISION_LOG.md`.

### Phase 2: Release Approval (Human)

8. Claude presents release summary to Human: what changed, gate results, evaluation results, risk assessment.
9. Human approves or requests changes.

### Phase 3: Commit and Deploy (Codex)

10. Prepare release commit and tag per versioning rules.
11. Deploy only after explicit Human approval.
12. Verify `/health` returns 200 after backend deployment.
13. Run smoke flow against intended target.
14. Update deployment report if deployment was performed.

### Phase 4: Post-Release (Claude)

15. Verify deployment health and smoke flow succeeded.
16. Mark completed items in `ROADMAP.md`.
17. Record release in `DECISION_LOG.md`.

## Emergency Hotfix Workflow

Trigger: security incident, data corruption risk, broken production deployment, or severe availability failure.

### Phase 1: Triage (Claude + Human)

1. Stop non-essential changes.
2. Identify blast radius.
3. **Decision point:** Is a known-good state available?
   - **Yes, and rollback is safe:** Roll back immediately. Proceed to Phase 3.
   - **No, or rollback is not safe:** Proceed to Phase 2.

### Phase 2: Patch (Codex, fast-track)

4. Preserve evidence of the failure (logs, reproduction details).
5. Create the smallest verified fix.
6. Add or adjust regression coverage if feasible.
7. Run the fastest meaningful validation set first.
8. Claude reviews the change and release risk (fast-track review, not full review).
9. Human approves deployment.

### Phase 3: Deploy and Verify (Codex)

10. Deploy the fix or rolled-back state.
11. Verify `/health` plus affected flow.
12. Record hotfix rationale in `DECISION_LOG.md`.
13. Record follow-up work in `ROADMAP.md` if the fix was a patch, not a root cause fix.

### Phase 4: Post-Mortem (Claude)

14. Within 48 hours, document what happened, why, and how to prevent recurrence.
15. Add regression test if not already added in Phase 2.
16. Update Harness docs if the incident revealed process gaps.

## Harness Maintenance Workflow

Trigger: any of the following:
- Code change that affects modules, endpoints, tests, dependencies, deployment, or roadmap.
- Quarterly review if the project is actively maintained.
- Harness drift detected during any workflow.
- Release audit.

### Phase 1: Classify Change (Claude or Codex)

1. Identify the change type using `HARNESS_UPDATE_CHECKLIST.md` trigger matrix.
2. Identify which documents are affected (Update, Review, or No).

### Phase 2: Audit Claims (Claude or Codex)

3. Read each affected document.
4. Compare claims against repository reality:
   - Test count → `pytest --collect-only -q`
   - Dependencies → `requirements.txt`, `package.json`
   - Env vars → `backend/core/config.py`, `.env.example`
   - API contract → `backend/api/reviews.py`, `backend/models/review.py`
   - CI gates → `.github/workflows/ci.yml`
   - Deployment → Dockerfiles, `docker-compose.yml`, deployment docs
5. Classify mismatches per `HARNESS_AUDIT_RULES.md` severity levels.

### Phase 3: Fix (Claude or Codex)

6. Fix Critical drift immediately before continuing any other work.
7. Fix Minor drift in the current change when practical.
8. Fix Informational drift opportunistically.
9. Record significant drift in `DECISION_LOG.md`.
10. Verify cross-references after edits.

### Phase 4: Verify (Claude)

11. Run cross-reference checklist from `HARNESS_UPDATE_CHECKLIST.md`.
12. Confirm no new drift was introduced by the fixes.

## Workflow Rules

- Documentation-only tasks must not modify application logic.
- API contract changes require architecture, test, workflow, and decision updates.
- Deployment commands require explicit Human approval.
- Harness drift must be corrected before relying on stale claims.
- Mock mode must remain usable for demos and CI.
- Windows PowerShell scripts remain first-class workflows.
- Every non-trivial change runs through the Harness Maintenance Workflow.
- Every production bug gets a numbered regression per `REGRESSION_RULES.md`.

## Cross-References

- Role rules: `CLAUDE.md`, `AGENTS.md`
- Quality gates: `RELEASE_RULES.md`
- Test strategy: `TESTING.md`
- Harness update triggers: `HARNESS_UPDATE_CHECKLIST.md`
- Audit rules: `HARNESS_AUDIT_RULES.md`
- Regression rules: `REGRESSION_RULES.md`
