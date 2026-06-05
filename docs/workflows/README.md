# CodePilot Workflows

> Last updated: 2026-06-05
> Source of truth: `.harness/WORKFLOW.md`

This directory provides quick workflow references for CodePilot development. Governance remains in `.harness/`; these files mirror the approved process in a more task-oriented form.

## Workflow Index

| Workflow | Use When |
|----------|----------|
| `feature-workflow.md` | Planning and implementing new product capabilities. |
| `bugfix-hotfix-workflow.md` | Fixing defects or responding to urgent production issues. |
| `release-workflow.md` | Preparing, validating, deploying, and verifying a release. |
| `harness-maintenance-workflow.md` | Updating Harness docs after repository changes or drift. |

## Ground Rules

- Repository reality wins over stale documentation.
- Documentation-only changes must not modify application behavior.
- API changes require tests, architecture updates, workflow review, and a decision log entry.
- Deployment requires explicit approval.
- Test counts must be verified with `pytest --collect-only -q`.

## Cross-References

- Full workflow: `.harness/WORKFLOW.md`
- Quality gates: `.harness/RELEASE_RULES.md`
- Audit rules: `.harness/HARNESS_AUDIT_RULES.md`
- Update matrix: `.harness/HARNESS_UPDATE_CHECKLIST.md`
