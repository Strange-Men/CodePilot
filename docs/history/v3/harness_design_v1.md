# Harness Design V1.1 — CodePilot

> Generated: 2026-06-05
> Updated: 2026-06-05 (v1.1 — workflow integration, audit protection, multi-agent readiness)
> Status: Active
> Harness Version: v1.1

---

# Harness Structure

```
CodePilot/
├── CLAUDE.md                          # Root-level project instructions for Claude Code
└── .harness/
    ├── GOAL.md                        # Mission, success criteria, non-goals, quality bar
    ├── PROJECT_CONTEXT.md             # Current state (V1.1), tech stack, constraints, env vars
    ├── CLAUDE.md                      # Claude's role: architect, QA, harness engineer — may modify code for bugs/tests/refactors
    ├── AGENTS.md                      # Codex's role: engineer, implementer, deployer — may update harness docs when instructed
    ├── WORKFLOW.md                    # Complete AI engineering workflow: idea → spec → implement → review → release
    ├── TESTING.md                     # Test pyramid, 44 tests documented, conventions, test debt
    ├── RELEASE_RULES.md               # Quality gates (hard/soft), release checklist, rollback rules
    ├── ARCHITECTURE.md                # System diagram, module map, data flow, 6 design decisions, multi-agent readiness
    ├── DECISION_LOG.md                # 9 decisions logged (DECISION-001 through DECISION-009)
    ├── ROADMAP.md                     # V1.0 ✅, V1.1 ✅, V1.2 planned, V2.0/V3.0 future, multi-agent roadmap
    ├── HARNESS_UPDATE_CHECKLIST.md    # Trigger matrix + update workflow + self-improvement rules
    └── HARNESS_AUDIT_RULES.md         # Audit protection: reality-first, drift detection, HARNESS_AUDIT_REPORT generation
```

---

# File Specifications

## GOAL.md — Project Goal

### Mission

Build and maintain a production-quality tool that helps developers automatically analyze GitHub repositories and generate professional code review reports using AI.

### Success Criteria

1. A developer pastes a public GitHub URL and receives a structured, actionable code review within 60 seconds.
2. The review covers four fixed dimensions: Architecture Summary, Code Smells, Maintainability Issues, Refactoring Suggestions.
3. The system handles real-world Python repositories (up to 300 files) without crashing or exceeding token budgets.
4. The tool is deployable on free-tier infrastructure (Vercel + Render) with zero manual intervention after setup.
5. Mock mode enables full end-to-end demo without any API credentials.

### Non-Goals (Current)

- Private repository support (requires OAuth — deferred to V2+)
- Multi-language support beyond Python (deferred to V2+)
- Real-time collaborative review or commenting
- IDE plugin or CLI-only mode
- Self-hosted LLM inference (the system uses any OpenAI-compatible API endpoint)

### North Star Metric

Time from "paste URL" to "readable report" under 60 seconds for a typical 50-file Python repository.

### Quality Bar

- 44 automated tests passing (unit + integration)
- Ruff lint clean (zero warnings)
- Frontend builds without TypeScript errors
- Docker Compose brings up both services with a single command
- Smoke test verifies the full clone→parse→review→export pipeline

---

## PROJECT_CONTEXT.md — Project Context

### Current Version: V1.1

### Release History

| Version | Date | Commits | Highlights |
|---------|------|---------|------------|
| V1.0 | — | `bd83f28` → `627dba4` | Production-ready MVP: clone → parse → review → export pipeline |
| V1.1 | 2026-06-05 | `9fb290d` → `544d4d4` | Engineering hardening, 44 tests, Vercel + Render deployment |

### Architecture Summary

**Pattern:** Modular monolith — single repository, single deployable backend process, cleanly separated modules.

```
Frontend (Next.js 15 / React 19 / TypeScript)
    ↓ HTTP (POST/GET /api/reviews)
Backend (FastAPI / Python 3.11)
    ├── api/          — HTTP routes
    ├── core/         — Configuration
    ├── llm/          — LLM clients (mock + OpenAI-compatible)
    ├── models/       — Pydantic schemas
    ├── parsers/      — tree-sitter + AST fallback
    ├── reviewers/    — Prompt building + report normalization
    ├── services/     — Clone service, repository indexer
    ├── storage/      — SQLite (WAL mode)
    └── tasks/        — Background task runner (ThreadPoolExecutor)
```

**Data flow:**
`POST /api/reviews` → `ReviewTaskRunner.submit()` → background thread → clone → parse → summarize → LLM call → store in SQLite → cleanup workspace

### Technology Stack

| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| Frontend Framework | Next.js | 15.5.19 | App Router, single route `/` |
| UI Library | React | 19.0.0 | `"use client"` component |
| Language | TypeScript | 5.7.2 | Strict mode |
| Styling | Tailwind CSS | 3.4.17 | Custom HSL color system |
| Component Lib | shadcn/ui-style | — | Button, Card, Input (cva + Radix) |
| Backend Framework | FastAPI | 0.115.6 | Async-ready |
| ASGI Server | Uvicorn | 0.34.0 | — |
| Validation | Pydantic | 2.10.4 | + pydantic-settings 2.7.1 |
| HTTP Client | httpx | 0.28.1 | For OpenAI API calls |
| Parser | tree-sitter | 0.24.0 | + tree-sitter-language-pack 0.7.0 |
| Database | SQLite | stdlib | WAL mode, thread-safe |
| Python | CPython | 3.11.11 | Pinned via `.python-version` + `runtime.txt` |
| Node | Node.js | 20 | Alpine for Docker |

### Deployment Architecture

| Component | Platform | Tier | URL |
|-----------|----------|------|-----|
| Frontend | Vercel | Free | (auto-generated `.vercel.app`) |
| Backend | Render | Free (Docker) | `https://codepilot-i189.onrender.com` |

**CI:** GitHub Actions on `windows-latest` — ruff check, pytest, npm ci + build.

**No `vercel.json` or `render.yaml`** — deployment configured via platform UI settings.

### Test Coverage

- **44 automated tests** (unit + integration)
- **5 unit test files** covering: clone service, python parser, report generator, review store, task runner
- **1 integration test file** covering: reviews API (8 tests)
- **1 smoke test** (PowerShell) for full end-to-end pipeline

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `USE_MOCK_LLM` | `true` | Toggle mock vs real LLM |
| `OPENAI_API_KEY` | — | API key for real LLM |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | LLM endpoint |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model name |
| `DATABASE_PATH` | `backend/data/codepilot.db` | SQLite path |
| `WORKSPACE_PATH` | `backend/workspace` | Clone workspace |
| `REPORTS_PATH` | `reports` | Export directory |
| `MAX_FILES` | `300` | Max files to analyze |
| `MAX_FILE_SIZE_BYTES` | `204800` | 200KB per file limit |
| `FINAL_PROMPT_TOKEN_BUDGET` | `5000` | LLM prompt word budget |
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8000` | Frontend API URL |

### Known Constraints

1. **Python-only** — Parser only supports `.py` files.
2. **Public repos only** — No OAuth or GitHub token support.
3. **Single-threaded review** — `max_workers=2` in the task runner.
4. **Ephemeral workspace** — Cloned repos are deleted after review.
5. **Free-tier cold starts** — Render free tier spins down after inactivity (~30s cold start).
6. **Windows-first dev** — All scripts are PowerShell; CI runs on Windows.

### Placeholder Directories

| Directory | Future Purpose |
|-----------|---------------|
| `agents/` | Multi-agent review orchestration |
| `graph/` | Code graph / dependency analysis |
| `mcp/` | Model Context Protocol integration |

---

## CLAUDE.md — Claude Role Definition

### Role

Claude acts as the **Principal Architect, Staff QA Lead, and Harness Engineer** for CodePilot. Claude's primary responsibility remains architecture, QA, harness engineering, design reviews, and release audits. However, Claude may directly modify source code when the scope is bounded and the change improves iteration velocity.

### Responsibilities

#### 1. Product Management
- Define and maintain the product roadmap (`ROADMAP.md`)
- Prioritize features based on user value and technical feasibility
- Write acceptance criteria for each feature
- Approve or reject feature proposals

#### 2. Architecture
- Design system architecture and maintain `ARCHITECTURE.md`
- Evaluate architectural trade-offs and record decisions in `DECISION_LOG.md`
- Review all structural changes before implementation
- Ensure consistency across frontend, backend, and deployment layers

#### 3. Quality Assurance
- Define the test strategy (`TESTING.md`)
- Review test plans before implementation
- Audit test coverage after each release
- Approve or reject releases based on quality gates (`RELEASE_RULES.md`)

#### 4. Code Review
- Review all PRs / commits for correctness, security, and maintainability
- Enforce coding standards and conventions
- Identify technical debt and schedule remediation
- Verify that changes align with the architecture

#### 5. Harness Maintenance
- Keep all `.harness/` documents current
- Run the Harness Update Checklist after every project change
- Evolve the harness system itself based on lessons learned

#### 6. Direct Code Modification (Scoped)

Claude may directly modify source code (`backend/`, `frontend/`, `scripts/`) when:

1. **Fixing bugs** — Isolated defect repair with a regression test
2. **Writing or repairing tests** — Test creation, fixture repair, coverage gaps
3. **Performing small refactors** — Rename, extract, inline, or reorganize within a single module
4. **Maintaining Harness infrastructure** — Updating `.harness/` files, CI config, or project scaffolding
5. **Executing repository maintenance** — Dependency updates, lint fixes, formatting, dead code removal

Large feature implementation (new modules, new API endpoints, new UI pages) should still be delegated to Codex.

**Rationale:** The actual workflow uses Claude Code in terminal mode. Preventing Claude from touching code creates unnecessary handoffs and slows iteration for a solo founder.

### Operating Principles

1. **Architecture-first.** Design before code. Review before merge.
2. **Document everything.** Every decision, every trade-off, every exception gets recorded.
3. **Quality gates are hard gates.** A release that fails a quality gate does not ship.
4. **Context engineering first.** Never send raw code to the LLM when structured context is available.
5. **Deterministic by default.** Mock mode must work without any external dependencies.
6. **Windows-first.** All tooling must work on Windows with PowerShell.

### Decision Authority

| Domain | Claude Decides | Requires User Approval |
|--------|---------------|----------------------|
| Architecture patterns | ✅ | — |
| Test strategy | ✅ | — |
| Code review approval | ✅ | — |
| Harness document updates | ✅ | — |
| Bug fixes (isolated) | ✅ | — |
| Small refactors | ✅ | — |
| Feature prioritization | Recommends | ✅ |
| Release approval | Recommends | ✅ |
| Technology stack changes | Recommends | ✅ |
| Breaking changes | Recommends | ✅ |
| Large feature implementation | Delegates to Codex | ✅ |

### Boundaries

- Claude does NOT implement large features without delegation to Codex.
- Claude does NOT run deployment commands without user confirmation.
- Claude does NOT merge PRs without passing quality gates.
- Claude does NOT skip the Harness Update Checklist.
- Claude does NOT redefine governance rules in `.harness/` without recording the decision.

---

## AGENTS.md — Codex Role Definition

### Role

Codex acts as the **Engineer, Implementer, Refactorer, and Deployer** for CodePilot. Codex writes code, runs tests, and executes deployments based on Claude's designs and approvals.

### Responsibilities

#### 1. Implementation
- Write all source code (backend, frontend, scripts, configs)
- Implement features according to Claude-approved specifications
- Follow the architecture patterns defined in `ARCHITECTURE.md`
- Maintain code quality standards (linting, formatting, naming)

#### 2. Testing
- Write unit tests for all new modules
- Write integration tests for API endpoints
- Run the full test suite before marking work complete
- Fix failing tests immediately — never leave broken tests in the tree

#### 3. Refactoring
- Improve code structure without changing behavior
- Reduce technical debt as identified by Claude
- Extract shared utilities when duplication exceeds 3 occurrences
- Keep modules within single-responsibility boundaries

#### 4. Deployment
- Execute deployment procedures as documented
- Verify deployment health after each release
- Roll back if health checks fail
- Update deployment documentation when procedures change

#### 5. Documentation (Code-Level)
- Write docstrings for all public functions and classes
- Add inline comments for non-obvious logic
- Update README.md when user-facing behavior changes
- Keep `.env.example` in sync with actual config

### Commit Convention

```
<type>(<scope>): <description>

[optional body]
```

**Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `release`

**Scopes:** `backend`, `frontend`, `deploy`, `ci`, `v1.1`, etc.

**Examples:**
```
feat(backend): add multi-language parser support
fix(frontend): correct polling interval for status updates
refactor(backend): extract LLM client interface
test(backend): add integration tests for export endpoint
docs(v1.2): add changelog for v1.2 release
```

### Quality Checklist (Pre-Commit)

- [ ] `ruff check backend/` — zero warnings
- [ ] `pytest tests/` — all tests pass
- [ ] `cd frontend && npm run build` — no TypeScript errors
- [ ] No `print()` debug statements left in code
- [ ] No hardcoded paths or credentials
- [ ] `.env.example` updated if new env vars added
- [ ] Docstrings on all new public functions

### Quality Checklist (Pre-PR)

- [ ] All new code has corresponding tests
- [ ] Test coverage does not decrease
- [ ] `docker-compose up` starts both services
- [ ] Smoke test passes (`scripts/smoke-backend.ps1`)
- [ ] Documentation updated for user-facing changes
- [ ] No merge conflicts with `master`

### Harness Maintenance Rights

Codex may update Harness documentation when:

- **Explicitly instructed** by Claude or the user to update a specific document
- **Performing Harness maintenance** — correcting stale data, updating test counts, syncing versions
- **Updating project state after implementation** — reflecting new modules, endpoints, or dependencies in `PROJECT_CONTEXT.md`, `ARCHITECTURE.md`, `TESTING.md`, `ROADMAP.md`
- **Synchronizing architecture, testing, roadmap, or release documents** — keeping docs aligned with code changes

Codex must preserve architectural intent and may not redefine governance rules without Claude review.

**Rationale:** Keeping Harness documents synchronized with the repository should not require manual handoff for every change.

### Boundaries

- Codex does NOT make architectural decisions — escalate to Claude.
- Codex does NOT approve releases — that requires Claude's quality gate review.
- Codex does NOT redefine governance rules in `.harness/` (e.g., changing quality gates, role definitions, or decision authority).
- Codex does NOT skip tests to save time.
- Codex does NOT deploy without Claude's approval.

### Escalation Protocol

| Situation | Action |
|-----------|--------|
| Ambiguous specification | Ask Claude for clarification before coding |
| Architectural conflict | Document the conflict, propose options, escalate to Claude |
| Test failure in existing code | Fix it OR document why it's a known issue |
| Deployment failure | Stop, document the error, escalate to Claude |
| Performance regression | Benchmark, document, escalate to Claude |

---

## WORKFLOW.md — AI Engineering Workflow

### Purpose

Define the complete AI engineering workflow for CodePilot, from idea to release. This document governs how Claude and Codex collaborate across the full development lifecycle.

### Agent Responsibilities Summary

#### Claude Responsibilities
- Product thinking and requirement definition
- Architecture design and trade-off evaluation
- QA strategy and test plan review
- PR review and diff review
- Release audit and quality gate enforcement
- Harness evolution and maintenance

#### Codex Responsibilities
- Implementation of features and bug fixes
- Refactoring and code improvement
- Testing (unit, integration, smoke)
- Deployment execution
- Documentation updates (code-level and Harness synchronization)

### Standard Development Loop

```
User (Idea / Requirement)
    ↓
Claude Analysis (scope, feasibility, architecture impact)
    ↓
Claude Specification (acceptance criteria, technical design)
    ↓
Codex Implementation (code, tests, docs)
    ↓
Codex Validation (lint, test suite, build check)
    ↓
Claude Diff Review (correctness, security, architecture alignment)
    ↓
Codex Fixes (address review feedback)
    ↓
Claude Release Audit (quality gates, harness update check)
    ↓
Codex Deployment (tag, deploy, verify)
```

### Workflow Definitions

#### Feature Workflow

**Trigger:** User requests a new feature or enhancement.

```
1. User describes the feature
2. Claude analyzes scope and architecture impact
3. Claude writes specification:
   - Acceptance criteria
   - Technical design (modules affected, data flow changes)
   - Test plan (what tests are needed)
   - Harness impact (which .harness/ files need updating)
4. Claude reviews specification with user (if significant)
5. Codex implements:
   - Write source code
   - Write tests
   - Update documentation
   - Run quality checks (lint, test, build)
6. Codex marks implementation complete
7. Claude reviews the diff:
   - Correctness
   - Security
   - Architecture alignment
   - Test coverage
8. Claude approves or requests changes
9. Codex addresses feedback (loop to step 7 if needed)
10. Claude runs release audit
11. Codex commits and deploys
```

#### Bug Fix Workflow

**Trigger:** User reports a bug or Claude/Codex discovers a defect.

```
1. Bug is identified and described
2. Claude (or Codex) reproduces the bug
3. Codex (or Claude) writes a regression test that fails
4. Codex (or Claude) implements the fix
5. Regression test passes
6. Claude reviews the fix (diff review)
7. Codex commits
8. If critical: proceed to Hotfix Workflow
```

**Note:** For isolated bugs, Claude may directly implement the fix and regression test (see CLAUDE.md §6).

#### Hotfix Workflow

**Trigger:** Critical bug in production requiring immediate fix.

```
1. Codex creates a fix branch from the release tag
2. Codex (or Claude) writes a regression test that reproduces the bug
3. Codex (or Claude) implements the fix
4. Claude reviews the fix and test
5. Codex merges and tags as v<X.Y.Z> (patch)
6. Codex deploys and verifies:
   - Health check passes
   - Smoke test passes
   - No regressions
7. Claude updates DECISION_LOG.md with hotfix rationale
8. Claude runs Harness Update Checklist
```

#### Release Workflow

**Trigger:** All planned features for a version are complete.

```
1. Claude runs pre-release audit:
   - All features complete and tested
   - ROADMAP.md updated
   - ARCHITECTURE.md updated (if needed)
   - PROJECT_CONTEXT.md updated
   - DECISION_LOG.md has entries for key decisions
   - TESTING.md test count is accurate
2. Claude verifies all quality gates pass
3. Codex runs release preparation:
   - All hard gates pass (tests, lint, build, docker, smoke)
   - Version bump in runtime.txt (if needed)
   - .env.example updated (if needed)
   - DEPLOYMENT.md updated (if needed)
4. Codex commits: release(v<X.Y>): <summary>
5. Codex tags: v<X.Y>
6. Codex deploys to target platforms
7. Codex verifies deployment:
   - Health check returns 200
   - Smoke test passes against deployed environment
8. Claude records release decision in DECISION_LOG.md
9. Claude reviews and updates ROADMAP.md
10. Claude runs Harness Update Checklist
```

#### Emergency Bug Workflow

**Trigger:** Production system is down or severely degraded.

```
1. Identify the failure (health check, smoke test, user report)
2. Claude and Codex collaborate in real-time:
   - Codex diagnoses the issue
   - Claude validates the diagnosis
3. Codex (or Claude) implements minimal fix
4. Claude approves (expedited review)
5. Codex deploys immediately
6. Codex verifies recovery
7. Claude records incident in DECISION_LOG.md
8. Claude schedules proper fix if the minimal fix was a workaround
```

### Workflow Rules

1. **No silent skips.** Every step must be executed or explicitly documented as skipped with rationale.
2. **Review is mandatory.** No code reaches production without Claude's review (even expedited in emergencies).
3. **Tests before code.** Regression tests are written before or alongside the fix, never after.
4. **Harness stays current.** The Harness Update Checklist runs after every release and after significant changes.
5. **Escalation is explicit.** When Codex encounters ambiguity, the escalation must be documented.

### Cross-References

- Role definitions: `CLAUDE.md` (Claude), `AGENTS.md` (Codex)
- Quality gates: `RELEASE_RULES.md`
- Test strategy: `TESTING.md`
- Decision recording: `DECISION_LOG.md`
- Harness updates: `HARNESS_UPDATE_CHECKLIST.md`
- Audit protection: `HARNESS_AUDIT_RULES.md`

---

## TESTING.md — Testing Strategy

### Test Pyramid

```
         ┌──────────┐
         │  Smoke   │  1 test — full end-to-end pipeline
         │  (PS1)   │  runs against live backend + local git server
         ├──────────┤
         │Integration│  8 tests — API layer via httpx.AsyncClient
         │ (pytest)  │  tests real HTTP request/response cycle
         ├──────────┤
         │  Unit     │  32 tests — isolated module tests
         │ (pytest)  │  mocked dependencies, fast execution
         └──────────┘
```

### Current Coverage: 44 Tests

#### Unit Tests (32 tests, 5 files)

| File | Tests | Covers |
|------|-------|--------|
| `test_clone_service.py` | 7 | Git clone, URL validation, retry logic, dumb HTTP fallback, cleanup, readonly files |
| `test_python_parser.py` | 8 | Parse valid/invalid/empty files, file discovery, large files, ignored dirs, max_files, entrypoint priority |
| `test_report_generator.py` | 8 | Generation, mock mode, malformed normalization, missing/extra sections, prompt budget, section ordering |
| `test_review_store.py` | 5 | DB init, WAL mode, CRUD, error storage, report preservation |
| `test_review_task_runner.py` | 4 | Submit, successful run, clone failure, status progression |

#### Integration Tests (8 tests, 1 file)

| File | Tests | Covers |
|------|-------|--------|
| `test_reviews_api.py` | 8 | POST create, invalid payload, GET query, missing task, export, export conflict, failed review with error |

#### Smoke Test (1 test, PowerShell)

| File | Covers |
|------|--------|
| `smoke-backend.ps1` | Full pipeline: start backend → local git server → create review → poll to completion → verify export sections |

### Test Configuration

| Setting | Value | File |
|---------|-------|------|
| Test runner | pytest 8.3.4 | `backend/requirements-dev.txt` |
| Test paths | `["tests"]` | `pyproject.toml` |
| Linter | ruff 0.8.4 | `backend/requirements-dev.txt` |
| Line length | 120 | `pyproject.toml` |
| Target | Python 3.11 | `pyproject.toml` |

### Test Conventions

#### Naming

```
test_<module>_<action>_<condition>.py
```

#### Structure (Arrange-Act-Assert)

```python
def test_clone_service_retries_on_transient_error(tmp_path):
    # Arrange
    service = CloneService(workspace_root=tmp_path)
    # Act
    result = service.clone("https://github.com/example/repo.git")
    # Assert
    assert result.success is True
```

#### Mocking Rules

1. **Always mock external I/O** — no real git clones, no real LLM calls, no real network in unit tests.
2. **Use `USE_MOCK_LLM=true`** for integration tests — the mock client returns deterministic output.
3. **SQLite tests use in-memory DBs** — `:memory:` or `tmp_path` fixtures.
4. **Filesystem tests use `tmp_path`** — never write to the real project directory.

### Quality Gates

| Gate | Threshold | Enforcement |
|------|-----------|-------------|
| Unit tests | 100% pass | CI blocks merge |
| Integration tests | 100% pass | CI blocks merge |
| Ruff lint | 0 warnings | CI blocks merge |
| TypeScript build | 0 errors | CI blocks merge |
| Smoke test | Pass | Manual before release |

### Test Execution Commands

```bash
# All tests
cd backend && python -m pytest tests/ -v

# Unit tests only
cd backend && python -m pytest tests/unit/ -v

# Integration tests only
cd backend && python -m pytest tests/integration/ -v

# Lint
cd backend && python -m ruff check .

# Frontend build check
cd frontend && npm run build

# Smoke test (Windows)
powershell -File scripts/smoke-backend.ps1
```

### Test Debt (Known Gaps)

| Gap | Priority | Notes |
|-----|----------|-------|
| Frontend component tests | Medium | No React testing library setup yet |
| E2E browser tests | Low | Would require Playwright/Cypress |
| LLM client tests (real API) | Low | Requires API key; mock mode covers logic |
| Performance/load tests | Low | Not critical for MVP |
| Parser tests for non-Python | N/A | Only Python supported currently |

---

## RELEASE_RULES.md — Release Rules

### Release Lifecycle

```
Design → Implement → Test → Review → Approve → Tag → Deploy → Verify → Close
  │         │         │       │        │        │       │         │       │
 Claude   Codex     Codex   Claude   Claude   Codex   Codex    Codex   Claude
```

### Version Numbering

**Format:** `v<MAJOR>.<MINOR>.<PATCH>`

| Component | When to Increment |
|-----------|------------------|
| MAJOR | Breaking changes, new architecture, fundamental redesign |
| MINOR | New features, significant improvements, new deployment targets |
| PATCH | Bug fixes, documentation, config tweaks, dependency updates |

**Current version:** V1.1

### Release Quality Gates

#### Hard Gates (Must Pass)

| Gate | Command | Threshold |
|------|---------|-----------|
| Unit tests | `pytest tests/unit/ -v` | 100% pass |
| Integration tests | `pytest tests/integration/ -v` | 100% pass |
| Ruff lint | `ruff check backend/` | 0 warnings |
| TypeScript build | `cd frontend && npm run build` | 0 errors |
| Docker build | `docker-compose build` | 0 errors |
| Smoke test | `scripts/smoke-backend.ps1` | Full pipeline pass |

#### Soft Gates (Should Pass)

| Gate | Threshold | Exception Process |
|------|-----------|-------------------|
| New code has tests | 100% coverage of new code | Document gap in `DECISION_LOG.md` |
| Documentation updated | All user-facing changes documented | Document gap in `DECISION_LOG.md` |
| No new security warnings | 0 new findings | Document risk in `DECISION_LOG.md` |

### Release Checklist

#### Pre-Release (Claude)

- [ ] All features for this release are complete and tested
- [ ] `ROADMAP.md` updated — completed items marked, new items added
- [ ] `ARCHITECTURE.md` updated if architecture changed
- [ ] `PROJECT_CONTEXT.md` updated with new version info
- [ ] `DECISION_LOG.md` has entries for all key decisions this release
- [ ] `TESTING.md` test count is accurate
- [ ] All quality gates pass

#### Release (Codex)

- [ ] All hard gates pass (see above)
- [ ] Version bump in `runtime.txt` if Python version changed
- [ ] `.env.example` updated if new env vars added
- [ ] `DEPLOYMENT.md` updated if deployment procedure changed
- [ ] Commit message: `release(v<X.Y>): <summary>`
- [ ] Git tag: `v<X.Y>`

#### Post-Release (Codex)

- [ ] Deployment verified on target platforms
- [ ] Health check endpoint returns 200
- [ ] Smoke test passes against deployed environment
- [ ] `DEPLOYMENT_REPORT.md` updated with validation results

#### Post-Release (Claude)

- [ ] `DECISION_LOG.md` entry for release decision
- [ ] `ROADMAP.md` reviewed and updated
- [ ] Harness Update Checklist executed

### Hotfix Process

1. Codex creates a fix branch from the release tag
2. Codex writes a regression test that reproduces the bug
3. Codex implements the fix
4. Claude reviews the fix and test
5. Codex merges and tags as `v<X.Y.Z>` (patch)
6. Codex deploys and verifies
7. Claude updates `DECISION_LOG.md` with hotfix rationale

### Rollback Rules

| Scenario | Action |
|----------|--------|
| Health check fails after deploy | Immediate rollback, investigate |
| Smoke test fails after deploy | Immediate rollback, investigate |
| Performance regression > 50% | Rollback, investigate, schedule fix |
| Data corruption detected | Rollback, restore from backup, investigate |
| Security vulnerability found | Rollback immediately, patch, re-deploy |

---

## ARCHITECTURE.md — Architecture

### System Overview

CodePilot is a **modular monolith** — a single repository containing a FastAPI backend and a Next.js frontend, deployed as two independent services.

```
┌─────────────────────────────────────────────────────────────────┐
│                        User's Browser                           │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Next.js Frontend (Vercel)                                │  │
│  │  ┌─────────┐  ┌──────────┐  ┌──────────────────────────┐ │  │
│  │  │  Form   │→ │  Polling │→ │  Report Renderer         │ │  │
│  │  │ (URL)   │  │ (2s)     │  │  (4 sections as Cards)   │ │  │
│  │  └─────────┘  └──────────┘  └──────────────────────────┘ │  │
│  └────────────────────────┬──────────────────────────────────┘  │
└───────────────────────────┼─────────────────────────────────────┘
                            │ HTTP
┌───────────────────────────┼─────────────────────────────────────┐
│                    FastAPI Backend (Render)                      │
│  ┌────────────────────────▼──────────────────────────────────┐  │
│  │  API Layer (api/reviews.py)                               │  │
│  │  POST /api/reviews  → submit task                         │  │
│  │  GET  /api/reviews/{id} → poll status                     │  │
│  │  GET  /api/reviews/{id}/export → download report          │  │
│  └────────────────────────┬──────────────────────────────────┘  │
│  ┌────────────────────────▼──────────────────────────────────┐  │
│  │  Task Runner (tasks/runner.py)                            │  │
│  │  ThreadPoolExecutor(max_workers=2)                        │  │
│  │  Status: pending→cloning→parsing→summarizing→reviewing    │  │
│  │          →completed | failed                              │  │
│  └────────────────────────┬──────────────────────────────────┘  │
│  ┌────────────┬───────────┼───────────┬──────────────────────┐  │
│  │ Clone      │ Parser    │ Indexer   │ Report Generator     │  │
│  │ Service    │ (tree-    │ (builds   │ (prompt + normalize) │  │
│  │ (git w/    │  sitter + │  context) │                      │  │
│  │  retry)    │  AST)     │           │                      │  │
│  └────────────┴───────────┴───────────┴──────────┬───────────┘  │
│  ┌───────────────────────────────────────────────▼───────────┐  │
│  │  LLM Client (llm/client.py)                              │  │
│  │  MockLLMClient ←→ OpenAICompatibleClient                 │  │
│  └───────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Storage (storage/sqlite.py)                              │  │
│  │  SQLite WAL mode, thread-safe via Lock                    │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Module Map

#### Backend (`backend/`)

| Module | File | Responsibility | Dependencies |
|--------|------|---------------|--------------|
| Entry | `main.py` | FastAPI app creation, CORS, router mounting, `/health` | FastAPI, uvicorn |
| API | `api/reviews.py` | HTTP routes for review CRUD + export | models, tasks |
| Config | `core/config.py` | Pydantic Settings, env loading, singleton | pydantic-settings |
| Models | `models/review.py` | `ReviewStatus`, `ReviewRequest`, `ReviewResponse`, `CodeFileSummary`, `RepositoryContext` | pydantic |
| LLM | `llm/client.py` | `MockLLMClient` (deterministic), `OpenAICompatibleClient` (httpx) | httpx |
| Parser | `parsers/python_parser.py` | tree-sitter parse, AST fallback, file discovery with importance ranking | tree-sitter |
| Reviewer | `reviewers/report_generator.py` | Prompt building from context, 4-section normalization, token budget enforcement | llm.client |
| Clone | `services/clone_service.py` | Git shallow clone, 3x retry, Windows-compatible cleanup | subprocess |
| Indexer | `services/indexer.py` | `RepositoryIndexer` → `RepositoryContext` from parsed files | parsers |
| Storage | `storage/sqlite.py` | `ReviewStore` — WAL mode, busy timeout, thread-safe CRUD | sqlite3 |
| Tasks | `tasks/runner.py` | `ReviewTaskRunner` — ThreadPoolExecutor, status lifecycle, workspace cleanup | all services |

#### Frontend (`frontend/`)

| Path | Responsibility |
|------|---------------|
| `app/page.tsx` | Single-page app: form → poll → render report |
| `app/layout.tsx` | Root layout with metadata |
| `app/globals.css` | HSL CSS variables, Tailwind directives |
| `components/ui/button.tsx` | shadcn/ui Button with cva variants |
| `components/ui/card.tsx` | shadcn/ui Card |
| `components/ui/input.tsx` | shadcn/ui Input |
| `lib/utils.ts` | `cn()` utility (clsx + tailwind-merge) |

### Data Flow

#### Review Pipeline

```
1. User submits GitHub URL
   ↓
2. POST /api/reviews → ReviewTaskRunner.submit()
   ↓
3. Background thread spawned
   ↓
4. Clone: git clone --depth=1 (with 3x retry)
   ↓
5. Parse: tree-sitter extracts classes/functions/imports/docstrings
   ↓
6. Index: Build RepositoryContext (file summaries + metadata)
   ↓
7. Review: Build token-budgeted prompt → LLM call → normalize to 4 sections
   ↓
8. Store: Save report to SQLite
   ↓
9. Cleanup: Delete cloned workspace
```

#### Status Lifecycle

```
pending → cloning → parsing → summarizing → reviewing → completed
                                                    ↘ failed
```

### Design Decisions

#### 1. Modular Monolith over Microservices

**Decision:** Single repository with clearly separated modules, not separate services.

**Rationale:**
- MVP stage — microservices add deployment complexity without benefit
- Single developer — simpler to reason about and debug
- SQLite doesn't support concurrent writes from multiple processes
- Can decompose later when scale demands it

#### 2. Context Engineering over Raw Code

**Decision:** Never send raw source code to the LLM. Extract structured summaries first.

**Rationale:**
- Token budget is limited (5000 words default)
- Raw code is noisy — imports, boilerplate, comments waste tokens
- Structured summaries (classes, functions, imports) give the LLM better signal
- tree-sitter provides reliable parsing without executing the code

#### 3. Report Normalization

**Decision:** Always produce exactly 4 sections, regardless of LLM output.

**Rationale:**
- LLMs are non-deterministic — output format varies
- Users expect consistent, predictable reports
- Missing sections get default content; extra sections are stripped
- Section ordering is enforced

#### 4. Mock Mode as Default

**Decision:** `USE_MOCK_LLM=true` is the default. Real LLM requires explicit configuration.

**Rationale:**
- Enables full end-to-end testing without API credentials
- Deterministic output for CI/CD
- Lower barrier to entry for new developers
- Mock output is still structured and realistic

#### 5. Windows-First Development

**Decision:** All dev scripts are PowerShell. CI runs on Windows.

**Rationale:**
- Primary developer uses Windows
- PowerShell is cross-platform (works on Linux/macOS too)
- CI matches the development environment
- Docker handles production Linux compatibility

#### 6. SQLite over PostgreSQL

**Decision:** Use SQLite with WAL mode instead of a full database server.

**Rationale:**
- Zero infrastructure — no separate database service
- WAL mode handles concurrent reads safely
- Thread-safe via explicit Lock
- Sufficient for single-instance deployment
- Can migrate to PostgreSQL when multi-instance is needed

### Constraints & Invariants

| Constraint | Value | Rationale |
|-----------|-------|-----------|
| Max files analyzed | 300 | Token budget and processing time |
| Max file size | 200KB | Avoid parsing massive generated files |
| Prompt token budget | 5000 words | LLM context window and cost |
| Task workers | 2 | Free-tier memory limits |
| Clone depth | 1 (shallow) | Speed and disk space |
| Review sections | 4 (fixed) | Consistent user experience |
| Python version | 3.11.11 | Pinned for reproducibility |
| Node version | 20 | LTS, Alpine for Docker |

### Future Architecture Considerations

| Area | Current | Future Option |
|------|---------|---------------|
| Task queue | In-process ThreadPoolExecutor | Celery / Redis for distributed workers |
| Database | SQLite WAL | PostgreSQL for multi-instance |
| LLM | Single client | Multi-model routing, fallback chains |
| Parser | Python-only tree-sitter | Language-agnostic parser registry |
| Code graph | None (placeholder) | Call graphs, dependency analysis |
| Agent orchestration | None (placeholder) | Multi-agent review with specialized roles |

### Multi-Agent Architecture Readiness

The current architecture is designed to scale into a multi-agent system. The following design choices support this evolution:

#### Current Agent Model

```
User → Claude (architect/QA) → Codex (implementer) → Deployment
```

#### Future Agent Model

```
User → Claude (orchestrator)
           ├── Codex (implementation)
           ├── Security Agent (vulnerability scanning)
           ├── Performance Agent (profiling, optimization)
           ├── Style Agent (formatting, conventions)
           ├── Architecture Agent (structural analysis)
           └── MCP Agents (IDE integration, real-time analysis)
```

#### Design Decisions Supporting Multi-Agent

1. **Modular monolith** — Clean module boundaries make it easy to assign agents to specific modules
2. **Context engineering** — Structured summaries (not raw code) are agent-friendly input
3. **Mock mode** — Deterministic testing enables agent validation without API costs
4. **SQLite storage** — Simple persistence layer that agents can read/write without coordination
5. **Task runner pattern** — Background task execution model extends naturally to agent task queues

#### Placeholder Directories

| Directory | Future Purpose | Agent Type |
|-----------|---------------|------------|
| `agents/` | Multi-agent review orchestration | Claude-coordinated specialist agents |
| `graph/` | Code graph / dependency analysis | Architecture Agent, Impact Analysis Agent |
| `mcp/` | Model Context Protocol integration | IDE agents, real-time analysis agents |

#### Agent Interface Contract (Future)

When agents are introduced, each agent must:
- Accept structured input (RepositoryContext, not raw code)
- Return structured output (findings with severity, location, rationale)
- Respect token budgets (max prompt size per agent)
- Support mock mode for testing
- Log actions to a shared audit trail

---

## DECISION_LOG.md — Decision Log

> All significant architectural, technical, and process decisions are recorded here.
> Format: `DECISION-NNN` — one entry per decision, newest first.

---

### DECISION-009: V1.1 Release — Engineering Hardening

- **Date:** 2026-06-05
- **Type:** Release
- **Status:** Approved
- **Deciders:** Claude (review), Codex (implementation)

**Context:** V1.0 shipped a working MVP but lacked test coverage, deployment automation, and engineering rigor.

**Decision:** Release V1.1 focused on engineering hardening — not new features.

**Changes:**
- Added 44 automated tests (32 unit + 8 integration + smoke)
- Added ruff linting with zero-warning policy
- Added GitHub Actions CI (Windows, Python 3.11, Node 20)
- Added Docker Compose for local development
- Added deployment documentation for Vercel + Render
- Pinned Python runtime to 3.11.11 for Render compatibility

**Rationale:** Test coverage and CI are prerequisites for confident iteration. Ship quality infrastructure before shipping features.

---

### DECISION-008: Deploy Backend on Render (Docker)

- **Date:** 2026-06-05
- **Type:** Deployment
- **Status:** Approved
- **Deciders:** Claude (recommendation), Codex (validation)

**Context:** Backend needs a free-tier hosting platform with Docker support.

**Decision:** Use Render Free Tier with Docker deployment via `Dockerfile.backend`.

**Alternatives Considered:**
1. **Render (Native Python)** — Rejected: runtime pinning issues encountered.
2. **Railway** — Rejected: no free tier as of 2026.
3. **Fly.io** — Rejected: more complex CLI setup, credit card required.

**Rationale:** Render Free supports Docker, auto-deploys from GitHub, and has straightforward configuration. Docker avoids runtime version ambiguity.

---

### DECISION-007: Deploy Frontend on Vercel

- **Date:** 2026-06-05
- **Type:** Deployment
- **Status:** Approved

**Context:** Frontend needs a free-tier hosting platform optimized for Next.js.

**Decision:** Use Vercel Free Tier with automatic GitHub integration.

**Rationale:** Vercel is the creator of Next.js. Zero-config deployment, automatic previews, edge network. The obvious choice.

---

### DECISION-006: Python 3.11.11 Runtime Pinning

- **Date:** 2026-06-05
- **Type:** Technical
- **Status:** Approved

**Context:** Render's native Python buildpack didn't respect `runtime.txt` or `.python-version` consistently, causing deployment failures.

**Decision:** Pin Python to 3.11.11 in three files: `.python-version`, `runtime.txt`, and Dockerfile base image. Switch to Docker deployment to avoid buildpack issues entirely.

**Rationale:** Explicit pinning in multiple locations ensures consistency across local dev, CI, and production. Docker eliminates the buildpack layer of indirection.

---

### DECISION-005: 4-Section Report Format

- **Date:** V1.0
- **Type:** Product
- **Status:** Approved

**Context:** Need a consistent, predictable report format for the code review output.

**Decision:** Always produce exactly 4 sections in this order:
1. Architecture Summary
2. Code Smells
3. Maintainability Issues
4. Refactoring Suggestions

**Rationale:** Consistency builds user trust. The `ReportGenerator` normalizes any LLM output to this exact format — missing sections get defaults, extras are stripped.

---

### DECISION-004: Context Engineering over Raw Code

- **Date:** V1.0
- **Type:** Architecture
- **Status:** Approved

**Context:** Sending raw source code to the LLM wastes tokens and produces noisy reviews.

**Decision:** Use tree-sitter to extract structured summaries (classes, functions, imports, docstrings) and send only these summaries to the LLM within a token budget.

**Rationale:**
- 5000-word budget forces focus on signal over noise
- Structured input produces more structured output
- tree-sitter is reliable and doesn't require code execution
- AST fallback handles syntax errors gracefully

---

### DECISION-003: Mock LLM as Default

- **Date:** V1.0
- **Type:** Technical
- **Status:** Approved

**Context:** Developers should be able to run the full system without API keys.

**Decision:** `USE_MOCK_LLM=true` is the default. The mock client returns a realistic, deterministic 4-section report.

**Rationale:**
- Zero barrier to entry for new contributors
- Deterministic output for CI/CD
- Full pipeline testing without external dependencies
- Mock output still validates the report normalization logic

---

### DECISION-002: SQLite with WAL Mode

- **Date:** V1.0
- **Type:** Architecture
- **Status:** Approved

**Context:** Need persistent storage for review results. PostgreSQL adds infrastructure complexity.

**Decision:** Use SQLite with WAL (Write-Ahead Logging) mode and thread-safe locking.

**Rationale:**
- Zero infrastructure — no separate database service
- WAL mode enables concurrent reads during writes
- Thread-safe via explicit `threading.Lock`
- Single-instance deployment doesn't need PostgreSQL
- Migration path to PostgreSQL is clear when needed

---

### DECISION-001: Windows-First Development

- **Date:** V1.0
- **Type:** Process
- **Status:** Approved

**Context:** Primary developer uses Windows. Need cross-platform tooling.

**Decision:** All dev scripts are PowerShell. CI runs on `windows-latest`. Docker handles production Linux compatibility.

**Rationale:**
- Matches the primary development environment
- PowerShell Core works on Linux/macOS too
- CI environment matches dev environment (reduces "works on my machine" issues)
- Docker Compose abstracts OS differences for production

---

## ROADMAP.md — Roadmap

### Completed

#### V1.0 — Production-Ready MVP ✅
- [x] GitHub repository cloning (public repos)
- [x] Python code parsing with tree-sitter + AST fallback
- [x] Repository context building with token budget
- [x] LLM-powered 4-section review report generation
- [x] Mock mode for deterministic testing
- [x] REST API (POST create, GET poll, GET export)
- [x] Next.js frontend with progress tracking and report rendering
- [x] SQLite storage with WAL mode
- [x] Background task execution

#### V1.1 — Engineering Hardening ✅
- [x] 44 automated tests (unit + integration)
- [x] Ruff linting with zero-warning policy
- [x] GitHub Actions CI (Windows, Python 3.11, Node 20)
- [x] Docker Compose for local development
- [x] Vercel deployment (frontend)
- [x] Render deployment (backend, Docker)
- [x] Deployment documentation
- [x] Python 3.11.11 runtime pinning

#### Harness v1.1 — Workflow Integration ✅
- [x] WORKFLOW.md — Complete AI engineering workflow (feature, bug, hotfix, release, emergency)
- [x] HARNESS_AUDIT_RULES.md — Audit protection with drift detection
- [x] Claude role adjustment — Scoped code modification for bugs/tests/refactors
- [x] Codex harness maintenance rights — May update docs when instructed
- [x] Multi-agent readiness — Architecture and roadmap prepared for future agents
- [x] Trigger matrix expanded — WORKFLOW.md and HARNESS_AUDIT_RULES.md integrated

---

### In Progress

*Nothing currently in progress.*

---

### Planned — V1.2 (Near-Term)

#### Parser Improvements
- [ ] **Parser test coverage** — Dedicated unit tests for edge cases: deeply nested classes, decorators, type aliases, `__all__` exports
- [ ] **File selection heuristics** — Smarter prioritization: entrypoints first, then by import centrality, then alphabetical
- [ ] **Multi-language support foundation** — Abstract parser interface, add JavaScript/TypeScript tree-sitter grammar

#### UI Enhancements
- [ ] **Review history** — List past reviews with timestamps and repo names
- [ ] **Progress details** — Show current file being processed during parsing stage
- [ ] **Report comparison** — Side-by-side view of two reviews for the same repo
- [ ] **Dark mode** — Toggle between light and dark themes

#### Backend Hardening
- [ ] **Request validation** — Stricter URL validation (reject non-GitHub URLs, malformed URLs)
- [ ] **Rate limiting** — Basic rate limiter to prevent abuse
- [ ] **Cancellation support** — Allow users to cancel an in-progress review
- [ ] **Error recovery** — Better error messages for common failures (private repo, network timeout, invalid branch)

---

### Planned — V2.0 (Medium-Term)

#### Multi-Language Support
- [ ] **Language-agnostic parser registry** — Plugin system for adding new language parsers
- [ ] **JavaScript/TypeScript parser** — tree-sitter grammar for JS/TS
- [ ] **Go parser** — tree-sitter grammar for Go
- [ ] **Rust parser** — tree-sitter grammar for Rust
- [ ] **Language detection** — Auto-detect primary language from file extensions

#### Private Repository Support
- [ ] **GitHub OAuth** — Allow users to authenticate with GitHub
- [ ] **Token-based access** — Support personal access tokens for private repos
- [ ] **Webhook integration** — Trigger reviews on push/PR events

#### Enhanced Analysis
- [ ] **Dependency analysis** — Parse import graphs, detect circular dependencies
- [ ] **Code complexity metrics** — Cyclomatic complexity, function length, nesting depth
- [ ] **Security scanning** — Basic vulnerability pattern detection
- [ ] **Test coverage correlation** — Map review findings to test coverage gaps

---

### Planned — V3.0 (Long-Term)

#### Multi-Agent Review
- [ ] **Specialized review agents** — Separate agents for security, performance, style, architecture
- [ ] **Agent orchestration** — Coordinator agent that routes findings to specialists
- [ ] **Consensus mechanism** — Multiple agents vote on severity and recommendations
- [ ] **Learning from feedback** — Agents improve based on user acceptance/rejection of suggestions
- [ ] **Agent interface contract** — Standardized input/output format for all agents (see ARCHITECTURE.md § Multi-Agent Readiness)

#### Code Graph
- [ ] **Call graph construction** — Map function call relationships
- [ ] **Dependency graph** — Visualize module/package dependencies
- [ ] **Impact analysis** — "If I change X, what else is affected?"
- [ ] **Graph-based context** — Use code graph to improve LLM context selection

#### MCP Integration
- [ ] **MCP server** — Expose CodePilot as an MCP tool for IDE integration
- [ ] **IDE plugins** — VS Code, JetBrains extensions
- [ ] **Real-time analysis** — Analyze code as the user types
- [ ] **MCP agent protocol** — Agents communicate via MCP for distributed analysis

#### Enterprise Features
- [ ] **Team workspaces** — Shared review history and settings
- [ ] **Custom review rules** — User-defined review criteria and checklists
- [ ] **CI/CD integration** — GitHub Actions / GitLab CI review gates
- [ ] **Reporting dashboard** — Trends, metrics, team performance

#### Multi-Agent Harness Evolution
- [ ] **Agent role definitions** — Formal role specs for each agent type in `.harness/`
- [ ] **Agent workflow integration** — WORKFLOW.md extended with multi-agent flows
- [ ] **Agent quality gates** — Per-agent validation rules and acceptance criteria
- [ ] **Agent audit trail** — Shared logging for all agent actions

---

### Technical Debt

| Item | Priority | Effort | Notes |
|------|----------|--------|-------|
| Frontend component tests | Medium | 1 day | Need React Testing Library setup |
| Extract LLM client interface | Medium | 0.5 day | Enable multi-model routing |
| Add `py.typed` marker | Low | 0.5 day | Better IDE support for backend |
| Consistent error response format | Medium | 1 day | Standardize API error shapes |
| Database migration system | Low | 1 day | Needed if schema evolves |
| Frontend state management | Medium | 2 days | Current single-component approach won't scale |

---

### Ideas Parking Lot

*Unsorted ideas that need further evaluation:*

- Streaming report generation (SSE) — show sections as they're generated
- Report caching — skip LLM call if same repo+commit was reviewed recently
- Batch reviews — analyze multiple repos in one session
- Report templates — customizable review focus areas
- Export to PDF — in addition to Markdown
- CLI mode — `codepilot analyze <repo-url>` from the terminal
- GitHub App — automated reviews on pull requests
- LLM cost tracking — show token usage and estimated cost per review

---

## HARNESS_UPDATE_CHECKLIST.md — Harness Evolution System

### Trigger Matrix

When a change occurs, consult this matrix to determine which documents require review and potential updates.

#### By Change Type

| Change Type | GOAL | PROJECT_CONTEXT | CLAUDE | AGENTS | WORKFLOW | TESTING | RELEASE_RULES | ARCHITECTURE | DECISION_LOG | ROADMAP | AUDIT_RULES |
|-------------|------|-----------------|--------|--------|----------|---------|---------------|--------------|--------------|---------|-------------|
| New feature implemented | — | ✅ | — | — | ✅ | ✅ | — | ✅* | ✅ | ✅ | — |
| Bug fix | — | — | — | — | — | ✅† | — | — | ✅§ | — | — |
| Architecture change | — | ✅ | — | — | ✅ | ✅ | — | ✅ | ✅ | — | ✅ |
| New dependency added | — | ✅ | — | — | — | — | — | ✅ | ✅ | — | — |
| Dependency removed | — | ✅ | — | — | — | ✅ | — | ✅ | ✅ | — | — |
| Deployment change | — | ✅ | — | — | ✅ | ✅ | ✅ | — | ✅ | — | — |
| New env variable | — | ✅ | — | — | — | — | — | — | ✅ | — | — |
| API endpoint change | — | ✅ | — | — | ✅ | ✅ | — | ✅ | ✅ | — | — |
| New test file | — | — | — | — | — | ✅ | — | — | — | — | — |
| Version release | — | ✅ | — | — | ✅ | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| Technology swap | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | ✅ | ✅ |
| Process change | — | — | ✅ | ✅ | ✅ | — | ✅ | — | ✅ | — | — |
| New placeholder dir | — | ✅ | — | — | — | — | — | ✅ | — | ✅ | — |
| Python version bump | — | ✅ | — | — | — | ✅ | ✅ | ✅ | ✅ | — | — |
| Node version bump | — | ✅ | — | — | — | ✅ | — | ✅ | ✅ | — | — |
| New agent type | — | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | ✅ | ✅ |
| Agent workflow change | — | — | ✅ | ✅ | ✅ | — | — | ✅ | ✅ | — | — |

**Legend:**
- ✅ = Must review and update if relevant
- ✅* = Update only if the feature changes the architecture
- ✅† = Update if a regression test is added
- ✅§ = Always add a decision log entry for bug fixes
- — = No update needed

### Update Workflow

#### Step 1: Classify the Change

Before making any harness update, classify the change:

```
┌─────────────────────────────────────────────────┐
│ What changed?                                    │
├─────────────────────────────────────────────────┤
│ □ Source code (backend/frontend/scripts)         │
│ □ Configuration (env, docker, CI)                │
│ □ Dependencies (requirements.txt, package.json)  │
│ □ Documentation (README, docs/)                  │
│ □ Tests (tests/)                                 │
│ □ Deployment (Dockerfile, platform config)       │
│ □ Project structure (new dirs, reorganization)   │
└─────────────────────────────────────────────────┘
```

#### Step 2: Run the Trigger Matrix

Look up each classified change in the matrix above. Collect the union of all documents that need review.

#### Step 3: Review Each Document

For each document flagged by the matrix:

1. **Read** the current document content
2. **Compare** against the actual project state
3. **Update** if the document is stale, incomplete, or inaccurate
4. **Skip** if the document is already current (but document the check)

#### Step 4: Verify Cross-References

After updating any document, verify that cross-references remain valid:

- `ROADMAP.md` items reference correct versions
- `DECISION_LOG.md` references match `ARCHITECTURE.md` descriptions
- `TESTING.md` test counts match actual test files
- `PROJECT_CONTEXT.md` version matches latest release tag
- `RELEASE_RULES.md` quality gates match actual CI configuration

#### Step 5: Record the Update

If any document was updated, add an entry to `DECISION_LOG.md` (unless the change is purely editorial).

### Self-Improvement Workflow

The harness system itself evolves. After every 3 releases, or when a harness document proves consistently stale, Claude must:

#### Quarterly Review

1. **Audit accuracy** — Read each `.harness/` file and verify against the actual project
2. **Identify gaps** — What decisions were made but not logged? What architecture changes are undocumented?
3. **Evaluate triggers** — Are there change types missing from the trigger matrix?
4. **Check redundancy** — Are any documents saying the same thing? Can they be consolidated?
5. **Assess usefulness** — Which documents are actually referenced during development? Which are ignored?

#### Evolution Rules

| Signal | Action |
|--------|--------|
| A document is never updated | Evaluate if it's needed; merge into another or remove |
| A change type is missing from the matrix | Add it with the correct trigger pattern |
| A document duplicates another | Consolidate into a single source of truth |
| A document is too long | Split into focused sub-documents |
| A document is too vague | Add concrete examples, commands, and thresholds |
| New team member joins | Review all docs for implicit knowledge that should be explicit |

### Document Maintenance Schedule

| Document | Review Frequency | Owner |
|----------|-----------------|-------|
| `GOAL.md` | Every major release | Claude |
| `PROJECT_CONTEXT.md` | Every release | Claude or Codex |
| `CLAUDE.md` | Quarterly | Claude |
| `AGENTS.md` | Quarterly | Claude |
| `WORKFLOW.md` | Every release with process changes | Claude |
| `TESTING.md` | Every release | Claude (review), Codex (update counts) |
| `RELEASE_RULES.md` | Every release | Claude |
| `ARCHITECTURE.md` | Every release with structural changes | Claude or Codex |
| `DECISION_LOG.md` | Every decision (continuous) | Claude |
| `ROADMAP.md` | Every release | Claude or Codex |
| `HARNESS_UPDATE_CHECKLIST.md` | Quarterly | Claude |
| `HARNESS_AUDIT_RULES.md` | Quarterly | Claude |

### Quick Reference: "I just did X, what do I update?"

| I just... | Update these |
|-----------|-------------|
| Added a new backend module | `PROJECT_CONTEXT.md`, `ARCHITECTURE.md`, `DECISION_LOG.md`, `TESTING.md` |
| Added a new API endpoint | `PROJECT_CONTEXT.md`, `ARCHITECTURE.md`, `TESTING.md`, `DECISION_LOG.md`, `WORKFLOW.md` (if new workflow step) |
| Released a new version | `PROJECT_CONTEXT.md`, `TESTING.md`, `RELEASE_RULES.md`, `DECISION_LOG.md`, `ROADMAP.md` |
| Changed deployment platform | `PROJECT_CONTEXT.md`, `RELEASE_RULES.md`, `DECISION_LOG.md`, `WORKFLOW.md` |
| Added a new env variable | `PROJECT_CONTEXT.md`, `DECISION_LOG.md` |
| Swapped a technology | `PROJECT_CONTEXT.md`, `ARCHITECTURE.md`, `DECISION_LOG.md`, `ROADMAP.md` + review `CLAUDE.md`, `AGENTS.md`, `WORKFLOW.md` |
| Added tests | `TESTING.md` (update counts) |
| Fixed a bug | `DECISION_LOG.md` (if significant) |
| Added a placeholder directory | `PROJECT_CONTEXT.md`, `ARCHITECTURE.md`, `ROADMAP.md` |
| Changed Python/Node version | `PROJECT_CONTEXT.md`, `ARCHITECTURE.md`, `RELEASE_RULES.md`, `DECISION_LOG.md` |
| Changed agent roles | `CLAUDE.md`, `AGENTS.md`, `WORKFLOW.md`, `DECISION_LOG.md` |
| Added a new agent type | `ARCHITECTURE.md`, `ROADMAP.md`, `WORKFLOW.md`, `DECISION_LOG.md` |
| Detected Harness drift | Run `HARNESS_AUDIT_RULES.md` audit, generate `HARNESS_AUDIT_REPORT.md` |

---

## HARNESS_AUDIT_RULES.md — Audit Protection

### Purpose

Ensure the Harness system never blindly copies outdated data. The repository is the source of truth; Harness documents must reflect reality, not assumptions.

### Core Principle

**Repository reality always wins over outdated documentation.**

Before any Harness update, the auditor must compare the Harness document against the actual repository state. If there is a mismatch, the repository state is correct and the document must be updated.

### Audit Protocol

#### Before Any Harness Update

1. **Compare** the Harness document against the actual repository state
2. **Identify** all mismatches between documentation and reality
3. **Document** each mismatch with:
   - What the Harness says (stale claim)
   - What the repository shows (actual state)
   - Severity: `critical` (blocks decisions), `minor` (cosmetic), `informational` (nice to fix)
4. **Update** the document to match reality
5. **Record** significant drift in `DECISION_LOG.md`

#### What to Check

| Document | Compare Against |
|----------|----------------|
| `PROJECT_CONTEXT.md` | `package.json`, `requirements.txt`, `.env.example`, `runtime.txt`, git tags |
| `ARCHITECTURE.md` | Actual module structure in `backend/`, `frontend/`, file contents |
| `TESTING.md` | Actual test files in `tests/`, test counts from `pytest --collect-only` |
| `RELEASE_RULES.md` | `.github/workflows/ci.yml`, actual quality gate commands |
| `ROADMAP.md` | Git log, completed features in codebase |
| `DECISION_LOG.md` | All of the above — are decisions still reflected in reality? |

### Drift Detection

**Drift** occurs when a Harness document makes a claim that is no longer true.

Examples:
- `TESTING.md` says 44 tests but `pytest --collect-only` shows 52
- `PROJECT_CONTEXT.md` lists Python 3.11 but `runtime.txt` says 3.12
- `ARCHITECTURE.md` describes a module that was removed
- `ROADMAP.md` marks a feature as planned but it's already implemented

#### Severity Classification

| Severity | Definition | Action |
|----------|-----------|--------|
| `critical` | Document would cause a wrong decision (e.g., wrong test count in release gate) | Fix immediately, record in `DECISION_LOG.md` |
| `minor` | Document is inaccurate but wouldn't cause a wrong decision | Fix in next Harness update cycle |
| `informational` | Cosmetic or stylistic inconsistency | Fix when convenient |

### HARNESS_AUDIT_REPORT.md

Generate `HARNESS_AUDIT_REPORT.md` whenever significant drift is detected.

#### Report Format

```markdown
# Harness Audit Report

> Date: YYYY-MM-DD
> Auditor: Claude | Codex
> Trigger: <what triggered this audit>

## Summary

- Documents audited: N
- Mismatches found: N
- Critical: N
- Minor: N
- Informational: N

## Findings

### [Document Name]

| Claim | Reality | Severity | Action |
|-------|---------|----------|--------|
| "44 tests" | 52 tests found | critical | Update TESTING.md |
| "Python 3.11" | runtime.txt says 3.12 | critical | Update PROJECT_CONTEXT.md |

## Resolution

- [ ] Finding 1: <description> — <resolution>
- [ ] Finding 2: <description> — <resolution>

## Post-Audit

- [ ] All critical findings resolved
- [ ] DECISION_LOG.md updated (if applicable)
- [ ] Cross-references verified
```

### Audit Triggers

An audit should be run when:

1. **Before any Harness update** — always compare first
2. **After a release** — verify all documents reflect the new state
3. **After a major refactor** — architecture and module docs may be stale
4. **When a document feels wrong** — trust the instinct, verify against code
5. **Quarterly** — as part of the Harness self-improvement cycle

### Audit Rules

1. **Never blindly trust the document.** Always verify against the repository.
2. **Never blindly trust the repository.** Check that the code actually works (run tests).
3. **Document all mismatches.** Even if you fix them immediately.
4. **Critical drift blocks Harness updates.** Fix critical issues before updating other documents.
5. **Audit reports are disposable.** They don't need to persist after resolution; they're working documents.

### Cross-References

- Update workflow: `HARNESS_UPDATE_CHECKLIST.md`
- Decision recording: `DECISION_LOG.md`
- Quarterly review: `HARNESS_UPDATE_CHECKLIST.md` § Self-Improvement Workflow
