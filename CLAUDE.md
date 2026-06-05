# CLAUDE.md - CodePilot Project Instructions

## Project

CodePilot's mission is to be an AI Code Review & Refactor Agent for Large Repositories. It clones public GitHub repositories, analyzes source files, builds structured repository context, generates a four-section review report, displays it in a Next.js UI, and exports Markdown.

## Priority Order

Every session must prioritize in this order:

1. **Repository Intelligence** - parsing, context building, and code understanding.
2. **Code Review Quality** - accuracy, coverage, and actionability of review output.
3. **Refactor Capability** - surfacing concrete improvement suggestions.
4. **Multi-Language Support** - expanding repository intelligence beyond Python.
5. Engineering hygiene (tests, lint, docs, harness) supports the above but never replaces it.

Do not expand the harness, create new governance documents, or refactor documentation workflows unless the code-level work is already complete and the change is required to reflect reality.

## Harness System

Project governance lives in `.harness/`. Treat the repository as the source of truth and update Harness docs only when specific claims become factually wrong.

Before making changes, consult:

- `.harness/GOAL.md` - Mission, success criteria, non-goals, and quality bar.
- `.harness/PROJECT_CONTEXT.md` - Current version, stack, constraints, environment variables, and deployment state.
- `.harness/CLAUDE.md` - Claude role, authority, and boundaries.
- `.harness/AGENTS.md` - Codex role, authority, and boundaries.
- `.harness/WORKFLOW.md` - AI engineering workflow from idea to release.
- `.harness/TESTING.md` - Test pyramid, test inventory, conventions, and gaps.
- `.harness/RELEASE_RULES.md` - Quality gates, release checklist, rollback rules.
- `.harness/ARCHITECTURE.md` - System design, module map, data flow, and design decisions.
- `.harness/DECISION_LOG.md` - Record of key architecture, technical, deployment, and process decisions.
- `.harness/ROADMAP.md` - Completed, planned, and future work.
- `.harness/HARNESS_UPDATE_CHECKLIST.md` - Trigger matrix for keeping Harness docs current.
- `.harness/HARNESS_AUDIT_RULES.md` - Drift detection and reality-first audit rules.

Workflow copies for quick navigation live under `docs/workflows/`.

## Repository Facts

- Backend: FastAPI, Python 3.11.11, SQLite WAL storage, in-process `ThreadPoolExecutor`.
- Frontend: Next.js 15.5.19, React 19.0.0, TypeScript 5.7.2, Tailwind CSS 3.4.17.
- Parser: Python-only tree-sitter with AST fallback.
- LLM: mock mode by default or OpenAI-compatible chat completions.
- API endpoints: `POST /api/reviews`, `GET /api/reviews/{task_id}`, `GET /api/reviews/{task_id}/export`, `GET /health`.
- CI: GitHub Actions on `windows-latest`, with ruff, pytest, npm install, and frontend build.

## Development Commands

```powershell
# Backend
pytest
ruff check .

# Frontend
cd frontend
npm run build

# Full stack
docker-compose up

# Smoke test
powershell -File scripts/smoke-backend.ps1
```

## Guardrails

- Do not change application logic, frontend behavior, backend behavior, API contracts, deployment configuration, tests, or dependencies unless the task explicitly requires it.
- Harness updates are a cleanup task, not a primary objective. Only update harness docs when code changes have made them factually wrong.
- No raw source code is sent to the LLM review prompt; CodePilot sends structured context.
- Mock mode must remain deterministic and usable without credentials.
- Windows PowerShell remains the primary local workflow.
