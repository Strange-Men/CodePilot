# CodePilot - Decision Log

> Harness version: v1.2
> Last updated: 2026-06-05
> Format: newest first, one significant decision per entry.

## DECISION-017: Automate Harness Drift Detection in CI

- Date: 2026-06-05
- Type: Process / Automation
- Status: Approved
- Deciders: User approval; Codex implementation

### Context

Harness documents (PROJECT_CONTEXT.md, TESTING.md, RELEASE_RULES.md) can drift from repository reality as code evolves. Manual audits are error-prone and happen too infrequently to catch drift before it affects decisions.

### Decision

Add `scripts/audit_harness.py` as a machine-readable audit gate that runs in CI and checks:

- Test count documented vs actual pytest collection.
- Environment variables documented vs used in code.
- CI gates documented vs present in workflow YAML.
- Dependency versions documented vs pinned in requirements/package files.

CI fails on critical drift findings.

### Alternatives Considered

- **Manual-only audits**: Lower cost but drift accumulates silently between Harness updates.
- **LLM-based audit agent**: More flexible but non-deterministic, slow, and expensive for every CI run.
- **YAML/schema validation only**: Would catch structural issues but not semantic drift (wrong version numbers, missing env vars).

### Tradeoffs

- AST-parsing `config.py` and regex-parsing markdown are fragile if file formats change significantly.
- Adds ~2s to CI for pytest collection and file parsing.
- Only checks a defined subset of drift; does not verify architecture claims or API contracts.

### Rationale

Automated detection catches drift at commit time, making the Harness a living document rather than stale documentation. The script is deterministic, fast, and runs on every PR.

## DECISION-016: Add Regression Harness for Production Bug Fixes

- Date: 2026-06-05
- Type: Quality / Process
- Status: Approved
- Deciders: User approval; Codex implementation

### Context

Production bugs that are fixed can return if no test locks the fix. The V1.0 tree-sitter non-ASCII IndexError (Regression-001) demonstrated the need for a formal regression workflow.

### Decision

Create `tests/regressions/` with:

- Numbered test files: `test_regression_<N>_<name>.py`.
- Numbered entries in `.harness/REGRESSION_RULES.md` with root cause and verification evidence.
- Workflow: Bug → Reproduce → Regression Test → Fix → Verify.
- Regressions use local fixtures, not real network or LLM calls.

### Alternatives Considered

- **Inline regression tests in unit test files**: Simpler but regression tests serve a different purpose (lock specific bugs, not validate general behavior) and benefit from separate tracking.
- **Snapshot/golden file testing**: Would catch output changes but not the root cause patterns that regressions target.

### Tradeoffs

- Adds a third test directory alongside `tests/unit` and `tests/integration`.
- Regression entries require manual maintenance in REGRESSION_RULES.md.
- Small local fixtures may not fully reproduce production conditions (documented as acceptable gap).

### Rationale

Separating regression tests from unit tests makes their purpose explicit: they exist to prevent specific historical failures from returning, not to validate general correctness. The numbered registry provides traceability from bug to fix to test.

## DECISION-015: Add Evaluation Harness for Pipeline Validation

- Date: 2026-06-05
- Type: Quality / Infrastructure
- Status: Approved
- Deciders: User approval; Codex implementation

### Context

CodePilot's review pipeline must work across diverse repository shapes (small/large, Python/JS/mixed, healthy/problematic). Manual testing against a few repos does not catch category-specific failures.

### Decision

Create `evaluation/` harness with:

- Structured dataset: `evaluation/datasets/repos.json` with 18 repos across size/language/health dimensions.
- Configuration: `evaluation/configs/default.json` with per-category expectations.
- Metrics: `evaluation/metrics.py` computing success rate, failure rates, report completeness, and average runtime by category.
- Runner: `evaluation/run_eval.py` executing the full pipeline with `USE_MOCK_LLM=true` and producing JSON + Markdown reports.
- Legacy mode: `--repos` flag for backward-compatible flat repo list.

### Alternatives Considered

- **Expand pytest integration tests**: Would keep everything in one framework but 18 real repos are too slow and network-dependent for unit/integration test runs.
- **Manual testing checklist**: Lower automation cost but non-repeatable and does not produce metrics over time.
- **Standalone evaluation service**: More infrastructure but overkill for V1.x single-instance deployment.

### Tradeoffs

- Requires network access to clone public GitHub repos; not runnable in air-gapped environments.
- Mock LLM mode means evaluation tests pipeline mechanics, not LLM output quality.
- 18 repos take significant wall-clock time; not suitable for per-commit CI (reserved for pre-release and manual runs).

### Rationale

The evaluation harness provides repeatable, metrics-driven validation of the full pipeline across repository categories. It catches regressions that unit and integration tests miss because those tests use small fixtures, not real-world repository shapes.

## DECISION-014: Choose tree-sitter for Python Parsing

- Date: V1.0
- Type: Technical
- Status: Approved

### Context

CodePilot needs to extract structural information (classes, functions, imports) from Python files. The parser must handle real-world code including syntax errors and non-ASCII content.

### Decision

Use `tree-sitter` with `tree-sitter-language-pack` as the primary parser, falling back to Python's `ast` module when tree-sitter fails.

### Alternatives Considered

- **ast module only**: Built-in, no dependencies, but fails on syntax errors and does not provide byte-offset precision for error recovery.
- **libcst**: Concrete syntax tree preserves formatting but is heavier and focused on code transformation, not structural extraction.
- **jedi**: Designed for IDE completion, not bulk structural analysis.
- **ANTLR Python grammar**: Powerful but requires grammar maintenance and a Java-like toolchain.

### Tradeoffs

- `tree-sitter` adds a C dependency and `tree-sitter-language-pack` pins grammar versions.
- Byte-offset handling requires careful UTF-8/decoded-string coordination (root cause of Regression-001).
- AST fallback provides graceful degradation but produces less detailed output.

### Rationale

tree-sitter provides fast, error-tolerant parsing with byte-level precision, which is critical for extracting structure from arbitrary public repositories that may contain syntax errors. The AST fallback ensures the pipeline does not crash when tree-sitter cannot parse a file.

## DECISION-013: Use FastAPI as Backend Framework

- Date: V1.0
- Type: Technical
- Status: Approved

### Context

CodePilot needs a Python web framework for its REST API that supports async request handling, Pydantic validation, and straightforward background task integration.

### Decision

Use FastAPI with Uvicorn as the ASGI server.

### Alternatives Considered

- **Flask**: Mature and simple but lacks native async, Pydantic integration, and OpenAPI schema generation.
- **Django**: Full-featured but heavyweight for a four-endpoint API; ORM and admin are unnecessary with SQLite direct access.
- **Litestar**: Modern alternative to FastAPI but smaller ecosystem and less community adoption at decision time.

### Tradeoffs

- FastAPI's async model is partially used; background tasks run in `ThreadPoolExecutor`, not native async.
- Pydantic v2 validation adds a dependency but provides strong request/response contracts.
- OpenAPI auto-documentation is a bonus but not a primary decision driver.

### Rationale

FastAPI provides Pydantic-validated request/response models, automatic OpenAPI docs, and a lightweight footprint that fits a four-endpoint API. The async model is not heavily leveraged but does not impose overhead.

## DECISION-012: Use In-Process ThreadPoolExecutor for Background Tasks

- Date: V1.0
- Type: Architecture
- Status: Approved

### Context

Review tasks (clone, parse, review) take seconds to minutes and must not block the HTTP request thread. The system needs background execution without external infrastructure.

### Decision

Use `ThreadPoolExecutor(max_workers=2)` from Python's standard library, running inside the FastAPI process.

### Alternatives Considered

- **Celery + Redis**: Production-grade task queue but adds two infrastructure dependencies and operational complexity for a single-instance MVP.
- **FastAPI BackgroundTasks**: Runs after response but in the same async loop; long-running tasks would block other requests.
- **asyncio.create_task**: Native async but clone and file I/O are synchronous; would require rewriting all blocking calls.
- **subprocess**: Heavy process-per-task overhead for short-lived work.

### Tradeoffs

- Limited to 2 concurrent reviews; additional submissions queue.
- No task persistence: if the process restarts, in-progress tasks are lost.
- Thread safety requires explicit locking in SQLite store (WAL + busy timeout + thread lock).
- No retry, dead-letter, or priority queue capabilities.

### Rationale

In-process execution is the simplest approach that works for a single-instance MVP. Two workers prevent resource exhaustion from concurrent clones while keeping latency acceptable. The tradeoff is no task durability, which is acceptable because reviews are idempotent and can be resubmitted.

## DECISION-011: Install Harness Engineering System v1.1

- Date: 2026-06-05
- Type: Process / Documentation
- Status: Approved
- Deciders: User approval; Codex implementation

### Context

CodePilot has working product, tests, deployment documentation, and CI, but the repository needs durable governance documents that keep agents aligned on product goals, architecture, quality gates, workflows, and roadmap.

### Decision

Install the Harness Engineering System in:

- Root `CLAUDE.md`.
- `.harness/GOAL.md`.
- `.harness/PROJECT_CONTEXT.md`.
- `.harness/CLAUDE.md`.
- `.harness/AGENTS.md`.
- `.harness/WORKFLOW.md`.
- `.harness/TESTING.md`.
- `.harness/RELEASE_RULES.md`.
- `.harness/ARCHITECTURE.md`.
- `.harness/DECISION_LOG.md`.
- `.harness/ROADMAP.md`.
- `.harness/HARNESS_UPDATE_CHECKLIST.md`.
- `.harness/HARNESS_AUDIT_RULES.md`.
- `docs/workflows/` reference documents.

### Rationale

The Harness makes project intent explicit, reduces drift across AI-assisted sessions, and provides a repeatable process for feature work, bug fixes, releases, audits, and future multi-agent work.

### Consequences

- Harness docs must be reviewed when repository facts change.
- Repository reality wins over stale Harness claims.
- Significant Harness governance changes require a decision log entry.

## DECISION-010: Keep CodePilot as a Modular Monolith

- Date: 2026-06-05
- Type: Architecture
- Status: Approved
- Deciders: Claude design; Codex validation

### Context

CodePilot currently has a single repository with a FastAPI backend, Next.js frontend, shared documentation, tests, scripts, and deployment files. The backend and frontend deploy independently but are developed together.

### Decision

Keep CodePilot as a modular monolith for V1.x.

### Rationale

- One repository keeps API contracts, tests, deployment docs, and Harness state synchronized.
- Current scale does not require microservices.
- SQLite and in-process background tasks fit single-instance deployment.
- Future decomposition remains possible when multi-agent, multi-language, or multi-instance needs justify it.

### Consequences

- Module boundaries inside `backend/` and `frontend/` remain important.
- New feature work should extend existing modules before creating new top-level systems.
- Distributed task queues or databases require a future architecture decision.

## DECISION-009: V1.1 Release - Engineering Hardening

- Date: 2026-06-05
- Type: Release
- Status: Approved
- Deciders: Claude review; Codex implementation

### Context

V1.0 shipped the MVP review pipeline but needed stronger tests, linting, CI, Docker support, and deployment documentation before faster iteration.

### Decision

Release V1.1 as an engineering hardening release rather than a feature release.

### Changes

- 44 collected pytest tests.
- Ruff linting with zero-warning release expectation.
- GitHub Actions CI on `windows-latest`.
- Docker Compose local stack.
- Vercel frontend deployment documentation.
- Render Docker backend deployment documentation.
- Python 3.11.11 runtime pinning.

### Rationale

Quality infrastructure is a prerequisite for reliable product iteration and deployment confidence.

## DECISION-008: Deploy Backend on Render with Docker

- Date: 2026-06-05
- Type: Deployment
- Status: Approved

### Context

The backend needs free-tier hosting with reliable Python runtime behavior and support for the FastAPI service.

### Decision

Use Render Free Tier with Docker deployment via `Dockerfile.backend`.

### Alternatives Considered

- **Railway**: Similar free tier but smaller community and less mature Python support at decision time.
- **Fly.io**: Good Docker support but requires `flyctl` CLI setup and has a more complex deployment model.
- **Heroku**: Familiar but no longer offers a meaningful free tier.
- **AWS/GCP free tier**: More infrastructure complexity for an MVP.

### Tradeoffs

- Free tier has cold starts (~30s) and ephemeral local filesystem (SQLite data lost on redeploy).
- No `render.yaml` IaC; deployment configured in dashboard, not version-controlled.
- Docker build adds CI time but eliminates buildpack version drift.

### Rationale

Docker avoids platform buildpack ambiguity and lets the project pin Python consistently. Render's free tier and Docker support fit the single-instance MVP deployment model.

## DECISION-007: Deploy Frontend on Vercel

- Date: 2026-06-05
- Type: Deployment
- Status: Approved

### Context

The frontend is a Next.js app and needs free-tier hosting with simple Git integration.

### Decision

Use Vercel Free Tier for frontend deployment.

### Alternatives Considered

- **Netlify**: Good for static sites but less optimized for Next.js SSR/ISR features.
- **Cloudflare Pages**: Fast edge deployment but Next.js support was less mature at decision time.
- **Self-hosted on Render**: Would consolidate hosting but Render's Node.js support adds cold-start latency for frontend requests.
- **Docker on any VPS**: Full control but operational overhead for a static/SSR frontend.

### Tradeoffs

- No `vercel.json`; deployment configured in Vercel dashboard, not version-controlled.
- Vercel free tier has bandwidth and build-minute limits.
- Tight coupling to Vercel's Next.js optimization; migration would require testing SSR behavior on another platform.

### Rationale

Vercel is optimized for Next.js and supports straightforward Git-connected deployment. The free tier is sufficient for the MVP frontend, and Vercel's build pipeline handles Next.js-specific optimizations (ISR, image optimization) without configuration.

## DECISION-006: Pin Python Runtime to 3.11.11

- Date: 2026-06-05
- Type: Runtime
- Status: Approved

### Context

Deployment reliability requires consistent Python behavior across local development, CI, and production.

### Decision

Pin Python to 3.11.11 through `.python-version`, `runtime.txt`, and Docker base image choice.

### Rationale

Explicit pinning reduces runtime drift and avoids buildpack ambiguity.

## DECISION-005: Enforce Four-Section Report Format

- Date: V1.0
- Type: Product / UX
- Status: Approved

### Context

LLM output can vary, but the product needs predictable reports and stable frontend rendering.

### Decision

Every report must contain exactly these sections in order:

1. Architecture Summary
2. Code Smells
3. Maintainability Issues
4. Refactoring Suggestions

### Rationale

Stable structure builds user trust and simplifies export/rendering behavior.

## DECISION-004: Use Context Engineering Instead of Raw Code Prompts

- Date: V1.0
- Type: Architecture
- Status: Approved

### Context

Sending raw source code to the LLM wastes context budget and can produce noisy reviews.

### Decision

Parse repositories into structured summaries and send those summaries to the LLM.

### Rationale

Structured context improves signal, respects prompt budgets, and avoids executing untrusted code.

## DECISION-018: Introduce Parser Registry Foundation

- Date: 2026-06-05
- Type: Architecture
- Status: Approved

### Context

The V1 pipeline directly instantiated the Python parser inside task orchestration, which made the parsing boundary concrete and Python-specific.

### Decision

Introduce a parser protocol and registry, register only the existing Python parser, and have the review runner resolve the Python parser through that registry.

### Rationale

This preserves Python behavior, report output, and API contracts while creating a stable extension point for later language support.

## DECISION-019: Decompose Review Pipeline From Runner

- Date: 2026-06-05
- Type: Architecture
- Status: Approved

### Context

ReviewTaskRunner owned task creation, worker scheduling, clone orchestration, parsing, summarization status, report generation, persistence, and workspace cleanup.

### Decision

Keep ReviewTaskRunner as the in-process scheduler and delegate review lifecycle execution to ReviewPipeline.

### Rationale

This reduces coupling in task scheduling code without introducing Redis, Celery, Temporal, or any new infrastructure. The status lifecycle, API behavior, database schema, and cleanup behavior remain unchanged.

## DECISION-003: Use Mock LLM Mode by Default

- Date: V1.0
- Type: Technical
- Status: Approved

### Context

Developers, demos, tests, and CI need the full pipeline to run without API credentials.

### Decision

Set `USE_MOCK_LLM=true` by default.

### Rationale

Mock mode is deterministic, credential-free, and validates the same report normalization and storage path as real LLM mode.

## DECISION-002: Use SQLite with WAL Mode

- Date: V1.0
- Type: Architecture
- Status: Approved

### Context

The MVP needs persistent review storage without operating a database server.

### Decision

Use SQLite with WAL mode, busy timeout, and explicit thread locking.

### Rationale

SQLite is enough for a single-instance MVP and keeps setup simple.

## DECISION-001: Use Windows-First Development Workflows

- Date: V1.0
- Type: Process
- Status: Approved

### Context

The primary development environment is Windows.

### Decision

Use PowerShell scripts and Windows CI while relying on Docker for Linux production compatibility.

### Rationale

Local and CI parity reduces friction, and PowerShell remains usable across platforms where needed.
