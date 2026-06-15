# CodePilot - Project Context

> Harness version: v1.2
> Last updated: 2026-06-13
> Repository reality checked: 2026-06-13

## Current Version

CodePilot V3.5.2 makes evidence-grounded Agent contributions visible through frontend summary cards, grouped
findings, and distinct evidence labels while preserving the complete Markdown report and old-report fallback.
It builds on V3.5.1 MiMo mode selection and V3.5 evaluation infrastructure, with 327 collected backend tests
(326 passed, 1 skipped) and 19 frontend tests.

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
| V2.5 | 2026-06-07 | `8b6347e` onward | Insight engine, mixed-language reviews, history, structured errors, URL validation, exact token counting, frontend reliability |
| V2.6 | 2026-06-07 | `4ae27d2` onward | Context decomposition, versioned prompt system, structured review adapter, parser/lifecycle cleanup, V3-ready boundaries |
| V3.0 | 2026-06-08 | `097dbee`~5 commits | Safety sandbox, deep context, evidence store, structured LLM, multi-agent review, V3 evaluation hardening |
| V3.1 | 2026-06-08 | `097dbee` to `9fdc220` | Structured finding persistence, agent state storage, graph-ready ReviewState, LangGraph deferred, inspectable agent results |
| V3.2 | 2026-06-08 | Through `636b7d8` | Tiered retrieval, deterministic context compression, large repo mode, retrieval metrics |
| V3.3 | 2026-06-08 | Through `2cb94c9` | CLI, CI report mode, optional MCP server integration, diff-aware review scope |
| V3.4 | 2026-06-09 | `8e06909` onward | Repository classification, human-readable composer, agent visibility, actionable guidance, report quality evaluation |
| V3.4.1 | 2026-06-09 | `bd8aea1` onward | Shared report constants, reduced classification false positives, evaluation report persistence, V3.4 artifact |
| V3.5 | 2026-06-11 | `707cb4d` onward | Versioned evaluation runs, deterministic quality metrics, optional real LLM, usage/cost summaries, regression artifacts |
| V3.5.1 | 2026-06-13 | MiMo LLM mode | MiMo LLM mode selection (mock/mimo), backend config, frontend selector, 327 tests |
| V3.5.2 | 2026-06-13 | Agent contribution visualization | Client-side Agent summary/findings parsing, compact contribution cards, grouped findings, and visible evidence IDs |

## Architecture Summary

CodePilot is a modular monolith in one repository, deployed as two services:

```text
Next.js frontend
  -> HTTP /api/reviews
FastAPI backend
  -> clone public GitHub repo
  -> orchestrate review lifecycle through ReviewPipeline
  -> run every matching registered parser through direct or composite parsing
  -> calculate file metrics and dependency graph
  -> classify roles, infer purpose, and score files
  -> build focused ReviewContext and deterministic repository insights
  -> render a versioned, token-budgeted prompt
  -> validate structured findings against safe evidence IDs
  -> compose a human-readable V3 report with agent summaries and actionable guidance
  -> preserve the shared-contract four sections and snippet-free evidence appendix
  -> persist in SQLite
  -> export Markdown

Evaluation CLI
  -> load versioned fixture or optional public repository dataset
  -> execute the same ReviewPipeline and SandboxFilter path
  -> score report quality and aggregate agent usage
  -> persist run, summary, per-repo, cost, quality, and optional comparison artifacts
```

Backend modules:

- `backend/api` - Review routes and structured error handlers.
- `backend/core` - Settings, environment loading, shared report contract loading, and logger setup.
- `backend/llm` - Mock and retrying OpenAI-compatible LLM clients selected at the runner composition boundary.
- `backend/models` - API schemas, focused review context models, compatibility context, and structured review findings.
- `backend/prompts` - Versioned prompt templates, sections, rendering, and token budgeting.
- `backend/parsers` - Parser protocol, registry, composite parser, and Python/JavaScript/TypeScript discovery and extraction.
- `backend/reviewers` - V2 Markdown adaptation, V3 human-readable composition, safe appendices, and export orchestration.
- `backend/services` - Clone service, repository indexer, dependency graph, calibrated scoring, insight engine, and token counting.
- `backend/storage` - SQLite review store using WAL mode.
- `backend/tasks` - Background task runner using `ThreadPoolExecutor(max_workers=2)` plus review pipeline orchestration.
- `backend/agents` - V3 evidence-grounded review agents and orchestrator.
- `backend/workflows` - CLI/CI/MCP integration layer, safe summaries, severity gates, and diff parsing.
- `backend/cli.py`, `backend/mcp_server.py` - Developer workflow entry points over the shared integration layer.
- `evaluation` - Versioned datasets, local fixtures, run registry, deterministic quality metrics, optional pricing,
  fixed artifacts, and compatible-run regression comparison.

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
| Tokenizer | tiktoken | 0.13.0 | `backend/requirements.txt` |
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
| `GET` | `/api/reviews` | List persisted reviews newest first. |
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
9. Run `npm test` in `frontend`.
10. Run `npm run build` in `frontend`.

## Test State

- `pytest` collected 327 tests on 2026-06-13: 326 passed, 1 skipped (`test_sandbox_rejects_paths_outside_repo`).
- Unit tests: 303 collected across context compatibility, prompts, structured reviews, report composition and quality,
  evaluation registry/artifacts/comparison/costs, review state, backend services, parsers, sandbox safety, evidence,
  structured LLM agents, multi-agent orchestration, V3 hardening, diff scope, lifecycle, API errors, LLM behavior,
  storage, task runner, and MiMo LLM mode.
- Integration tests: 23 collected for review API/history/errors, language review pipelines, CLI/CI, MCP wrappers, and diff mode.
- Regression tests: 1 collected for Regression-001 tree-sitter non-ASCII parsing.
- Frontend tests: 19 passing tests for Markdown, Agent contribution cards, grouped findings, evidence labels,
  old-report fallbacks, history, validation, API error handling, loading/error fallbacks, and LLM mode selector.
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
- V3.4 deterministic report quality evaluation ran on 2026-06-09 with no network or real LLM.
- V3.4 result: 8/8 checks passed; the sample report was 5,516 characters and 102 lines with no snippet leakage.
- V3.4 report artifact persisted at `reports/v34-flask-quality-sample.md` (5,516 chars, 102 lines, Flask-like sample).
- V3.4.1 patch: shared report constants, reduced classification false positives, evaluation report markdown persistence.
- V3.5 deterministic fixture evaluation ran on 2026-06-11 without network or credentials and passed all quality checks.
- V3.5 run artifacts include fixed summaries, per-repository JSON/Markdown, usage metadata, and optional comparable-run
  regression reports under `evaluation/runs/<run-id>/`.
- Missing real-LLM credentials are rejected before artifact creation; live model calls remain outside CI.

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `PYTHON_VERSION` | `3.11.11` | Runtime documentation in `.env.example`. |
| `USE_MOCK_LLM` | `true` | Toggle deterministic mock LLM vs real API. |
| `ENABLE_REAL_LLM` | `false` | Required opt-in guard before a real OpenAI-compatible client can be used. |
| `REVIEW_ENGINE` | `v3_multi_agent` | Selects `v2`, `v3_single_agent`, or `v3_multi_agent`. |
| `OPENAI_API_KEY` | empty | Required only when `USE_MOCK_LLM=false`. |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible endpoint. |
| `OPENAI_MODEL` | `gpt-4o-mini` | Chat model name. |
| `MIMO_API_KEY` | empty | Optional MiMo LLM API key. Set in backend `.env` only. |
| `MIMO_BASE_URL` | `https://token-plan-cn.xiaomimimo.com/v1` | MiMo-compatible endpoint. |
| `MIMO_MODEL_NAME` | `mimo-v2.5-pro` | MiMo chat model name. |
| `DATABASE_PATH` | `backend/data/codepilot.db` | SQLite database path. |
| `WORKSPACE_PATH` | `backend/workspace` | Temporary clone workspace. |
| `REPORTS_PATH` | `reports` | Markdown export directory. |
| `CORS_ALLOW_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Explicit local frontend origins. |
| `CORS_ALLOW_ORIGIN_REGEX` | `https?://(localhost|127\.0\.0\.1):\d+` | Local dev origin regex. |
| `MAX_FILES` | `300` | Maximum source files analyzed. |
| `MAX_FILE_SIZE_BYTES` | `204800` | Per-file size limit. |
| `LARGE_REPO_THRESHOLD` | `300` | Enables V3.2 large repo retrieval tiering when supported source files exceed this count. |
| `FINAL_PROMPT_TOKEN_BUDGET` | `5000` | Approximate prompt token budget. |
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8000` | Frontend API base URL. |

## Known Constraints

1. Mixed-language import resolution is static; Python-to-browser-language runtime relationships are not inferred.
2. Repository access is canonical public GitHub HTTPS URLs only.
3. Review execution is in-process with two worker threads.
4. Cloned repositories are temporary and should be cleaned after each task.
5. SQLite fits single-instance deployment, not multi-instance distributed writes.
6. Free-tier hosting can have cold starts and ephemeral local filesystem limits.
7. Local scripts and CI are Windows-first.
8. `RepositoryContext` is a V2.5 compatibility layer; new internal work uses `ReviewContext`.
9. V3.4 responsibility labels and related-test matching are static heuristics; mock mode does not claim deep semantics.
10. V3.5 deterministic quality scores are a product rubric, not human preference or semantic-correctness labels.
11. Token counts are local estimates; cost is only calculated for an exact model entry in an optional pricing config.
12. Real-LLM evaluations are network-dependent, billable, and nondeterministic, so CI does not run them.

## Reserved Directories

| Directory | Current State | Intended Use |
|-----------|---------------|--------------|
| `backend/mcp_server.py` | Optional integration | Registers V3.3 MCP tools when the external MCP SDK is installed. |
| `evaluation/runs/` | Gitignored runtime output | Stores V3.5 run registry, summaries, per-repo artifacts, and comparisons. |

## Cross-References

- Mission and quality bar: `GOAL.md`
- Architecture details: `ARCHITECTURE.md`
- Test inventory: `TESTING.md`
- Release process: `RELEASE_RULES.md`
- Planned work: `ROADMAP.md`
- Decisions backing current state: `DECISION_LOG.md`
