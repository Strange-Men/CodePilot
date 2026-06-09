# CodePilot - Architecture

> Harness version: v1.2
> Last updated: 2026-06-08
> Repository reality checked: 2026-06-08

## System Overview

CodePilot is a modular monolith repository with a FastAPI backend and Next.js frontend. The backend and frontend deploy independently, but the repository keeps their contracts, docs, and tests together.

```text
Browser
  -> Next.js frontend on Vercel or localhost:3000
  -> FastAPI backend on Render or localhost:8000
  -> SQLite review store
  -> temporary git clone workspace
  -> Markdown reports directory
```

## Runtime Flow

```text
1. User submits a public GitHub repository URL.
2. Frontend POSTs to /api/reviews.
3. Backend creates a pending review row and schedules a background task.
4. ReviewTaskRunner schedules execution on the in-process worker pool.
5. ReviewPipeline clones the repository using shallow git clone.
6. ReviewPipeline discovers every matching registered parser; mixed repositories use CompositeSourceParser while single-language repositories keep their direct parser path.
7. Parsers extract structure, metrics, entry-point signals, and internal import candidates into one analyzed file set.
8. Indexer builds one DependencyGraph, calculates graph metrics, classifies file roles, infers purpose, scores files, and runs RepositoryInsightEngine.
9. PromptRenderer builds a versioned insight- and graph-aware prompt within FINAL_PROMPT_TOKEN_BUDGET.
10. LLM client returns report text; transient real-client failures receive three exponential-backoff retries, while mock mode remains deterministic.
11. MarkdownReviewAdapter converts output through StructuredReviewDraft, normalizes the four required sections, and appends repository intelligence exports.
12. Store persists status, report, and export path.
13. Frontend polls /api/reviews/{task_id} until completed or failed and can load persisted reviews from GET /api/reviews.
14. User can read onboarding and risk guidance or download Markdown from /api/reviews/{task_id}/export.
```

## Backend Module Map

| Module | Key File | Responsibility | Important Details |
|--------|----------|----------------|-------------------|
| Entry | `backend/main.py` | FastAPI app setup, CORS, router mounting, `/health` | Uses settings singleton and shared store/runner. |
| API | `backend/api/reviews.py`, `backend/api/errors.py` | Review creation, history, polling, export, and structured errors | Errors use `{error, code, detail}` without changing successful item responses. |
| Core | `backend/core/config.py`, `backend/core/report_contract.py`, `backend/core/logging.py` | Settings, shared report contract loading, and logger setup | Loads `.env`, creates runtime paths, reads `contracts/report_sections.json`, and centralizes backend logger initialization. |
| Models | `backend/models/review.py`, `backend/models/context.py`, `backend/models/structured_review.py` | API schemas, focused review context, compatibility context, and structured findings | `ReviewStatus` lifecycle and flat API payloads remain unchanged. |
| Prompts | `backend/prompts/` | Versioned prompt sections, rendering, and token budgets | Prompt policy is independently testable and separate from report export. |
| LLM | `backend/llm/client.py` | Mock and OpenAI-compatible clients | Mock is default; the real client retries transient transport, 408, 409, 429, and 5xx failures three times with exponential backoff. |
| Parser | `backend/parsers/base.py`, `backend/parsers/registry.py`, `backend/parsers/composite.py`, `backend/parsers/python_parser.py`, `backend/parsers/javascript_parser.py` | Parser protocol, registry, composite mixed-language delegation, and structure extraction | Single-language behavior stays direct; mixed Python/JavaScript/TypeScript files share one index and graph. |
| Reviewer | `backend/reviewers/report_generator.py`, `backend/reviewers/markdown_adapter.py` | Review orchestration, structured Markdown adaptation, and export | Enforces the four-section contract while preserving appendices and frontend output. |
| Shared Contract | `contracts/report_sections.json` | Ordered report section contract consumed by backend and frontend | Defines the V1 report section IDs and titles without coupling either runtime to the other. |
| Clone | `backend/services/clone_service.py` | Public GitHub clone and cleanup | Validates allowed URLs and retries transient failures. |
| Indexer | `backend/services/indexer.py` | Convert parsed files into `ReviewContext` | Generates focused metadata, file, dependency, and insight bundles; flat `RepositoryContext` remains compatible. |
| Dependency Graph | `backend/services/dependency_graph.py` | Resolve internal imports and calculate graph signals | Produces deterministic edges, fan-in/out, hubs, fan-in-based orphans, and strongly connected dependency cycles. |
| Insight Engine | `backend/services/insights.py` | Convert context metrics and graph signals into architectural guidance | Produces architecture overview, risk hotspots, onboarding order, and refactoring candidates with explanations. |
| Token Counting | `backend/services/token_counting.py` | Count and fit prompt tokens | Uses the configured OpenAI model encoding with a stable fallback for unknown models. |
| Scoring | `backend/services/scoring.py` | Classify and prioritize files | Uses an absolute saturating 0-100 scale so small repositories do not automatically receive Critical labels. |
| Storage | `backend/storage/sqlite.py` | SQLite persistence | Uses WAL mode, busy timeout, and thread lock. |
| Tasks | `backend/tasks/runner.py`, `backend/tasks/pipeline.py` | Background scheduling and review pipeline orchestration | `ThreadPoolExecutor(max_workers=2)` remains the execution model. |
| Agents | `backend/agents/` | V3 evidence-grounded review agents and fan-out/fan-in orchestration | Agents consume `ReviewContext` and `EvidenceRetriever`, produce structured findings, and cannot read files directly. |
| Workflows | `backend/workflows/`, `backend/cli.py`, `backend/mcp_server.py` | CLI, CI, MCP, and diff-aware integration | Wraps `ReviewPipeline` and `ReviewStore`; MCP is optional and never reads raw repository files. |

## Frontend Module Map

| Path | Responsibility |
|------|----------------|
| `frontend/app/page.tsx` | Single-page client composition for submission, polling, status display, and report rendering. |
| `frontend/app/layout.tsx` | Root layout and metadata. |
| `frontend/app/error.tsx`, `frontend/app/loading.tsx` | Route-level error boundary and loading fallback. |
| `frontend/app/globals.css` | Tailwind directives and theme variables. |
| `frontend/components/ReviewSubmissionForm.tsx` | Review URL form and submit state. |
| `frontend/components/ReviewHistory.tsx` | Persisted review list and previous-report selection. |
| `frontend/components/ReviewStatusDisplay.tsx` | Review lifecycle and export link display. |
| `frontend/components/ReportRenderer.tsx` | Report section rendering using the shared report contract. |
| `frontend/components/ui/button.tsx` | Button primitive using class-variance-authority. |
| `frontend/components/ui/card.tsx` | Card primitive. |
| `frontend/components/ui/input.tsx` | Input primitive. |
| `frontend/hooks/useReviewPolling.ts` | Polling lifecycle for review status. |
| `frontend/lib/api.ts` | Frontend API client for submission, polling, history, and structured errors. |
| `frontend/lib/validation.ts` | Client-side canonical GitHub repository URL validation. |
| `frontend/lib/report.ts` | Status labels, terminal states, and shared-contract report parsing. |
| `frontend/lib/types.ts` | Frontend review API types. |
| `frontend/lib/utils.ts` | `cn()` helper using clsx and tailwind-merge. |

## API Contract

### `POST /api/reviews`

Request body:

```json
{
  "repo_url": "https://github.com/owner/repo"
}
```

Response body:

```json
{
  "task_id": "hex-string"
}
```

### `GET /api/reviews/{task_id}`

Response body:

```json
{
  "task_id": "hex-string",
  "repo_url": "https://github.com/owner/repo",
  "status": "pending|cloning|parsing|summarizing|reviewing|completed|failed",
  "error": null,
  "report_markdown": null,
  "export_path": null
}
```

### `GET /api/reviews`

Returns newest reviews first using the existing item response shape. Supports `limit=1..100`.

### `GET /api/reviews/{task_id}/export`

Returns `text/markdown` when completed. Returns 404 for unknown tasks and 409 when the report is not ready.

All JSON API errors use:

```json
{
  "error": "Human-readable summary",
  "code": "stable_machine_code",
  "detail": "Actionable detail"
}
```

## Data Model

`ReviewStatus` values:

```text
pending -> cloning -> parsing -> summarizing -> reviewing -> completed
                                              -> failed
```

Internal `ReviewContext` contains:

- `RepoMetadata` for identity, language, counts, metrics, and summary.
- `FileAnalysisBundle` for summaries and structural roles.
- `DependencyStructure` for edges, cycles, hubs, and orphans.
- `InsightReport` for architecture, hotspots, onboarding, and refactoring guidance.

`RepositoryContext` preserves the flat V2.5 constructor and serialized fields through explicit conversion methods.

`CodeFileSummary` contains:

- `path`
- `classes`
- `functions`
- `purpose`
- `summary`
- `line_count`
- `function_count`
- `complexity_estimate`
- `importance_score`
- `importance_label`
- `file_role`
- `dependencies`
- `fan_in`
- `fan_out`
- graph flags for cycles, hubs, and orphans

## Design Decisions

### 1. Modular Monolith

Decision: keep backend, frontend, tests, docs, and deployment files in one repository.

Rationale: MVP speed, easier local development, simpler CI, and clear deployment split without distributed-system overhead.

Decision log: `DECISION-010`.

### 2. Context Engineering Over Raw Code

Decision: parse source into structured summaries before LLM review.

Rationale: controls prompt size, improves signal, avoids sending large raw files, and supports deterministic mock-mode tests.

Decision log: `DECISION-004`.

### 3. Parser Registry Before Multi-Language Expansion

Decision: route parsing through a registry-backed parser protocol. V2 registers Python, JavaScript, and TypeScript parser entries.

Rationale: decouples task orchestration and indexing from concrete parser implementations without changing API contracts, report output, or current Python behavior.

Decision log: `DECISION-018`.

### 4. Decompose Review Pipeline From Task Scheduling

Decision: keep ReviewTaskRunner responsible for task creation and worker-pool scheduling, and move clone/parse/summarize/review/cleanup orchestration into ReviewPipeline.

Rationale: reduces coupling in the runner while preserving status transitions, SQLite schema, API behavior, workspace cleanup, and the in-process ThreadPoolExecutor execution model.

Decision log: `DECISION-019`.

### 5. Inject LLM Client at the Runner Boundary

Decision: build or accept the LLMClient in ReviewTaskRunner and inject it into ReviewPipeline, which passes it to ReportGenerator.

Rationale: keeps provider selection at the composition boundary while preserving mock behavior, OpenAI-compatible behavior, prompts, report normalization, and current execution flow.

Decision log: `DECISION-020`.

### 6. Shared Four-Section Report Contract

Decision: normalize every review to Architecture Summary, Code Smells, Maintainability Issues, and Refactoring Suggestions, with the ordered section titles loaded from `contracts/report_sections.json`.

Rationale: stable UX and predictable export format even when LLM output varies, while avoiding independent backend and frontend section definitions.

Decision logs: `DECISION-005`, `DECISION-021`.

### 7. Mock Mode by Default

Decision: default `USE_MOCK_LLM=true`.

Rationale: no credentials needed for demos, CI, smoke testing, or local onboarding.

Decision log: `DECISION-003`.

### 8. SQLite WAL Storage

Decision: use SQLite with WAL mode and locking.

Rationale: zero database infrastructure and enough durability for the single-instance MVP.

Decision log: `DECISION-002`.

### 9. Windows-First Tooling

Decision: use PowerShell scripts and Windows CI.

Rationale: matches primary development environment while Docker covers Linux production runtime.

Decision log: `DECISION-001`.

### 10. Render Docker Backend and Vercel Frontend

Decision: deploy backend to Render via Docker and frontend to Vercel.

Rationale: free-tier availability, easy Git integration, and Docker avoids buildpack runtime ambiguity.

Decision logs: `DECISION-007`, `DECISION-008`, `DECISION-006`.

### 11. Harness Engineering System v1.2

Decision: install `.harness/` governance docs, workflow references, regression rules, evaluation harness, and automated audit enforcement.

Rationale: preserve architecture intent, quality gates, agent roles, regression coverage, evaluation evidence, and reality-first audit behavior.

Decision logs: `DECISION-011`, `DECISION-015`, `DECISION-016`, `DECISION-017`.

## Invariants

| Invariant | Current Value | Source |
|-----------|---------------|--------|
| Max analyzed files | 300 | `backend/core/config.py` |
| Max file size | 204800 bytes | `backend/core/config.py` |
| Prompt budget | 5000 model tokens | `backend/core/config.py` |
| Worker count | 2 | `backend/tasks/runner.py` |
| Required report sections | 4 | `contracts/report_sections.json` |
| Python runtime | 3.11.11 | `.python-version`, `runtime.txt` |
| Node runtime | 20 | CI and Dockerfile |

## V3

V3.0 introduced evidence-grounded review with the following modules:

- `backend/services/sandbox.py` for safe manifest-based file access and secret redaction.
- `backend/services/evidence.py` for stable `evidence_id` generation, storage, and lexical retrieval.
- `backend/services/deep_context.py` for symbol, call, and class context summaries.
- `backend/agents/` for Architecture, CodeSmell, Maintainability, Refactor, and orchestrator behavior.

V3.1 added structured persistence and graph-ready state:

- Structured finding persistence in SQLite alongside Markdown reports.
- Agent state storage for per-agent intermediate results.
- Graph-ready `ReviewState` for future LangGraph migration (LangGraph deferred).
- Inspectable agent results.

V3.2 added tiered retrieval, context compression, large repo mode, and retrieval metrics.

V3.3 adds `ReviewWorkflow`, CLI/CI commands, optional MCP SDK registration, and `ReviewScope` for changed-file plus dependency-neighbor retrieval. Full-repo behavior remains unchanged when no scope is supplied. V3 remains opt-in through `REVIEW_ENGINE`; `v2` remains the default. See `docs/V3_ARCHITECTURE.md`, `docs/V3_2_RETRIEVAL.md`, and `docs/V3_3_WORKFLOWS.md`.

V3.4 adds report quality and agent visibility:

- `backend/services/insights.py` `_repository_type()` classifies repositories as web framework, CLI tool, SDK, mixed-language, etc.
- `backend/reviewers/report_composer.py` `HumanReadableReportComposer` produces bounded V3 reports with executive summary, repository identity, architecture map, agent summary, agent findings, actionable recommendations, and snippet-free evidence appendix.
- `backend/reviewers/constants.py` holds shared report constants (`DEFAULT_SECTION_CONTENT`, `format_cycle_group`) used by both the V2 adapter and V3 composer.
- `evaluation/report_quality.py` runs 8 deterministic quality gates (classification, ranking, cycles, agents, actionability, grounding, bounds, leakage) without network or real LLM.
- V3.4.1 reduces false-positive classification markers by removing generic `application`/`request`/`response` from framework detection.

## Cross-References

- Product goal: `GOAL.md`
- Current stack and constraints: `PROJECT_CONTEXT.md`
- Roadmap: `ROADMAP.md`
- Decisions: `DECISION_LOG.md`
- Workflow: `WORKFLOW.md`
