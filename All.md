# CodePilot V3.5.3 Full Project Audit

**Audit Date:** 2026-06-13
**Auditor Role:** Senior Software Architect / Product Auditor / Release Reviewer
**Scope:** Full CodePilot project (backend, frontend, evaluation, tests, deployment, docs)
**Constraint:** Audit only — no code changes, no commits, no version bumps

---

## 1. Executive Summary

| Dimension | Score (0-10) | Notes |
|-----------|:---:|-------|
| **Overall Health** | **6.5** | Functional but accumulating debt. Not broken, not clean. |
| **Product Readiness** | **6** | Core flow works. Several features are technically present but weak UX. |
| **Frontend UX** | **5.5** | Report readable, progress visible. Missing polish, no navigation, fragile parsing. |
| **Backend Architecture** | **7** | Agent pattern clean. Context models messy. Evidence system strong. |
| **Test Confidence** | **7** | 327 tests, strong security coverage. Gaps in concurrency, frontend integration, and real-user flows. |
| **Deployment Readiness** | **5** | Works locally. Production path manual, docs stale, no IaC, ephemeral storage. |

**What works well:**
- The multi-agent evidence-grounded architecture is well-designed and prevents hallucinated findings.
- The security posture is strong: multi-layer redaction, no secret leakage, safe error handling.
- The backend task lifecycle is clean: sequential status transitions, proper cleanup, thread-safe progress.
- The thin-subclass agent pattern has zero code duplication.
- The evaluation platform provides deterministic CI-safe quality checks.

**What does not work well:**
- The frontend parses markdown that the backend generates, creating a fragile implicit contract.
- The dual `ReviewContext`/`RepositoryContext` model system is the single largest source of fragility.
- Progress memory is never cleaned up. Stale tasks are never recovered.
- The evaluation platform does not cover V3.5.1, V3.5.2, or V3.5.3 features.
- Documentation is stale: multiple harness docs reference V3.1 or test counts from weeks ago.
- V3 reports are missing sections that the frontend expects (Repository Insights, Metrics, Architecture Graph).

---

## 2. Overall Verdict

**Do V3.5.4 frontend refactor first.**

The project is not in crisis, but it is at an inflection point. The backend is reasonably solid (7/10) but the frontend (5.5/10) is the weakest layer. The core problem is that the frontend re-parses markdown that the backend generates — this creates an implicit, fragile, duplicated contract that will break on any backend report format change. Before V3.6 adds more features, this contract must be replaced with a structured API.

V3.5.4 should be a focused frontend refactor with minimal backend API additions. It should NOT be a full stabilization pass (the backend has issues but they are not blocking). It should NOT start V3.6 feature work.

---

## 3. System Map

### Actual Current Flow

```
User (browser)
  │
  ├─ POST /api/reviews {repo_url, llm_mode}
  │    │
  │    ▼
  │  ReviewTaskRunner.submit()
  │    ├─ Validate LLM mode (build client, discard)
  │    ├─ store.create_review(status=pending)
  │    ├─ _initialize_progress() [v3_multi_agent only]
  │    └─ ThreadPoolExecutor.submit(_run)
  │         │
  │         ▼
  │       ReviewPipeline.run(task_id, repo_url)
  │         ├─ _clone_repository()    → status=cloning
  │         ├─ _build_manifest()      → sandbox filter
  │         ├─ _build_context()       → status=parsing, indexer
  │         ├─ _record_summarized()   → status=summarizing
  │         ├─ _generate_report()     → status=reviewing
  │         │    ├─ AgentOrchestrator.run()
  │         │    │    ├─ ArchitectureAgent.review()  → LLM call
  │         │    │    ├─ CodeSmellAgent.review()     → LLM call
  │         │    │    ├─ MaintainabilityAgent.review() → LLM call
  │         │    │    └─ RefactorAgent.review()      → LLM call
  │         │    ├─ _deduplicate(findings)
  │         │    ├─ HumanReadableReportComposer.compose() → markdown
  │         │    └─ write .md file
  │         ├─ _complete_review()     → status=completed
  │         └─ _cleanup_workspace()   → always runs
  │
  ├─ GET /api/reviews/{task_id}  [polls every 2s]
  │    ├─ store.get_review() → status, report_markdown
  │    └─ runner.get_progress() → in-memory snapshot [v3_multi_agent only]
  │
  ├─ GET /api/reviews/{task_id}/export → .md download
  │
  └─ GET /api/reviews → list (limit=50)
```

### Data Flow: Report Generation to Display

```
Backend                          Wire                         Frontend
─────────                        ────                         ────────
AgentOrchestrator                                                     |
  → StructuredReviewDraft                                             |
    → ReviewFinding[]                                                 |
      → HumanReadableReportComposer.compose()                         |
        → markdown string ────── HTTP JSON ──────→ report_markdown    |
                                                      │               |
                                                      ▼               |
                                              parseReport(markdown)   |
                                              parseAgentReportDetails |
                                                (re-parses tables)    |
                                                      │               |
                                                      ▼               |
                                              React components render |
```

**The critical problem:** The backend generates structured data (findings, agent states, evidence), serializes it to markdown, sends the markdown to the frontend, and the frontend re-parses the markdown back into structured data. This round-trip through markdown is the root cause of most frontend fragility.

---

## 4. Feature Reality Matrix

| Feature | User-Visible? | Works? | UX Quality | Coupling Risk | Duplicate/Overlap? | Verdict |
|---------|:---:|:---:|:---:|:---:|:---:|---------|
| **Repo import** | ✅ | ✅ | Good | Low | No | **Real and visible.** URL validation clear, errors shown. |
| **Mock/MiMo selector** | ✅ | ✅ | Adequate | Low | No | **Real and visible.** Missing key error is clear. Backend-only key. |
| **Review status** | ✅ | ✅ | Adequate | Medium | No | **Real.** Status labels clear. No cancel button. |
| **Runtime Agent Progress** | ✅ | ✅ | Weak | High | Yes (vs Agent Contributions) | **Technically implemented but weak UX.** Progress rail does not handle "failed". Only works for v3_multi_agent. Visually subtle. |
| **Agent Contribution cards** | ✅ | ✅ | Adequate | High | Yes (vs Runtime Progress) | **Technically implemented but fragile.** Parses markdown tables on every render. No useMemo. Duplicates concept of runtime progress. |
| **Agent Findings** | ✅ | ✅ | Adequate | High | Partial | **Real but parser-dependent.** Grouped by agent, shows severity/confidence/files/evidence. Breaks if markdown format changes. |
| **Report renderer** | ✅ | ✅ | Weak | High | Yes (section lists in 3 places) | **Technically implemented but weak.** Missing sections render "No findings returned." No table of contents. No section navigation. |
| **Evidence display** | ✅ | ⚠️ | Weak | Low | No | **Technically implemented but hidden.** Evidence IDs shown as badges but not clickable. No way to view actual code snippets. |
| **Appendix / metrics** | ✅ | ⚠️ | Weak | Medium | Yes (V3 missing sections) | **Partially broken.** V3 reports don't produce Repository Insights/Metrics/Architecture Graph sections that the frontend expects. Shows fallback text. |
| **Review history** | ✅ | ✅ | Weak | Low | No | **Real but minimal.** No timestamps, no pagination (cap 50), no delete. |
| **Export Markdown** | ✅ | ✅ | Adequate | Low | No | **Real and useful.** Downloads the raw markdown report. |
| **Evaluation platform** | ❌ | ✅ | N/A | Low | No | **Internal only.** Not user-visible. Covers V3.4 quality but not V3.5.1/V3.5.2/V3.5.3. |
| **CLI/CI/MCP** | Partial | ✅ | Adequate | Low | Partial (runner vs workflow) | **Real but separate path.** CLI bypasses the task runner. Two parallel task creation paths. |

### Summary Count

- **Real and visible:** 4 (Repo import, Mock/MiMo, Review status, Export)
- **Technically implemented but weak UX:** 4 (Runtime Progress, Agent Contributions, Report renderer, Evidence display)
- **Partially broken:** 1 (Appendix/metrics — V3 missing sections)
- **Hidden / internal:** 1 (Evaluation platform)
- **Fragile / parser-dependent:** 3 (Agent Findings, Agent Contributions, Report renderer)

---

## 5. Critical / High / Medium / Low Issues

### Critical Issues

| ID | Area | Evidence | Problem | User Impact | Future Impact | Fix in V3.5.4? |
|----|------|----------|---------|-------------|---------------|:---:|
| C-01 | Frontend/Backend Contract | `frontend/lib/report.ts` + `backend/reviewers/report_composer.py` | **Frontend re-parses backend-generated markdown.** Section names, table formats, heading levels are all implicit contracts. Any backend change silently breaks the frontend. | Agent contribution cards and report sections can go blank with no error. | Blocks all future report format changes. Blocks V3.6 report improvements. | **Yes — primary target** |
| C-02 | Backend Models | `backend/models/context.py` lines 246-310 | **Dual context model (ReviewContext + RepositoryContext)** with manual 30-line conversion methods. Three representations of repo metadata. Adding any field requires changes in 4+ places. | None directly (internal). | Any new feature touching context models risks silent data loss. | No (V3.6) |

### High Issues

| ID | Area | Evidence | Problem | User Impact | Future Impact | Fix in V3.5.4? |
|----|------|----------|---------|-------------|---------------|:---:|
| H-01 | Frontend | `ReviewStatusDisplay.tsx` line 116 | **ProgressRail does not handle "failed" status.** `activeIndex` is -1 for failed reviews. No segment lights up. | Failed reviews show a completely dark progress bar with no indication of failure point. | Confusing for users debugging failed reviews. | **Yes** |
| H-02 | Backend Tasks | `backend/tasks/runner.py` | **Progress memory never cleaned up.** `_progress` dict grows unboundedly. No eviction, TTL, or max-size. | None for short sessions. Memory leak for long-running servers. | Production deployment instability over time. | **Yes** |
| H-03 | Backend Tasks | `backend/tasks/runner.py` + `backend/storage/sqlite.py` | **No stale task recovery.** Crashed processes leave tasks stuck in intermediate statuses. No startup sweep. | Reviews stuck as "parsing" forever after server restart. | Users see infinite polling with no resolution. | **Yes** |
| H-04 | Frontend | `frontend/lib/report.ts` + `backend/reviewers/markdown_adapter.py` | **Section name lists defined in 3 places.** `contracts/report_sections.json`, `markdown_adapter.py` APPENDIX_SECTIONS, and `frontend/lib/report.ts` hardcoded arrays. | None until names change. | Adding a new section requires coordinated changes in 3 files. | **Yes (consolidate)** |
| H-05 | Frontend | `ReportRenderer.tsx` lines 39-48 | **V3 reports missing Repository Insights/Metrics/Architecture Graph sections.** Frontend renders "No findings returned." for these. | Users see misleading empty cards implying the agent found nothing. | Looks broken even when the review succeeded. | **Yes (remove or fix)** |
| H-06 | Backend API | `backend/api/reviews.py` line 19 | **POST /api/reviews returns 200 instead of 202.** Async operation returns synchronous success code. | API consumers cannot distinguish accepted from completed. | Breaks REST conventions. | Yes |
| H-07 | Backend API | `backend/api/errors.py` lines 41-48 | **Catch-all Exception handler does not log.** Unhandled 500s are invisible in server logs. | Operators cannot diagnose production failures. | Silent failures in production. | Yes |
| H-08 | Backend Tasks | `backend/tasks/pipeline.py` + `backend/tasks/runner.py` | **Progress/status dual-source inconsistency.** Status from SQLite, progress from memory. Can disagree after restart. | Frontend polls forever if server restarts mid-task. | Data integrity issue. | Partial |
| H-09 | Backend API | `backend/api/reviews.py` | **Missing API endpoints.** No DELETE, no structured findings endpoint, no agent states endpoint. Data stored but not served. | Users cannot clean up reviews. Frontend cannot get structured data without parsing markdown. | Forces frontend markdown parsing (C-01). | **Yes (add structured endpoint)** |

### Medium Issues

| ID | Area | Evidence | Problem | User Impact | Future Impact | Fix in V3.5.4? |
|----|------|----------|---------|-------------|---------------|:---:|
| M-01 | Frontend | `AgentContributions.tsx` line 31 | **`parseAgentReportDetails` called on every render.** No useMemo. Parses entire markdown each time. | Slow re-renders for large reports. | Performance degrades with report size. | Yes |
| M-02 | Frontend | `ReportRenderer.tsx` line 21 | **`parseReport` called twice per render.** Once in ReportRenderer, once inside AgentContributions via parseAgentReportDetails. | Wasted CPU. | Performance issue at scale. | Yes |
| M-03 | Frontend | `AgentContributions.tsx` line 177 | **O(n²) array spread in `groupFindings`.** `[...(existing), new]` on every iteration. | Slow for reports with many findings. | Performance degrades. | Yes |
| M-04 | Backend Agents | `backend/agents/evidence_agent.py` line 62 | **Redundant EvidenceRetriever instantiation.** `_render_prompt` creates a new retriever that precomputes BM25 stats already computed in `review()`. | None (internal). | Wasted CPU per agent invocation. | No |
| M-05 | Backend Agents | `backend/agents/orchestrator.py` | **Sequential agent execution.** Four LLM calls run serially. | Reviews take 4x longer than necessary. | Blocks V3.6 performance goals. | No (V3.6) |
| M-06 | Backend Agents | `backend/agents/orchestrator.py` | **No per-agent timeout.** Hung LLM call blocks entire review indefinitely. | Review hangs forever if LLM provider is down. | Production reliability risk. | Yes |
| M-07 | Frontend | `useReviewPolling.ts` | **No polling backoff.** 2-second interval for entire lifecycle including 5+ minute reviews. | ~150 unnecessary requests per long review. | Server load scales linearly with active reviews. | Yes |
| M-08 | Frontend | `frontend/lib/api.ts` | **No request timeout.** All fetch calls have no AbortController. | UI spins indefinitely if backend hangs. | User cannot recover without page refresh. | Yes |
| M-09 | Backend API | `backend/api/reviews.py` lines 38-39 | **Fragile getattr duck-typing for progress.** `getattr(runner, "get_progress", None)` on a known class. | None (internal). | Unnecessary complexity. | Yes |
| M-10 | Backend Models | `backend/models/review.py` lines 8-18 | **Massive import side-effect.** `review.py` imports all context models and re-exports them. None used within the file. | None (internal). | Slow imports, unnecessary coupling. | Yes |
| M-11 | Backend Models | `backend/models/structured_review.py` line 6 | **`RawLLMFinding` defined but never imported.** Dead code. | None. | Confusion for developers. | Yes |
| M-12 | Backend | `backend/reviewers/report_composer.py` line 462 | **`_table_cell` only escapes pipes.** Other markdown syntax (`*`, `_`, `[`, `]`) in LLM titles can break tables or create links. | Broken table formatting or unexpected links in report. | Security: LLM-generated `[link](url)` renders as clickable. | Yes |
| M-13 | Evaluation | `evaluation/run_eval.py` line 92 | **`classify_failure_stage()` defined but never called.** Dead code. | None. | Confusion. | Yes |
| M-14 | Evaluation | `evaluation/metrics.py` | **Unused metric classes.** `HallucinationMetrics`, `FindingQualityMetrics`, `AgentEvaluationMetrics`, `RetrievalEvaluationMetrics` defined but never used by the pipeline. | None. | Dead code weight. | No |
| M-15 | Evaluation | `evaluation/run_eval.py` lines 86, 237 | **Fragile import of REPORT_SECTIONS from `backend.llm.client`** instead of canonical `backend.core.report_contract`. | None until re-export changes. | Silent divergence if import path changes. | Yes |
| M-16 | Deployment | `.env.example` line 19 | **`FINAL_PROMPT_TOKEN_BUDGET=5000` but code default is 8000.** All docs say 5000. | If .env.example copied verbatim, budget is 5000 instead of 8000. | Behavioral drift between documented and actual. | Yes |
| M-17 | Deployment | `.harness/RELEASE_RULES.md` line 29 | **Stale version: "V3.1" but project is V3.5.3.** | None (internal). | Governance docs are wrong. | Yes |
| M-18 | Deployment | `.harness/GOAL.md` line 35 | **Stale test count: "255" but actual is 327.** | None (internal). | Governance docs are wrong. | Yes |
| M-19 | Deployment | `.harness/HARNESS_AUDIT_RULES.md` lines 107-118 | **Stale baseline: "44/46 tests" but actual is 327.** | None (internal). | Audit rules produce false results. | Yes |
| M-20 | Deployment | `docs/VERCEL_DEPLOYMENT.md` | **Hardcoded Render URL.** `https://codepilot-i189.onrender.com` appears in multiple places. | Stale if Render service changes. | Docs become wrong. | Yes |
| M-21 | Frontend | `ReviewHistory.tsx` | **No timestamp in history items.** Only repo name and status shown. | Cannot distinguish multiple reviews of same repo. | Poor UX for repeat users. | Yes |
| M-22 | Frontend | `page.tsx` line 18 | **Hardcoded default repo URL.** `https://github.com/pallets/flask` pre-filled. | Confusing for production users. | Looks like a demo, not a product. | Yes |
| M-23 | Backend Models | `backend/models/report_result.py` | **Mixed model paradigm.** `ReportResult` is a dataclass while everything else is Pydantic BaseModel. | None (internal). | Inconsistent serialization. | No |
| M-24 | Backend | `backend/main.py` lines 47-50 | **Side effects at import time.** Module-level code creates DB, directories, ThreadPoolExecutor on import. | None in production. Breaks test isolation. | Testability concern. | No |
| M-25 | Frontend | `globals.css` | **No dark mode.** `tailwind.config.ts` has `darkMode: ["class"]` but no `.dark` selector defined. | No dark mode available. | Feature configured but never implemented. | No (V3.6) |
| M-26 | Frontend | `ReviewHistory.tsx` | **No pagination.** Hard cap at 50 reviews with no indication. | Reviews beyond 50 silently dropped. | History becomes useless for power users. | Yes |
| M-27 | Backend | `backend/core/config.py` line 16-23 | **CORS allow_methods=["*"] and allow_headers=["*"].** Extremely permissive. | None in dev. Security risk in production. | Attack surface. | Yes |
| M-28 | Backend Agents | `backend/agents/orchestrator.py` line 132 | **Agent failure exceptions reduced to `str(exc)`.** Tracebacks lost. | None to users. Hard to debug production failures. | Operational blindness. | Yes |
| M-29 | Evaluation | `evaluation/configs/default.json` | **`max_runtime_seconds` thresholds defined but never enforced.** Code measures runtime but never checks against thresholds. | None. | Dead configuration. | No |
| M-30 | Evaluation | `evaluation/datasets/` | **Network-dependent datasets have no pinned commits.** Public repos referenced by branch HEAD. | None until repo changes. | Evaluation results silently change. | No |

### Low Issues

| ID | Area | Evidence | Problem | Fix in V3.5.4? |
|----|------|----------|---------|:---:|
| L-01 | Backend API | `errors.py` line 28 | Only first validation error reported to user | Yes |
| L-02 | Backend API | `errors.py` lines 34-35 | StarletteHTTPException duplicates error/detail | Yes |
| L-03 | Backend API | `reviews.py` line 60 | Export endpoint streams large reports with no size limit | No |
| L-04 | Backend Models | `review.py` line 33 | `llm_mode` uses regex instead of Literal type | Yes |
| L-05 | Backend Models | `review.py` lines 41-47 | Smoke test bypass URL format is confusing | No |
| L-06 | Backend Models | `review_scope.py` line 34 | `candidate_paths()` returns `None` vs empty set distinction | No |
| L-07 | Backend Agents | `finding_validator.py` | All-or-nothing evidence resolution (1 invalid ID kills entire finding) | No |
| L-08 | Backend Agents | `finding_validator.py` | No severity/confidence normalization | No |
| L-09 | Backend Agents | `evidence_agent.py` | Prompt not clipped to token budget | No |
| L-10 | Backend | `report_generator.py` line 132-133 | V3 multi-agent failure is silent in report text | Yes |
| L-11 | Backend | `report_composer.py` line 405 | Evidence Appendix hard-capped at 30 with no overflow indicator | Yes |
| L-12 | Backend | `report_composer.py` | `DEFAULT_SECTION_CONTENT` same for all sections — misleading for Refactoring | Yes |
| L-13 | Backend | `report_composer.py` line 73 | LLM severity values not validated against expected set | No |
| L-14 | Frontend | `ReviewSubmissionForm.tsx` | No `aria-describedby` on LLM mode select | Yes |
| L-15 | Frontend | `MarkdownContent.tsx` | No component-level error boundary | Yes |
| L-16 | Frontend | `report.ts` line 287 | `parseCommaList` silently truncates to 6 items | No |
| L-17 | Frontend | `report.ts` | `parseReport` ignores unrecognized headings (absorbs into previous section) | No |
| L-18 | Frontend | `ReviewStatusDisplay.tsx` | Export link has no error handling for 404 | Yes |
| L-19 | Backend | `runner.py` line 48 | `_shutdown` flag not synchronized (safe under CPython GIL but not spec-guaranteed) | No |
| L-20 | Backend | `pipeline.py` lines 212-220 | Duck-typed pipeline-generator interface (getattr/callable) | No |
| L-21 | Backend | `runner.py` | `self.pipeline` is a dead object — only carries factory defaults | No |
| L-22 | Backend | `context.py` line 308 | `as_review_context()` runtime type-dispatch exists because callers can't decide which type to use | No |
| L-23 | Evaluation | `registry.py` + `metrics.py` | `REPORT_MARKDOWN_MAX_CHARS = 5000` duplicated | No |
| L-24 | Evaluation | `report_quality.py` | V3.4 quality gate still labeled "V3.4" but used by V3.5 tests | No |
| L-25 | Deployment | `DEPLOYMENT.md` | Env var table missing `ENABLE_REAL_LLM`, `REVIEW_ENGINE`, MiMo vars | Yes |
| L-26 | Deployment | `README.md` lines 72, 74 | References `docs/V3_3_WORKFLOWS.md` and `docs/V3_4_REPORT_QUALITY.md` which don't exist | Yes |
| L-27 | Deployment | `docs/harness_design_v1.md` | 1592-line monolith frozen at V1.1, severely outdated | Yes (delete or archive) |
| L-28 | Deployment | No `render.yaml` or `vercel.json` | Infrastructure not version-controlled | No |
| L-29 | Deployment | No CHANGELOG | No formal change tracking | No |
| L-30 | Security | `sandbox.py` | No JWT, AWS key, or database connection string redaction patterns | No |
| L-31 | Security | `core/logging.py` | Logging has no secret filtering | No |
| L-32 | Frontend | `globals.css` | No print styles for export | No |
| L-33 | Frontend | `page.tsx` | No cancel/abort for running reviews | No |
| L-34 | Frontend | `AgentContributions.tsx` | Evidence IDs not clickable/linked to appendix | No |
| L-35 | Frontend | `ReportRenderer.tsx` | No table of contents / section navigation | No (V3.6) |
| L-36 | Backend | `runner.py` | Hardcoded `PLANNED_AGENTS` must stay in sync with orchestrator's `agent_classes` | No |
| L-37 | Frontend | `report.ts` | `terminalStatuses` must stay in sync with backend `ReviewStatus` enum | No |

---

## 6. Coupling and Duplication Findings

### Duplicated Logic

| What | Where | Risk |
|------|-------|------|
| **Section name lists** | `contracts/report_sections.json`, `markdown_adapter.py` APPENDIX_SECTIONS, `frontend/lib/report.ts` hardcoded arrays | **High.** Three independent definitions of the same concept. |
| **Markdown section parsing** | `markdown_adapter.py:extract_sections()`, `frontend/lib/report.ts:parseReport()` | **High.** Same algorithm implemented independently in Python and TypeScript. |
| **Agent summary/findings parsing** | `report_composer.py` generates tables, `frontend/lib/report.ts` re-parses them | **High.** The frontend re-implements table parsing to extract data the backend already had as structured objects. |
| **Repo metadata fields** | `RepoMetadata`, `ReviewContextSummary`, `RepositoryContext` | **Medium.** Three representations of the same fields with manual copying. |
| **Context model** | `ReviewContext` (V3), `RepositoryContext` (V2.5) | **Medium.** Two parallel models with 30-line conversion methods. |
| **`total_python_files` / `total_source_files`** | `RepositoryContext`, `ReviewContext`, `ReviewPipelineResult` | **Low.** Deprecated name still present in 3 places. |
| **`REPORT_MARKDOWN_MAX_CHARS`** | `evaluation/registry.py`, `evaluation/metrics.py` | **Low.** Same constant defined independently. |
| **`InsightReport` / `RepositoryInsights`** | `backend/models/context.py` lines 87-88 | **Low.** Same class, two names. |

### Fragile Markdown Parsing

The frontend's `report.ts` (294 lines) is the most fragile file in the codebase:

1. **`parseReport`** matches headings by exact string. Unknown headings are absorbed into the previous section.
2. **`parseAgentSummary`** parses a markdown table by column name. If the backend renames a column, parsing silently returns empty arrays.
3. **`parseAgentFindings`** uses a regex (`/^[A-Za-z][A-Za-z0-9]*Agent$/`) to detect agent names in headings. If the backend changes agent naming, parsing breaks.
4. **`readMarkdownTable`** splits on `|` pipes. If a cell contains an escaped pipe, the `splitMarkdownRow` helper handles it, but other edge cases (multi-line cells, nested tables) would break.
5. **`parseCommaList`** silently truncates to 6 items.
6. **`parseEvidenceIds`** filters to alphanumeric pattern. Evidence IDs with hyphens would be dropped.

**All of this parsing would be unnecessary if the backend exposed structured data via the API.**

### Runtime vs Final Agent Visualization Overlap

- **Runtime progress** (`ReviewStatusDisplay.tsx`): Shows agent status during execution via polling. Uses `AgentProgressItem` from the API response.
- **Agent contributions** (`AgentContributions.tsx`): Shows agent results after completion. Parses markdown tables from the report.

These are two different data models for the same concept (agent execution results). They should share a frontend data model. The runtime data comes from the API as structured JSON. The final data comes from the report as markdown that must be re-parsed. If the backend exposed agent states via an API endpoint, both could use the same structured data.

### Backend/Frontend Contract Problems

| Contract | Backend Source | Frontend Consumer | Problem |
|----------|---------------|-------------------|---------|
| Review status enum | `ReviewStatus` (Python StrEnum) | `terminalStatuses` (TypeScript array) | Must stay in sync manually |
| Agent names | `PLANNED_AGENTS` (runner.py) + `agent_classes` (orchestrator.py) | `agentRank` (report.ts) | Three independent lists |
| Report sections | `REPORT_SECTIONS` (contract JSON) | `orderedSections` + hardcoded arrays (report.ts) | Partial import, partial hardcode |
| Progress snapshot | `ReviewProgressSnapshot` (Pydantic) | `ReviewProgressSnapshot` (TypeScript) | Types are manually mirrored |

### Stale Compatibility Code

| Code | Purpose | Status |
|------|---------|--------|
| `RepositoryContext` (V2.5 flat model) | Backward compatibility | Still used by V2 pipeline. Can be removed when V2 is removed. |
| `RepositoryInsights` class alias | V2.5 import paths | Pure alias. Can be replaced with `RepositoryInsights = InsightReport`. |
| `total_python_files` property | Deprecated name | Still present. Should be removed. |
| `ReviewPipelineResult.total_python_files` | Deprecated field | Has `total_source_files` alias. Old name should be removed. |
| `as_review_context()` | Runtime type dispatch | Exists because callers use both context types. Remove when V2.5 context is removed. |

### Dead Code

| Code | Location | Status |
|------|----------|--------|
| `RawLLMFinding` class | `structured_review.py` line 6 | Never imported anywhere |
| `classify_failure_stage()` | `run_eval.py` line 92 | Never called |
| `HallucinationMetrics`, `FindingQualityMetrics`, etc. | `metrics.py` | Defined with serializers but never used by pipeline |
| `_run_legacy()` | `run_eval.py` line 940 | Backward compat, no structured artifacts |
| `docs/harness_design_v1.md` | `docs/` | 1592 lines frozen at V1.1 |

---

## 7. Frontend Refactor Readiness

### What Can Be Safely Preserved

| Component | Reason |
|-----------|--------|
| `ui/button.tsx`, `ui/input.tsx`, `ui/card.tsx` | Clean, well-structured primitives. No changes needed. |
| `lib/api.ts` | Clean API client. Needs timeout/retry additions but structure is fine. |
| `lib/types.ts` | Clean TypeScript types mirroring backend models. |
| `lib/validation.ts` | Clean URL validation. |
| `lib/utils.ts` | Single utility function. |
| `hooks/useReviewPolling.ts` | Correct polling logic. Needs backoff addition but structure is fine. |
| `app/error.tsx`, `app/loading.tsx`, `app/layout.tsx` | Clean Next.js boilerplate. |
| `ReviewSubmissionForm.tsx` | Clean presentational component. Minor accessibility fixes only. |

### What Should Be Redesigned

| Component | Current Problem | Recommended Change |
|-----------|----------------|-------------------|
| **`report.ts` (294 lines)** | Re-parses markdown into structured data. 7 parsing functions. Fragile. | **Replace with structured API endpoint.** Backend exposes findings/agent states as JSON. Frontend consumes JSON directly. |
| **`ReportRenderer.tsx`** | Parses markdown on every render. Renders sections in hardcoded order. Missing sections show misleading fallback. | **Consume structured API data.** Render from JSON, not markdown. Add section navigation. |
| **`AgentContributions.tsx`** | Parses markdown tables on every render. No useMemo. O(n²) grouping. | **Consume structured API data.** Remove markdown parsing entirely. |
| **`ReviewStatusDisplay.tsx`** | ProgressRail doesn't handle "failed". No cancel button. | **Fix ProgressRail. Add cancel button. Unify runtime/final agent data model.** |
| **`ReviewHistory.tsx`** | No timestamps. No pagination. No delete. | **Add timestamps, pagination, delete action.** |

### What Should Be Consolidated

| Current State | Target State |
|---------------|-------------|
| Two agent data models (runtime `AgentProgressItem` + parsed `AgentContribution`) | One unified agent data model fed by structured API |
| `parseReport` called twice per render (ReportRenderer + AgentContributions) | Parse once in parent, pass down. Or better: don't parse at all — use API data. |
| Section names in 3 places | Single source of truth (import from contract JSON or API) |

### What Should Not Be Touched

| Area | Reason |
|------|--------|
| Backend agent system | Works well. Clean architecture. Not in scope for frontend refactor. |
| Backend evidence system | Strong design. Not in scope. |
| Evaluation platform | Internal tool. Not in scope. |
| Backend models (context.py etc.) | Debt exists but is not blocking frontend refactor. V3.6 work. |

### API Contracts That Must Be Preserved

| Endpoint | Contract | Notes |
|----------|----------|-------|
| `POST /api/reviews` | `{repo_url: string, llm_mode: "mock"\|"mimo"}` → `{task_id: string, llm_mode: string}` | Do not change. |
| `GET /api/reviews/{task_id}` | `ReviewStatusResponse` with optional `progress` | Do not change. Add new fields only. |
| `GET /api/reviews` | List with `limit` param | Do not change. Add cursor pagination later. |
| `GET /api/reviews/{task_id}/export` | Raw markdown download | Do not change. |

### New API Endpoints Needed for V3.5.4

| Endpoint | Purpose | Replaces |
|----------|---------|----------|
| `GET /api/reviews/{task_id}/findings` | Structured findings as JSON | Frontend markdown parsing of findings tables |
| `GET /api/reviews/{task_id}/agent-states` | Agent execution states as JSON | Frontend markdown parsing of agent summary table |
| `DELETE /api/reviews/{task_id}` | Delete a review | Nothing (new) |

### Risks V3.5.4 Must Avoid

1. **Do not break the existing markdown export.** The `GET /api/reviews/{task_id}/export` endpoint must continue to work. Users depend on it.
2. **Do not change the polling contract.** The `GET /api/reviews/{task_id}` response shape must remain backward-compatible.
3. **Do not remove the markdown report from the response.** The `report_markdown` field on `ReviewStatusResponse` must remain for backward compatibility. The new structured endpoints are additions, not replacements.
4. **Do not redesign the backend agent system.** It works well. Frontend refactor only.
5. **Do not add new dependencies unless absolutely necessary.** The current stack is sufficient.

---

## 8. Backend Refactor / Stabilization Needs

### Must Fix Before Frontend Refactor

| Issue | Why |
|-------|-----|
| Add `GET /api/reviews/{task_id}/findings` endpoint | Frontend needs structured data to stop parsing markdown |
| Add `GET /api/reviews/{task_id}/agent-states` endpoint | Same reason |
| Fix `_table_cell` to escape all markdown special chars | Prevents broken tables in both markdown export and frontend rendering |

### Should Fix Alongside Frontend Refactor

| Issue | Why |
|-------|-----|
| Add progress memory cleanup (evict completed/failed after N minutes) | Prevents memory leak |
| Add stale task recovery on startup | Prevents stuck reviews after restart |
| Change POST /api/reviews to return 202 | Correct HTTP semantics |
| Add logging to catch-all Exception handler | Operational necessity |
| Fix catch-all to log exceptions | Debugging production failures |

### Can Wait Until V3.6

| Issue | Why |
|-------|-----|
| Dual context model (ReviewContext/RepositoryContext) | Large refactor, not blocking frontend |
| Sequential agent execution → parallel | Performance improvement, not blocking |
| Redundant EvidenceRetriever instantiation | Performance optimization, not blocking |
| Remove V2 backward compatibility code | Only when V2 engine is removed |
| Add authentication/rate limiting | Important but not blocking refactor |
| Dark mode | UX polish, not blocking |
| Per-agent timeout | Reliability improvement, not blocking |

### Schema Concern

The SQLite schema (`backend/storage/sqlite.py`) is well-structured with separate tables for reviews, findings, evidence refs, agent states, and graph states. The `schema_metadata` table tracks version. No immediate concerns, but:

- The `review_agent_states` table stores agent metadata as JSON blob. Adding the new `/agent-states` endpoint just requires reading this column.
- The `review_findings` table stores structured findings. Adding the new `/findings` endpoint just requires reading this table.
- No schema migration needed for V3.5.4.

### Agent/Pipeline Coupling Concern

The pipeline uses duck-typing (`getattr`/`callable`) to configure the ReportGenerator:

```python
if callable(getattr(report_generator, "configure_engine", None)):
    report_generator.configure_engine(self.review_engine)
```

This is fragile but functional. For V3.5.4, no change needed. For V3.6, consider defining a formal protocol or base class.

---

## 9. Test Gap Analysis

### Backend Tests — Missing

| Area | Missing Test | Priority |
|------|-------------|:---:|
| Concurrency | Thread safety of `_progress` dict under contention | Medium |
| Concurrency | Concurrent write access to SQLite store | Medium |
| API | POST returns 202 (after fix) | High |
| API | New `/findings` and `/agent-states` endpoints | High |
| API | DELETE endpoint | Medium |
| API | `RequestValidationError` with multiple errors | Low |
| Pipeline | Unhandled RuntimeError from report generator | Medium |
| Pipeline | Stale task recovery on startup | High |
| Pipeline | Progress memory cleanup | High |
| Agent | All agents failing simultaneously | Medium |
| Agent | Agents producing conflicting findings | Medium |
| Agent | Per-agent timeout | Medium |
| LLM | Timeout behavior (httpx.TimeoutException) | Medium |
| LLM | Malformed JSON response from provider | Medium |
| Security | JWT token redaction | Low |
| Security | Database connection string redaction | Low |
| Security | Review status `error` field secret leakage | Medium |

### Frontend Tests — Missing

| Area | Missing Test | Priority |
|------|-------------|:---:|
| Integration | Full flow: submit → poll → display | High |
| Integration | New structured API consumption | High |
| Component | ProgressRail with "failed" status | High |
| Component | MarkdownContent error boundary | Medium |
| Component | Large report rendering performance | Low |
| Component | Evidence ID clickability (after V3.5.4) | Medium |

### Evaluation Tests — Missing

| Area | Missing Test | Priority |
|------|-------------|:---:|
| Coverage | MiMo provider integration | Medium |
| Coverage | JavaScript fixture evaluation | Medium |
| Coverage | V3.5.3 runtime progress | Low |
| Coverage | Multi-language fixture | Medium |
| Coverage | Error case evaluation (repos that should fail) | Medium |

### Deployment Tests — Missing

| Area | Missing Test | Priority |
|------|-------------|:---:|
| CI | Docker build in CI pipeline | Medium |
| CI | Frontend build with NEXT_PUBLIC_API_BASE | Low |
| Smoke | Production CORS configuration | Low |

---

## 10. V3.5.4 Recommendation

### Must Do

| # | Task | Area | Effort |
|---|------|------|:---:|
| 1 | **Add `GET /api/reviews/{task_id}/findings` endpoint** exposing structured findings as JSON | Backend API | Small |
| 2 | **Add `GET /api/reviews/{task_id}/agent-states` endpoint** exposing agent execution states as JSON | Backend API | Small |
| 3 | **Frontend: replace markdown parsing with structured API consumption** in ReportRenderer and AgentContributions | Frontend | Medium |
| 4 | **Frontend: unify agent data model** — runtime progress and final contributions share one TypeScript type | Frontend | Small |
| 5 | **Fix ProgressRail to handle "failed" status** | Frontend | Trivial |
| 6 | **Fix `_table_cell` to escape all markdown special chars** (`*`, `_`, `[`, `]`, `(`, `)`, `` ` ``) | Backend | Trivial |
| 7 | **Add progress memory cleanup** — evict completed/failed snapshots after 10 minutes | Backend | Small |
| 8 | **Add stale task recovery** — on startup, mark intermediate-status tasks as failed | Backend | Small |
| 9 | **Add `DELETE /api/reviews/{task_id}` endpoint** | Backend API | Small |
| 10 | **Remove V3 missing sections from frontend** (Repository Insights, Metrics, Architecture Graph) or add them to V3 reports | Frontend | Small |

### Should Do

| # | Task | Area | Effort |
|---|------|------|:---:|
| 11 | Change POST /api/reviews to return 202 | Backend | Trivial |
| 12 | Add logging to catch-all Exception handler | Backend | Trivial |
| 13 | Add useMemo to parseReport/parseAgentReportDetails calls | Frontend | Trivial |
| 14 | Add timestamps to review history items | Frontend | Small |
| 15 | Add pagination to review history (cursor-based) | Frontend+Backend | Small |
| 16 | Add request timeout to API fetch calls (AbortController) | Frontend | Small |
| 17 | Add polling backoff (increase interval after 30s) | Frontend | Small |
| 18 | Add per-agent timeout (30s per LLM call) | Backend | Small |
| 19 | Fix hardcoded default repo URL (empty or from env) | Frontend | Trivial |
| 20 | Consolidate section name lists (single source of truth) | Frontend+Backend | Small |
| 21 | Fix harness docs (test counts, version numbers, token budget) | Docs | Small |
| 22 | Fix missing docs references in README | Docs | Trivial |
| 23 | Delete or archive `docs/harness_design_v1.md` | Docs | Trivial |
| 24 | Add new tests for new endpoints and frontend structured consumption | Tests | Medium |

### Nice to Have

| # | Task | Area | Effort |
|---|------|------|:---:|
| 25 | Add CORS method/header narrowing | Backend | Trivial |
| 26 | Fix `llm_mode` regex to Literal type | Backend | Trivial |
| 27 | Remove dead code (`RawLLMFinding`, `classify_failure_stage`, unused metric classes) | Backend+Eval | Small |
| 28 | Add accessibility improvements (aria-describedby, download indication) | Frontend | Small |
| 29 | Add delete action to review history | Frontend | Small |
| 30 | Fix `orderedSections` to skip absent sections instead of showing "No findings returned." | Frontend | Trivial |
| 31 | Add component-level error boundary for MarkdownContent | Frontend | Small |
| 32 | Fix `.env.example` FINAL_PROMPT_TOKEN_BUDGET to match code (8000) | Config | Trivial |
| 33 | Fix DEPLOYMENT.md env var table | Docs | Trivial |
| 34 | Add `DEPLOYMENT.md` health check documentation | Docs | Trivial |

### Do Not Do

| Task | Why Not |
|------|---------|
| Refactor dual context model (ReviewContext/RepositoryContext) | Large effort, not blocking frontend. V3.6 work. |
| Add parallel agent execution | Performance optimization, not blocking. V3.6 work. |
| Add authentication/rate limiting | Important but separate concern. V3.6 work. |
| Add dark mode | UX polish. V3.6 work. |
| Add SSE/WebSocket for progress | Polling works. V3.6 optimization. |
| Refactor V2 pipeline | Only needed when V2 engine is removed. V3.6+ work. |
| Add new evaluation datasets | Evaluation coverage gap but not blocking frontend refactor. |
| Add render.yaml / vercel.json | Deployment improvement but not blocking. |
| Add CHANGELOG | Good practice but not blocking. |

---

## 11. V3.6 Readiness

### Is V3.6 Safe to Plan Now?

**Yes, with caveats.** V3.5.4 must complete the frontend refactor first. Once the frontend consumes structured API data instead of parsing markdown, V3.6 can safely change report formats, add new sections, and modify agent outputs without breaking the frontend.

### What Must Be Cleaned First (V3.5.4)

1. Frontend must stop parsing markdown for structured data.
2. Progress memory leak must be fixed.
3. Stale task recovery must be implemented.
4. `_table_cell` must escape all markdown chars (prevents future report format issues).

### What V3.6 Should Not Touch Yet

| Area | Why |
|------|-----|
| Dual context model | Still too risky without careful planning. Needs its own release. |
| V2 engine removal | Requires migration path for any V2 users. |
| Authentication/rate limiting | Requires design decisions (JWT? API keys? OAuth?). |
| New language parsers | Parser system works but adding languages needs evaluation coverage first. |

### Recommended V3.6 Scope

Based on the ROADMAP and audit findings:

1. **Parallel agent execution** — reduce review wall-clock time by 3-4x.
2. **Per-agent timeout** — prevent hung reviews.
3. **Evaluation coverage for MiMo mode and multi-language** — close evaluation gaps.
4. **Structured findings/agent-states API** (completed in V3.5.4) enables: report customization, filtering, sorting in frontend.
5. **Dark mode** — now easy since frontend is refactored.
6. **Section navigation / table of contents** — now easy since frontend uses structured data.
7. **Evidence snippet expandability** — show code snippets on demand (safety-gated).

---

## 12. Final Recommendation

**Start V3.5.4 frontend refactor.**

The project is at 6.5/10 health. The backend is solid enough (7/10) to support a frontend refactor without backend changes breaking things. The frontend (5.5/10) is the weakest layer and the primary blocker for future work.

The core problem is clear: the frontend parses markdown that the backend generates. This creates a fragile, duplicated, implicit contract. The fix is straightforward: add two small API endpoints (`/findings`, `/agent-states`), rewrite the frontend to consume JSON instead of markdown, and fix the known bugs (ProgressRail, memory leak, stale tasks).

The scope is bounded. The backend changes are ~200 lines of new code (two endpoints). The frontend changes are concentrated in 4 files (`report.ts`, `ReportRenderer.tsx`, `AgentContributions.tsx`, `ReviewStatusDisplay.tsx`). The risk is low because the existing markdown export and polling contract are preserved.

After V3.5.4, the project will be at ~7.5/10 health with a clean frontend-backend contract, and V3.6 can safely add features without worrying about breaking the frontend through markdown format changes.

**Do not start V3.6 before V3.5.4.** Adding features to a frontend that parses markdown is building on sand.
