# CodePilot - Decision Log

> Harness version: v1.1
> Last updated: 2026-06-05
> Format: newest first, one significant decision per entry.

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

### Rationale

Docker avoids platform buildpack ambiguity and lets the project pin Python consistently.

## DECISION-007: Deploy Frontend on Vercel

- Date: 2026-06-05
- Type: Deployment
- Status: Approved

### Context

The frontend is a Next.js app and needs free-tier hosting with simple Git integration.

### Decision

Use Vercel Free Tier for frontend deployment.

### Rationale

Vercel is optimized for Next.js and supports straightforward Git-connected deployment.

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
