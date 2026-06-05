# CodePilot - Architecture

> Harness version: v1.2
> Last updated: 2026-06-05
> Repository reality checked: 2026-06-05

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
6. ReviewPipeline selects a registered parser based on repository files and discovers eligible source files.
7. Parser extracts structure and the indexer builds RepositoryContext with file summaries.
8. ReportGenerator builds a prompt within FINAL_PROMPT_TOKEN_BUDGET using the shared report-section contract.
9. LLM client returns report text, or mock client returns deterministic output.
10. ReportGenerator normalizes output to the four required contract sections.
11. Store persists status, report, and export path.
12. Frontend polls /api/reviews/{task_id} until completed or failed.
13. User can download Markdown from /api/reviews/{task_id}/export.
```

## Backend Module Map

| Module | Key File | Responsibility | Important Details |
|--------|----------|----------------|-------------------|
| Entry | `backend/main.py` | FastAPI app setup, CORS, router mounting, `/health` | Uses settings singleton and shared store/runner. |
| API | `backend/api/reviews.py` | Review creation, polling, and export endpoints | Raises 404 for missing task and 409 for export before completion. |
| Core | `backend/core/config.py`, `backend/core/report_contract.py`, `backend/core/logging.py` | Settings, shared report contract loading, and logger setup | Loads `.env`, creates runtime paths, reads `contracts/report_sections.json`, and centralizes backend logger initialization. |
| Models | `backend/models/review.py` | Review statuses and Pydantic schemas | `ReviewStatus` lifecycle is the API contract. |
| LLM | `backend/llm/client.py` | Mock and OpenAI-compatible clients | Mock is default through `USE_MOCK_LLM=true`; runner composes the selected client and injects it into the pipeline. |
| Parser | `backend/parsers/base.py`, `backend/parsers/registry.py`, `backend/parsers/python_parser.py`, `backend/parsers/javascript_parser.py` | Parser protocol, registry, Python/JavaScript/TypeScript file discovery, and structure extraction | Python uses tree-sitter with AST fallback; JS/TS uses dependency-free structural extraction for imports, classes, functions, and exports. |
| Reviewer | `backend/reviewers/report_generator.py` | Prompt building, section normalization, Markdown export | Enforces the shared-contract four-section report format. |
| Shared Contract | `contracts/report_sections.json` | Ordered report section contract consumed by backend and frontend | Defines the V1 report section IDs and titles without coupling either runtime to the other. |
| Clone | `backend/services/clone_service.py` | Public GitHub clone and cleanup | Validates allowed URLs and retries transient failures. |
| Indexer | `backend/services/indexer.py` | Convert parsed files into `RepositoryContext` | Generates deterministic summaries before LLM review. |
| Storage | `backend/storage/sqlite.py` | SQLite persistence | Uses WAL mode, busy timeout, and thread lock. |
| Tasks | `backend/tasks/runner.py`, `backend/tasks/pipeline.py` | Background scheduling and review pipeline orchestration | `ThreadPoolExecutor(max_workers=2)` remains the execution model. |

## Frontend Module Map

| Path | Responsibility |
|------|----------------|
| `frontend/app/page.tsx` | Single-page client composition for submission, polling, status display, and report rendering. |
| `frontend/app/layout.tsx` | Root layout and metadata. |
| `frontend/app/globals.css` | Tailwind directives and theme variables. |
| `frontend/components/ReviewSubmissionForm.tsx` | Review URL form and submit state. |
| `frontend/components/ReviewStatusDisplay.tsx` | Review lifecycle and export link display. |
| `frontend/components/ReportRenderer.tsx` | Report section rendering using the shared report contract. |
| `frontend/components/ui/button.tsx` | Button primitive using class-variance-authority. |
| `frontend/components/ui/card.tsx` | Card primitive. |
| `frontend/components/ui/input.tsx` | Input primitive. |
| `frontend/hooks/useReviewPolling.ts` | Polling lifecycle for review status. |
| `frontend/lib/api.ts` | Frontend API client for review submission and polling. |
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

### `GET /api/reviews/{task_id}/export`

Returns `text/markdown` when completed. Returns 404 for unknown tasks and 409 when the report is not ready.

## Data Model

`ReviewStatus` values:

```text
pending -> cloning -> parsing -> summarizing -> reviewing -> completed
                                              -> failed
```

`RepositoryContext` contains:

- `repo_url`
- `total_python_files` (legacy API-compatible field now populated with selected parser source-file count)
- `analyzed_files`
- `skipped_files`
- `file_summaries`
- `repository_summary`

`CodeFileSummary` contains:

- `path`
- `classes`
- `functions`
- `purpose`
- `summary`

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
| Prompt budget | 5000 words | `backend/core/config.py` |
| Worker count | 2 | `backend/tasks/runner.py` |
| Required report sections | 4 | `contracts/report_sections.json` |
| Python runtime | 3.11.11 | `.python-version`, `runtime.txt` |
| Node runtime | 20 | CI and Dockerfile |

## Multi-Agent Readiness

The repository contains reserved top-level directories for future expansion:

- `agents/` for specialized review agents.
- `graph/` for call graph and dependency analysis.
- `mcp/` for Model Context Protocol integration.

Current implementation does not orchestrate multiple agents. Future multi-agent work must define agent input/output contracts, persistence needs, and quality gates before implementation.

## Cross-References

- Product goal: `GOAL.md`
- Current stack and constraints: `PROJECT_CONTEXT.md`
- Roadmap: `ROADMAP.md`
- Decisions: `DECISION_LOG.md`
- Workflow: `WORKFLOW.md`
