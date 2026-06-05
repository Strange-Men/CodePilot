# CodePilot - Project Context

> Harness version: v1.2
> Last updated: 2026-06-05
> Repository reality checked: 2026-06-05

## Current Version

CodePilot is at V1.4 release-freeze foundation state: production-ready MVP, engineering hardening, CI, deployment documentation, Docker support, evaluation harness, regression harness, frontend foundation extraction, parser registry foundation, review pipeline decomposition, LLM dependency injection foundation, evaluation metrics reliability, shared report-section contract, centralized backend logger setup, and 54 collected tests.

## Release History

| Version | Date | Commit Range | Highlights |
|---------|------|--------------|------------|
| V1.0 | Recorded before Harness install | `bd83f28` to `627dba4` | MVP clone -> parse -> context -> review -> export pipeline |
| V1.1 | 2026-06-05 | `9fb290d` to `544d4d4` | 44 tests, ruff, Windows CI, Docker Compose, Vercel frontend, Render Docker backend |
| Harness V1.2 | 2026-06-05 | In progress | Evaluation harness, regression harness, Harness audit enforcement |

## Architecture Summary

CodePilot is a modular monolith in one repository, deployed as two services:

```text
Next.js frontend
  -> HTTP /api/reviews
FastAPI backend
  -> clone public GitHub repo
  -> orchestrate review lifecycle through ReviewPipeline
  -> discover parser-supported files through the Python parser registry entry
  -> build RepositoryContext
  -> inject selected LLMClient into report generation
  -> generate normalized shared-contract four-section report
  -> persist in SQLite
  -> export Markdown
```

Backend modules:

- `backend/api` - Review routes.
- `backend/core` - Settings, environment loading, shared report contract loading, and logger setup.
- `backend/llm` - Mock and OpenAI-compatible LLM clients selected at the runner composition boundary.
- `backend/models` - Pydantic schemas and review status enum.
- `backend/parsers` - Parser protocol, parser registry, and registered Python parser/file discovery.
- `backend/reviewers` - Prompt building, report normalization, Markdown export.
- `backend/services` - Clone service and repository indexer.
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
6. Set up Node 20 with npm cache.
7. Run `python scripts/audit_harness.py --output harness-audit.json`.
8. Run `npm ci` in `frontend`.
9. Run `npm run build` in `frontend`.

## Test State

- `pytest --collect-only -q` collected 54 tests on 2026-06-05.
- Unit tests: 45 collected across clone service, parser, parser registry, report generator, evaluation metrics, review store, and task runner/pipeline delegation.
- Integration tests: 8 collected for review API routes.
- Regression tests: 1 collected for Regression-001 tree-sitter non-ASCII parsing.
- Smoke workflow: `scripts/smoke-backend.ps1` validates live backend behavior and Markdown export.

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
| `MAX_FILES` | `300` | Maximum Python files analyzed. |
| `MAX_FILE_SIZE_BYTES` | `204800` | Per-file size limit. |
| `FINAL_PROMPT_TOKEN_BUDGET` | `5000` | Prompt word budget. |
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8000` | Frontend API base URL. |

## Known Constraints

1. Parser only analyzes `.py` files.
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
| `graph/` | Empty/reserved project area | Future code graph and dependency analysis. |
| `mcp/` | Empty/reserved project area | Future MCP integration. |

## Cross-References

- Mission and quality bar: `GOAL.md`
- Architecture details: `ARCHITECTURE.md`
- Test inventory: `TESTING.md`
- Release process: `RELEASE_RULES.md`
- Planned work: `ROADMAP.md`
- Decisions backing current state: `DECISION_LOG.md`
