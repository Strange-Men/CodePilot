# CodePilot | AI Code Review and Repository Understanding System

中文版: [README.md](README.md)

Static analysis + structured context + evidence binding for reviewable AI-generated repository reports.

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi)
![Pydantic](https://img.shields.io/badge/Pydantic-Data%20Validation-E92063?logo=pydantic)
![SQLite](https://img.shields.io/badge/SQLite-Persistence-003B57?logo=sqlite)
![Next.js](https://img.shields.io/badge/Next.js-15-000000?logo=nextdotjs)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-Strict-3178C6?logo=typescript)
![Tailwind CSS](https://img.shields.io/badge/Tailwind%20CSS-UI-06B6D4?logo=tailwindcss)
![Mock](https://img.shields.io/badge/Mock-Default-orange)
![Docker](https://img.shields.io/badge/Docker-Local%20Run-2496ED?logo=docker)
![Render](https://img.shields.io/badge/Render-Backend-46E3B7?logo=render)
![Vercel](https://img.shields.io/badge/Vercel-Frontend-000000?logo=vercel)

## 🎯 Project Background: Why Build It? (Situation)

Understanding and reviewing small-to-medium GitHub repositories often runs into three practical problems:

- Manual repository reading is time-consuming, experience-dependent, and hard to keep consistent.
- Asking a general-purpose LLM directly often misses complete repository context, leading to generic suggestions with weak traceability.
- Traditional static analysis tools focus on syntax, style, and security checks, but usually do not produce architecture-level understanding reports.

CodePilot targets small-to-medium Python repositories. It follows a “static facts first, LLM explanation second” approach: repository files, symbols, dependencies, and size metrics are extracted into structured context before the model generates an evidence-backed code understanding and review report.

## ✨ Positioning and Core Capabilities (Task)

CodePilot is an AI code review MVP for small-to-medium GitHub repositories, with Python as the current priority. Given a public repository URL, the system reads the repository statically and produces a four-section report:

- Architecture overview
- Code smells
- Maintainability analysis
- Refactoring suggestions

Core capabilities:

- Pre-LLM static parsing and noise reduction to reduce model input size.
- Structured evidence binding so suggestions can be traced to files, functions, classes, dependencies, and metrics.
- `ReportContract` as a unified report schema that absorbs LLM output variation.
- Mock / Real LLM modes are decoupled, making development, testing, and CI reproducible.
- Provider interfaces make the model layer pluggable; the project currently supports a Mock Provider and OpenAI-compatible Real LLM Providers.
- SQLite stores task state and historical reports for frontend polling and display.

Current non-goals:

- Large monorepos are outside the current scope.
- Full coverage across all programming languages is not a current target.
- User repository code is not executed; analysis is static only.
- CodePilot does not perform automatic fixes.
- CodePilot is not packaged as a full commercial code review platform.

## 🏗️ Architecture and Core Implementation (Action)

End-to-end pipeline:

```text
GitHub URL
→ Repository clone (static read)
→ File filtering / static parsing
→ Structured context building
→ Mock / Real LLM report generation
→ ReportContract validation
→ SQLite persistence
→ Frontend presentation
```

### 1. Upfront Engineering Noise Reduction

CodePilot does not send the entire raw repository directly to the model. It first reduces engineering noise before LLM generation:

- Filters low-value content such as `.git`, `__pycache__`, `.venv`, `dist`, and `build`.
- Keeps source files, configuration files, and README so the model can still understand repository structure.
- Uses Python AST, with a tree-sitter extension-ready parsing path, to extract functions, classes, imports, dependencies, and file-scale metrics.
- Replaces raw-code direct prompting with structured context, reducing noise while preserving locatable engineering facts.

### 2. Report Quality Control

Report generation is constrained by a schema instead of being free-form prose:

- The report always uses four sections: architecture overview, code smells, maintainability analysis, and refactoring suggestions.
- `ReportContract` standardizes the report structure and reduces the impact of LLM output variation on the frontend and stored history.
- Evidence fields bind each finding to file paths, functions, classes, dependencies, and metrics.
- The goal is to make reports reviewable, not to produce a long subjective assessment without traceable evidence.

### 3. Engineering Stability

The system separates real model calls from local engineering verification:

- Mock LLM is used for development, testing, and CI with reproducible output.
- Real LLM is used for actual report generation validation.
- Provider interfaces isolate the model invocation layer, making it possible to switch between MiMo, Doubao, DeepSeek, and other OpenAI-compatible providers.
- Tasks are recorded by phase, so failures can be located to clone, parsing, LLM, or report composition stages.
- `pytest` / `ruff` / `audit_harness` cover tests, static checks, and full-chain validation.

## 🛠️ Tech Stack

| Layer | Stack | Notes |
|---|---|---|
| Backend | FastAPI 0.115.6 + Pydantic 2.10.4 + Uvicorn 0.34.0 | Structured API, parameter validation, async service entry point |
| Frontend | Next.js 15.5.19 + React 19.0.0 + TypeScript 5.7.2 + Tailwind CSS 3.4.17 | Review workspace, task state, evidence display, and Markdown rendering |
| Persistence | SQLite (Python stdlib, WAL mode) | Task state and historical report persistence |
| Parsing | Python AST + tree-sitter 0.24.0 / tree-sitter-language-pack 0.7.0 | Python-first, with a path for multi-language expansion |
| Token Counting | tiktoken 0.13.0 | Unified token estimation |
| LLM | Mock Provider + OpenAI-compatible Real LLM Provider | Mock by default; Real LLM can be configured for MiMo / Doubao / DeepSeek |
| Deployment | Docker Compose local run; Render backend and Vercel frontend docs | See `docker-compose.yml`, `Dockerfile.*`, and `docs/setup/` |
| Quality | pytest + ruff + audit_harness + GitHub Actions | Tests, static checks, full-chain audit, and CI |

## 📊 Quantified Results (Result)

### Engineering Noise Reduction

- Benchmark repositories: 3 public Python repositories.
- Repository size: 60-79 Python source files, close to or above the early 50-file boundary.
- Average file noise reduction: 49.1%.
  - Method: uses `git ls-files` tracked native business files as the baseline, excluding `.git`, dependency directories, virtual environments, and other non-business content.
- Average structured-context token compression: 96.8%.
  - Method: compares raw source-code tokens and structured-context tokens over the same valid source scope, using tiktoken estimation.

### Real LLM Single-Repository Validation

- Validation repository: httpx.
- Baseline input tokens: 137417.
- CodePilot input tokens: 15212.
- Input size reduction: about 8.85x, close to 9x.
- Real LLM call input token compression: 88.7%.
- CodePilot evidence binding rate: 100%.
- General LLM direct-output baseline evidence binding rate: 0%.
- Evidence binding improvement: 100 percentage points.

Notes:

- This is a qualitative single-repository validation on httpx, not a large-scale statistical conclusion.
- Only input tokens are counted here; output tokens are excluded, so this must not be described as total cost reduction.
- Evidence binding rate is measured under v1.0 rules and does not mean the report is absolutely correct.

### Engineering Quality

- `pytest`: 1000 passed, 1 skipped.
- `ruff`: 0 issues.
- `audit_harness`: full-chain validation passed.
- Mock-mode repository review success rate: 100%.

| Validation Dimension | Result | Method |
|---|---:|---|
| Average file noise reduction | 49.1% | 3 benchmark repos, `git ls-files` business-file baseline |
| Structured-context token compression | 96.8% | Same valid source scope: raw source vs structured context |
| httpx real LLM input token compression | 88.7% | Single-repo real call, input tokens only |
| Evidence binding rate | 100% vs 0% | httpx single repo, CodePilot vs raw-code direct prompting |
| pytest | 1000 passed, 1 skipped | Native test output |
| ruff | 0 issues | Static check |
| audit_harness | passed | Full-chain audit validation |

## 🚀 Quick Start

### Windows PowerShell Script Startup

The repository includes Windows PowerShell scripts that create the `codepilot` conda environment, install dependencies, and start both services:

```powershell
git clone https://github.com/Strange-Men/CodePilot.git
cd CodePilot
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\start-demo.ps1
```

After startup:

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend: [http://localhost:8000](http://localhost:8000)
- Health Check: [http://localhost:8000/health](http://localhost:8000/health)

If `conda.exe` is not on PATH:

```powershell
$env:CODEPILOT_CONDA = "path\to\your\conda.exe"
.\scripts\setup.ps1
```

### Manual Startup

```bash
# Backend
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev -- --port 3000
```

On Windows PowerShell, you can explicitly set the backend URL before starting the frontend:

```powershell
$env:NEXT_PUBLIC_API_BASE = "http://localhost:8000"
npm run dev -- --port 3000
```

### Docker Local Run

```powershell
cp .env.example .env
docker compose up --build
```

Open:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Health: http://localhost:8000/health

Default mode is Mock LLM — no real API key required. To use a real model, configure the provider API key in `.env`. See [Docker local run docs](docs/DOCKER.md) for details.

Stop and clean up:

```bash
docker compose down        # stop containers
docker compose down -v     # stop and remove SQLite/workspace/reports volumes
```

### Tests and Quality Checks

```bash
# Backend tests and checks
python -m pytest tests/ -q
ruff check .
python scripts/audit_harness.py

# Frontend tests and build
cd frontend
npm test
npm run build
```

## 📁 Project Structure

```text
CodePilot/
├── backend/          # FastAPI backend, parsers, LLM providers, review pipeline
├── frontend/         # Next.js / React / TypeScript frontend
├── contracts/        # Report section contract files
├── docs/             # Architecture, setup, evaluation and deployment docs
├── evaluation/       # Evaluation datasets, metrics and comparison scripts
├── reports/          # Generated metric and validation outputs
├── scripts/          # Setup, startup, audit and metric scripts
├── tests/            # Unit, integration, regression and metric tests
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
├── README.md
└── README.en.md
```

## 🛣️ Roadmap

- Strengthen report evidence chains: bind code snippets, impact scope, and refactoring priority.
- Improve real LLM stability: schema validation, automatic retries, and fallback paths.
- Harden the external-repository safety sandbox: directory isolation, file count / file size limits, and timeout controls.
- Expand multi-language support, starting with JavaScript / TypeScript on tree-sitter.
- Build a productized evaluation system: evaluation dashboard.

## ⚠️ Current Limitations

- Python repositories are the current priority.
- User repository code is not executed; analysis is static only.
- Real LLM validation has only completed one end-to-end run on httpx.
- The baseline comparison is a qualitative single-repository validation, not a large-scale statistical conclusion.
- This is an MVP, not a full commercial code review platform.
- JavaScript / TypeScript parsing entry points and tests exist, but analysis depth is currently weaker than Python.
- SQLite review history depends on the actual storage configuration; temporary environments such as Render Free may lose history after restarts.

## 📄 License

MIT License
