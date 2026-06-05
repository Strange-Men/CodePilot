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
4. Task clones the repository using shallow git clone.
5. Task resolves the registered Python parser and discovers eligible Python files.
6. Parser extracts structure and the indexer builds RepositoryContext with file summaries.
7. ReportGenerator builds a prompt within FINAL_PROMPT_TOKEN_BUDGET.
8. LLM client returns report text, or mock client returns deterministic output.
9. ReportGenerator normalizes output to four required sections.
10. Store persists status, report, and export path.
11. Frontend polls /api/reviews/{task_id} until completed or failed.
12. User can download Markdown from /api/reviews/{task_id}/export.
```

## Backend Module Map

| Module | Key File | Responsibility | Important Details |
|--------|----------|----------------|-------------------|
| Entry | `backend/main.py` | FastAPI app setup, CORS, router mounting, `/health` | Uses settings singleton and shared store/runner. |
| API | `backend/api/reviews.py` | Review creation, polling, and export endpoints | Raises 404 for missing task and 409 for export before completion. |
| Config | `backend/core/config.py` | Pydantic settings and path creation | Loads `.env`, ignores unknown vars, creates data/workspace/reports dirs. |
| Models | `backend/models/review.py` | Review statuses and Pydantic schemas | `ReviewStatus` lifecycle is the API contract. |
| LLM | `backend/llm/client.py` | Mock and OpenAI-compatible clients | Mock is default through `USE_MOCK_LLM=true`. |
| Parser | `backend/parsers/base.py`, `backend/parsers/registry.py`, `backend/parsers/python_parser.py` | Parser protocol, registry, Python file discovery, and structure extraction | Python-only registered parser, tree-sitter with AST fallback. |
| Reviewer | `backend/reviewers/report_generator.py` | Prompt building, section normalization, Markdown export | Enforces four-section report format. |
| Clone | `backend/services/clone_service.py` | Public GitHub clone and cleanup | Validates allowed URLs and retries transient failures. |
| Indexer | `backend/services/indexer.py` | Convert parsed files into `RepositoryContext` | Generates deterministic summaries before LLM review. |
| Storage | `backend/storage/sqlite.py` | SQLite persistence | Uses WAL mode, busy timeout, and thread lock. |
| Tasks | `backend/tasks/runner.py` | Background review pipeline | `ThreadPoolExecutor(max_workers=2)`. |

## Frontend Module Map

| Path | Responsibility |
|------|----------------|
| `frontend/app/page.tsx` | Single-page client UI: URL input, submit, status polling, report rendering, export link. |
| `frontend/app/layout.tsx` | Root layout and metadata. |
| `frontend/app/globals.css` | Tailwind directives and theme variables. |
| `frontend/components/ui/button.tsx` | Button primitive using class-variance-authority. |
| `frontend/components/ui/card.tsx` | Card primitive. |
| `frontend/components/ui/input.tsx` | Input primitive. |
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
- `total_python_files`
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

Decision: route parsing through a registry-backed parser protocol while registering only the existing Python parser.

Rationale: decouples task orchestration and indexing from the concrete Python parser without changing API contracts, report output, or current Python behavior.

Decision log: `DECISION-018`.

### 4. Fixed Four-Section Report Format

Decision: normalize every review to Architecture Summary, Code Smells, Maintainability Issues, and Refactoring Suggestions.

Rationale: stable UX and predictable export format even when LLM output varies.

Decision log: `DECISION-005`.

### 5. Mock Mode by Default

Decision: default `USE_MOCK_LLM=true`.

Rationale: no credentials needed for demos, CI, smoke testing, or local onboarding.

Decision log: `DECISION-003`.

### 6. SQLite WAL Storage

Decision: use SQLite with WAL mode and locking.

Rationale: zero database infrastructure and enough durability for the single-instance MVP.

Decision log: `DECISION-002`.

### 7. Windows-First Tooling

Decision: use PowerShell scripts and Windows CI.

Rationale: matches primary development environment while Docker covers Linux production runtime.

Decision log: `DECISION-001`.

### 8. Render Docker Backend and Vercel Frontend

Decision: deploy backend to Render via Docker and frontend to Vercel.

Rationale: free-tier availability, easy Git integration, and Docker avoids buildpack runtime ambiguity.

Decision logs: `DECISION-007`, `DECISION-008`, `DECISION-006`.

### 9. Harness Engineering System v1.2

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
| Required report sections | 4 | `backend/reviewers/report_generator.py` |
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
