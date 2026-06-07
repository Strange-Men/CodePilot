# CodePilot - Project Context

> Harness version: v1.2
> Last updated: 2026-06-07
> Repository reality checked: 2026-06-07

## Current Version

CodePilot is at V2.4 repository-intelligence hardening state: Python/JavaScript/TypeScript parsing, repository metrics, dependency graph analysis, calibrated file scoring, structural roles and purpose inference, graph-aware prompts, resilient LLM calls, rich Markdown rendering, and 131 collected tests.

## Release History

| Version | Date | Commit Range | Highlights |
|---------|------|--------------|------------|
| V1.0 | Recorded before Harness install | `bd83f28` to `627dba4` | MVP clone -> parse -> context -> review -> export pipeline |
| V1.1 | 2026-06-05 | `9fb290d` to `544d4d4` | 44 tests, ruff, Windows CI, Docker Compose, Vercel frontend, Render Docker backend |
| Harness V1.2 | 2026-06-05 | In progress | Evaluation harness, regression harness, Harness audit enforcement |
| V2.1 | 2026-06-07 | `871f6b6` | Repository/file metrics, importance ranking, prompt optimization, metrics export |
| V2.2 | 2026-06-07 | `df36f77` | Scoring intelligence, entry-point detection, file roles, rich Markdown reports |
| V2.3 | 2026-06-07 | `15a1121` | Internal dependency graph, fan-in/out, hubs, cycles, orphans, graph-aware scoring |
| V2.4 | 2026-06-07 | `f8be650` onward | CI audit repair, LLM retries, structural architecture context, calibrated scoring, quality coverage |

## Architecture Summary

CodePilot is a modular monolith in one repository, deployed as two services:

```text
Next.js frontend
  -> HTTP /api/reviews
FastAPI backend
  -> clone public GitHub repo
  -> orchestrate review lifecycle through ReviewPipeline
  -> select a registered parser based on repository files
  -> calculate file metrics and dependency graph
  -> classify roles, infer purpose, and score files
  -> build graph-aware RepositoryContext
  -> inject selected LLMClient into report generation
  -> generate normalized shared-contract four-section report
  -> persist in SQLite
  -> export Markdown
```

Backend modules:

- `backend/api` - Review routes.
- `backend/core` - Settings, environment loading, shared report contract loading, and logger setup.
- `backend/llm` - Mock and retrying OpenAI-compatible LLM clients selected at the runner composition boundary.
- `backend/models` - Pydantic schemas and review status enum.
- `backend/parsers` - Parser protocol, parser registry, registered Python parser, and JavaScript/TypeScript parser/file discovery.
- `backend/reviewers` - Graph-aware prompt building, report normalization, metrics/architecture appendices, Markdown export.
- `backend/services` - Clone service, repository indexer, dependency graph, and calibrated scoring.
- `backend/storage` - SQLite review store using WAL mode.
- `backend/tasks` - Background task runner using `ThreadPoolExecutor(max_workers=2)` plus review pipeline orchestration.

## Technology Stack

| Layer | Technology | Version | Source |
|-------|------------|---------|--------|
| Frontend framework | Next.js | 15.5.19 | `frontend/package.json` |
| UI library | React / React DOM | 19.0.0 | `frontend/package.json` |
| Language | TypeScript | 5.7.2 | `frontend/package.json` |
| Styling | Tailwind CSS | 3.4.17 | `frontend/package.json` |
| UI utilities | Radix Slot, cva, clsx, tailwind-merge, lucide-react | pinned | `frontend/package.json` |
| Backend framework | FastAPI | 0.115.6 | `backend/requirements.txt` |
| ASGI server | Uvicorn | 0.34.0 | `backend/requirements.txt` |
| Validation | Pydantic / pydantic-settings | 2.10.4 / 2.7.1 | `backend/requirements.txt` |
| HTTP client | httpx | 0.28.1 | `backend/requirements.txt` |
| Parser | tree-sitter / tree-sitter-language-pack | 0.24.0 / 0.7.0 | `backend/requirements.txt` |
| Test runner | pytest | 8.3.4 | `backend/requirements-dev.txt` |
| Linter | ruff | 0.8.4 | `backend/requirements-dev.txt` |
| Database | SQLite | Python stdlib | `backend/storage/sqlite.py` |
| Python runtime | CPython | 3.11.11 | `.python-version`, `runtime.txt`, Dockerfile |
| Node runtime | Node.js | 20 | CI and `Dockerfile.frontend` |

## API Surface

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Backend health check. |
| `POST` | `/api/reviews` | Submit a public GitHub repository URL and receive a `task_id`. |
| `GET` | `/api/reviews/{task_id}` | Poll task status and retrieve the report once completed. |
| `GET` | `/api/reviews/{task_id}/export` | Download completed report as Markdown. |

Review status lifecycle: `pending -> cloning -> parsing -> summarizing -> reviewing -> completed`; failures move to `failed`.

## Deployment Architecture

| Component | Platform | Method | Config Source |
|-----------|----------|--------|---------------|
| Frontend | Vercel Free | Git-connected Next.js deployment | Platform UI, `docs/VERCEL_DEPLOYMENT.md` |
| Backend | Render Free | Docker deployment using `Dockerfile.backend` | Platform UI, `DEPLOYMENT.md` |
| Local full stack | Docker Compose | `docker-compose up` | `docker-compose.yml` |

There is no `vercel.json` and no `render.yaml`; production deployment is configured in the hosting dashboards.

## CI

GitHub Actions workflow `.github/workflows/ci.yml` runs on `windows-latest`:

1. Checkout.
2. Set up Python 3.11.
3. Install `backend/requirements-dev.txt`.
4. Run `ruff check .`.
5. Run `pytest`.
6. Run `python scripts/audit_harness.py --output harness-audit.json`.
7. Set up Node 20 with npm cache.
8. Run `npm ci` in `frontend`.
9. Run `npm run build` in `frontend`.

## Test State

- `pytest --collect-only -q` collected 131 tests on 2026-06-07.
- Unit tests: 121 collected across clone service, parsers, parser registry, metrics, dependency graph, scoring, purpose inference, LLM retries, report generation, evaluation, storage, and task orchestration.
- Integration tests: 9 collected for review API routes and JS/TS review pipeline completion.
- Regression tests: 1 collected for Regression-001 tree-sitter non-ASCII parsing.
- Smoke workflow: `scripts/smoke-backend.ps1` validates live backend behavior and Markdown export.

## Release Certification Evidence

- V1.4.1 certification evaluation ran on 2026-06-05 against `pallets/click`, `pallets/flask`, `expressjs/express`, and `jupyter/notebook`.
- Evaluation report artifacts were generated at `evaluation/reports/eval-20260605-135055.json` and `evaluation/reports/eval-20260605-135055.md`.
- Result: 4/4 repositories passed, 0 failed, 100.0% success rate, 100.0% report completeness, 39.8s average runtime.
- Per-repo parser/runtime evidence: click 63 source files in 23.4s; flask 83 source files in 21.4s; express 0 source files in 11.2s; jupyter 11 source files in 103.3s.
- V2.0 parser evaluation ran on 2026-06-05 against `pallets/click`, `expressjs/express`, and `axios/axios`.
- V2.0 evaluation report artifacts were generated at `evaluation/reports/eval-20260605-145119.json`, `evaluation/reports/eval-20260605-145119.md`, `evaluation/reports/eval-20260605-145113.json`, and `evaluation/reports/eval-20260605-145113.md`.
- V2.0 result: click passed with 63 source files; express passed with 141 JavaScript files; axios passed with 178 JavaScript files.
- V2.0.1 integrity evaluation ran on 2026-06-05 with enforced `min_source_files` thresholds against `pallets/click` and `expressjs/express`.
- V2.0.1 result: click passed with 63 source files; express passed with 141 JavaScript files. Reports were generated at `evaluation/reports/eval-20260605-153358.*` and `evaluation/reports/eval-20260605-153343.*`.

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `PYTHON_VERSION` | `3.11.11` | Runtime documentation in `.env.example`. |
| `USE_MOCK_LLM` | `true` | Toggle deterministic mock LLM vs real API. |
| `OPENAI_API_KEY` | empty | Required only when `USE_MOCK_LLM=false`. |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible endpoint. |
| `OPENAI_MODEL` | `gpt-4o-mini` | Chat model name. |
| `DATABASE_PATH` | `backend/data/codepilot.db` | SQLite database path. |
| `WORKSPACE_PATH` | `backend/workspace` | Temporary clone workspace. |
| `REPORTS_PATH` | `reports` | Markdown export directory. |
| `CORS_ALLOW_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Explicit local frontend origins. |
| `CORS_ALLOW_ORIGIN_REGEX` | `https?://(localhost|127\.0\.0\.1):\d+` | Local dev origin regex. |
| `MAX_FILES` | `300` | Maximum source files analyzed. |
| `MAX_FILE_SIZE_BYTES` | `204800` | Per-file size limit. |
| `FINAL_PROMPT_TOKEN_BUDGET` | `5000` | Approximate prompt token budget. |
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8000` | Frontend API base URL. |

## Known Constraints

1. Each review selects one registered repository language; mixed-language analysis is not yet combined.
2. Repository access is public GitHub HTTPS only.
3. Review execution is in-process with two worker threads.
4. Cloned repositories are temporary and should be cleaned after each task.
5. SQLite fits single-instance deployment, not multi-instance distributed writes.
6. Free-tier hosting can have cold starts and ephemeral local filesystem limits.
7. Local scripts and CI are Windows-first.

## Reserved Directories

| Directory | Current State | Intended Use |
|-----------|---------------|--------------|
| `agents/` | Empty/reserved project area | Future multi-agent review orchestration. |
| `mcp/` | Empty/reserved project area | Future MCP integration. |

## Cross-References

- Mission and quality bar: `GOAL.md`
- Architecture details: `ARCHITECTURE.md`
- Test inventory: `TESTING.md`
- Release process: `RELEASE_RULES.md`
- Planned work: `ROADMAP.md`
- Decisions backing current state: `DECISION_LOG.md`
