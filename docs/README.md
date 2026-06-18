# CodePilot Documentation

Documentation index for the CodePilot project — an AI Code Review & Refactor Agent for Large Repositories.

---

## Current Release

**V3.7** — Stable demo release. CI green. 995 backend + 104 frontend tests passing.

| Document | Description |
|----------|-------------|
| [V3.7 Release Notes](releases/v3.7/V3.7_RELEASE_NOTES.md) | Highlights, fixes, test results, known limitations |
| [V3.7 Project Closure](releases/v3.7/V3.7_PROJECT_CLOSURE.md) | Full closure report, verification results, resume-ready summary |
| [V3.7 Release Audit](releases/v3.7/V3.7_RELEASE_AUDIT.md) | Harness audit results |

---

## Product Documentation

| Document | Description |
|----------|-------------|
| [Setup Guide](setup/SETUP.md) | Installation and environment configuration |
| [Architecture](architecture/ARCHITECTURE.md) | System design, module map, data flow |
| [Roadmap](product/ROADMAP.md) | Completed work, planned items, deferred scope |
| [Resume Value](product/RESUME_VALUE.md) | What CodePilot demonstrates for resume/portfolio |
| [Design System](product/DESIGN.md) | Visual language and UI design system |
| [Deployment Guide](setup/DEPLOYMENT.md) | Backend/frontend deployment to Render and Vercel |
| [Deployment Report](setup/DEPLOYMENT_REPORT.md) | V1.1 deployment validation report |
| [Vercel Deployment](setup/VERCEL_DEPLOYMENT.md) | Frontend deployment to Vercel |

---

## Workflow Documentation

| Document | Description |
|----------|-------------|
| [Workflows Overview](workflows/README.md) | Workflow index |
| [Feature Workflow](workflows/feature-workflow.md) | How to add a new feature |
| [Bugfix/Hotfix Workflow](workflows/bugfix-hotfix-workflow.md) | How to fix bugs |
| [Release Workflow](workflows/release-workflow.md) | How to cut a release |
| [Harness Maintenance](workflows/harness-maintenance-workflow.md) | How to update governance docs |

---

## Harness & Governance

Project governance lives in `../.harness/`. Key files:

| Document | Description |
|----------|-------------|
| [.harness/GOAL.md](../.harness/GOAL.md) | Mission, success criteria, non-goals |
| [.harness/PROJECT_CONTEXT.md](../.harness/PROJECT_CONTEXT.md) | Version, stack, constraints, env vars |
| [.harness/ARCHITECTURE.md](../.harness/ARCHITECTURE.md) | System design decisions |
| [.harness/TESTING.md](../.harness/TESTING.md) | Test pyramid, inventory, conventions |
| [.harness/ROADMAP.md](../.harness/ROADMAP.md) | Completed, planned, and future work |
| [.harness/DECISION_LOG.md](../.harness/DECISION_LOG.md) | Key decisions record |
| [.harness/RELEASE_RULES.md](../.harness/RELEASE_RULES.md) | Quality gates and release checklist |

---

## Historical Development Notes

Step-by-step implementation notes from V3.5 through V3.7. Archived for reference — not needed to understand or demo the product.

<details>
<summary>V3.5.9 — Performance, benchmark, quality audit (10 docs)</summary>

- [V3.5.9 Release Notes](history/v3/V3.5.9_RELEASE_NOTES.md)
- [V3.5.9 Release Audit](history/v3/V3.5.9_RELEASE_AUDIT.md)
- [V3.5.9 Step 1 — Performance Audit](history/v3/V3.5.9_STEP1_PERFORMANCE_AUDIT.md)
- [V3.5.9 Step 2 — Concurrency Benchmark](history/v3/V3.5.9_STEP2_CONCURRENCY4_BENCHMARK.md)
- [V3.5.9 Step 2.5 — Real MiMo Benchmark](history/v3/V3.5.9_STEP2_5_REAL_MIMO_BENCHMARK.md)
- [V3.5.9 Step 3 — Finding Quality Audit](history/v3/V3.5.9_STEP3_FINDING_QUALITY_AUDIT.md)
- [V3.5.9 Step 3.5 — Real MiMo Quality Validation](history/v3/V3.5.9_STEP3_5_REAL_MIMO_QUALITY_VALIDATION.md)
- [V3.5.9 Step 4 — CodeSmell Validation Fix](history/v3/V3.5.9_STEP4_CODESMELL_VALIDATION_FIX.md)
- [V3.5.9 Step 4.5 — Real CodeSmell Smoke](history/v3/V3.5.9_STEP4_5_REAL_CODESMELL_SMOKE.md)
- [V3.5.9 Step 5 — Report Usefulness & zh Polish](history/v3/V3.5.9_STEP5_REPORT_USEFULNESS_AND_ZH_POLISH.md)

</details>

<details>
<summary>V3.5.10 — Grouped agent mode (7 docs)</summary>

- [V3.5.10 Release Notes](history/v3/V3.5.10_RELEASE_NOTES.md)
- [V3.5.10 Release Audit](history/v3/V3.5.10_RELEASE_AUDIT.md)
- [V3.5.10 MiMo Provider Hotfix](history/v3/V3.5.10_MIMO_PROVIDER_HOTFIX.md)
- [V3.5.10 Step 1 — Grouped Agents Design](history/v3/V3.5.10_STEP1_GROUPED_AGENTS_DESIGN.md)
- [V3.5.10 Step 2 — Grouped Mode Implementation](history/v3/V3.5.10_STEP2_GROUPED_MODE_IMPLEMENTATION.md)
- [V3.5.10 Step 3 — Grouped Benchmark](history/v3/V3.5.10_STEP3_GROUPED_BENCHMARK.md)
- [V3.5.10 Step 4 — Grouped Stabilization](history/v3/V3.5.10_STEP4_GROUPED_STABILIZATION.md)

</details>

<details>
<summary>V3.5.11 — Hotfix validation (2 docs)</summary>

- [V3.5.11 Release Notes](history/v3/V3.5.11_RELEASE_NOTES.md)
- [V3.5.11 Hotfix Validation](history/v3/V3.5.11_HOTFIX_VALIDATION.md)

</details>

<details>
<summary>V3.5.12 — Product usability & Chinese quality (6 docs)</summary>

- [V3.5.12 Product Usability Plan](history/v3/V3.5.12_PRODUCT_USABILITY_PLAN.md)
- [V3.5.12 Step 1 — Export & Stale History](history/v3/V3.5.12_STEP1_EXPORT_STALE_HISTORY.md)
- [V3.5.12 Step 2 — Self-Contained Evidence](history/v3/V3.5.12_STEP2_SELF_CONTAINED_EVIDENCE.md)
- [V3.5.12 Step 3 — Chinese Quality Guard](history/v3/V3.5.12_STEP3_CHINESE_QUALITY_GUARD.md)
- [V3.5.12 Step 3.5 — Product Acceptance](history/v3/V3.5.12_STEP3_5_PRODUCT_ACCEPTANCE.md)
- [V3.5.12 Final zh Quality Fix](history/v3/V3.5.12_FINAL_ZH_QUALITY_FIX.md)

</details>

<details>
<summary>V3.6 — UI polish (1 doc)</summary>

- [V3.6 UI Polish](history/v3/V3.6_UI_POLISH.md)

</details>

<details>
<summary>V3.7 — Implementation steps (4 docs)</summary>

- [V3.7 Step 1 — zh Presentation Pipeline](history/v3/V3.7_STEP1_ZH_PRESENTATION_PIPELINE.md)
- [V3.7 Step 1.1 — zh Leakage Gate](history/v3/V3.7_STEP1_1_ZH_LEAKAGE_GATE.md)
- [V3.7 Step 2 — Global Language Switch](history/v3/V3.7_STEP2_GLOBAL_LANGUAGE_SWITCH.md)
- [V3.7 Step 3 — MiMo zh Fallback](history/v3/V3.7_STEP3_MIMO_ZH_FALLBACK.md)

</details>

<details>
<summary>Earlier V3 architecture & planning (9 docs)</summary>

- [V3 Overview](history/v3/V3.md)
- [V3 Architecture](history/v3/V3_ARCHITECTURE.md)
- [V3 Readiness](history/v3/V3_READINESS.md)
- [V3 Agent Development](history/v3/V3_AGENT_DEVELOPMENT.md)
- [V3.2 Retrieval](history/v3/V3_2_RETRIEVAL.md)
- [V3.3 Workflows](history/v3/V3_3_WORKFLOWS.md)
- [V3.4 Report Quality](history/v3/V3_4_REPORT_QUALITY.md)
- [V3.5 Evaluation](history/v3/V3_5_EVALUATION.md)
- [Harness Design v1](history/v3/harness_design_v1.md)

</details>

<details>
<summary>V3.5.3 — Full project audit (1 doc)</summary>

- [V3.5.3 Full Audit](history/v3/V3.5.3_FULL_AUDIT.md) — Comprehensive product, architecture, test, and deployment audit

</details>

---

## Docs Useful for Resume/Demo

These are the most relevant documents for a resume reviewer or demo audience:

1. **[../README.md](../README.md)** — Project overview, features, quick start, demo flow
2. **[Release Notes](releases/v3.7/V3.7_RELEASE_NOTES.md)** — What V3.7 ships
3. **[Project Closure](releases/v3.7/V3.7_PROJECT_CLOSURE.md)** — Verification results, resume-ready conclusion
4. **[Architecture](architecture/ARCHITECTURE.md)** — System design and data flow
5. **[Resume Value](product/RESUME_VALUE.md)** — What CodePilot demonstrates

---

## Known Limitations

See [V3.7 Release Notes — Known Limitations](releases/v3.7/V3.7_RELEASE_NOTES.md#known-limitations) for the full list.

In brief: MiMo Chinese output has occasional quirks, storage is ephemeral on free tiers, analysis is strongest for Python, and real LLM mode requires a working API key. Mock mode is the stable demo path.
