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
![Render](https://img.shields.io/badge/Render-Backend-46E3B7?logo=render)
![Vercel](https://img.shields.io/badge/Vercel-Frontend-000000?logo=vercel)

## 🎯 Project Background: Why Build It? (Situation)

Understanding and reviewing small-to-medium GitHub repositories often runs into three practical problems:

- Manual repository reading is time-consuming, experience-dependent, and hard to keep consistent.
- Asking a general LLM directly often misses complete repository context and produces generic suggestions with weak traceability.
- Traditional static analysis tools focus on syntax, style, and security checks, but usually do not produce architecture-level understanding reports.

CodePilot targets small-to-medium Python repositories. It follows a “static facts first, LLM explanation second” approach: source files, symbols, dependencies, and size metrics are extracted into structured context before the model generates an evidence-backed review report.

## ✨ Positioning and Core Capabilities (Task)

CodePilot is an AI code review MVP for small-to-medium GitHub repositories, with Python as the current priority. Given a public repository URL, it reads the repository statically and produces a four-section report:

- Architecture overview
- Code smells
- Maintainability analysis
- Refactoring suggestions

Core capabilities:

- Pre-LLM static parsing and filtering to reduce noisy input.
- Structured evidence binding so suggestions can be traced back to files, functions, classes, dependencies, and metrics.
- Mock / Real LLM modes separated for reproducible development, testing, CI, and real report generation validation.
- SQLite persistence for task state and historical reports.
- Provider interfaces that isolate model integration, covering Mock and OpenAI-compatible real model configuration.

Current non-goals:

- Not designed for large monorepos.
- No full coverage across all programming languages.
- Does not execute user repository code.
- Does not automatically fix code.
- Not packaged as a commercial code review product.

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

- Filters low-value content such as `.git`, `__pycache__`, `.venv`, `dist`, and `build`.
- Keeps source files, configuration files, README files, and other repository-understanding signals.
- Uses Python AST, with a tree-sitter extension-ready parsing path, to extract functions, classes, imports, dependencies, and file-scale metrics.
- Replaces raw-code prompting with structured context so the model receives less noise while keeping locatable engineering facts.

### 2. Report Quality Control

- Uses a fixed four-section report structure: architecture overview, code smells, maintainability analysis, and refactoring suggestions.
- `ReportContract` provides a unified report schema and absorbs variation in LLM output.
- Evidence fields bind each finding to file paths, functions, classes, dependencies, and metrics.
- The goal is a reviewable report, not a long free-form subjective assessment.

### 3. Engineering Stability

- Mock LLM is used for development, tests, and CI with deterministic output.
- Real LLM is used for validating real report generation.
- Provider interfaces make the model layer pluggable.
- Task state is recorded by phase so failures can be located in clone, parsing, LLM, or report composition stages.
- `pytest`, `ruff`, and `audit_harness` cover tests, static checks, and engineering consistency checks.

## 🛠️ Tech Stack

- Backend: FastAPI 0.115.6 + Pydantic 2.10.4 + Uvicorn 0.34.0
- Frontend: Next.js 15.5.19 + React 19 + TypeScript 5.7 + Tailwind CSS 3.4
- Persistence: SQLite via Python stdlib, with WAL mode
- Parsing: Python AST + tree-sitter / tree-sitter-language-pack
- Token Counting: tiktoken 0.13.0
- LLM: Mock Provider + OpenAI-compatible Real LLM Provider (MiMo / Doubao / DeepSeek configuration)
- Deployment: Locally deployable with Docker; repository docs include Render backend and Vercel frontend deployment configuration
- Quality: pytest + ruff + audit_harness + GitHub Actions

## 📊 Quantified Results (Result)

### Engineering Noise Reduction

- Benchmark repositories: 3 public Python repositories.
- Repository size: 60-79 Python source files, close to or above the early 50-file boundary.
- Average file noise reduction: 49.1%.
  - Method: `git ls-files` tracked business files as the baseline, excluding `.git`, dependency directories, virtual environments, and other non-business content.
- Average structured-context token compression: 96.8%.
  - Method: raw source-code tokens and structured-context tokens are compared over the same valid source scope with the same estimation method.

### Single-Repository Real LLM Validation

- Validation repository: httpx.
- Baseline input tokens: 137417.
- CodePilot input tokens: 15212.
- Input size reduction: about 8.85x, approximately 9x.
- Real LLM call input token compression: 88.7%.
- CodePilot evidence binding rate: 100%.
- Direct general-LLM baseline evidence binding rate: 0%.
- Evidence binding improvement: 100 percentage points.

Notes:

- This is a qualitative single-repository validation on httpx, not a large-scale statistical conclusion.
- Only input tokens are counted here. Output tokens are not included, so this must not be described as total cost reduction.
- Evidence binding rate is measured under v1.0 rules and does not mean the report is absolutely correct.

### Engineering Quality

- `pytest`: 1000 passed, 1 skipped.
- `ruff`: 0 issues.
- `audit_harness`: full-chain validation passed.
- Mock-mode repository review success rate: 100%.

| Validation Dimension | Result | Method |
|---|---:|---|
| Average file noise reduction | 49.1% | 3 benchmark repositories, `git ls-files` business-file baseline |
| Structured-context token compression | 96.8% | Same valid source scope vs structured context |
| httpx real LLM input token compression | 88.7% | Single-repository real call, input tokens only |
| Evidence binding rate | 100% vs 0% | httpx single repository, CodePilot vs raw-code direct prompting |
| pytest | 1000 passed, 1 skipped | Native test output |
| ruff | 0 issues | Static check |

## 🚀 Quick Start

The recommended local path is the repository's PowerShell scripts. They create the `codepilot` conda environment, install backend dependencies, install frontend dependencies, and start both services.

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

Manual startup is also available:

```powershell
# Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements-dev.txt
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# Frontend
cd frontend
npm install
$env:NEXT_PUBLIC_API_BASE = "http://localhost:8000"
npm run dev -- --port 3000
```

Quality checks:

```powershell
python -m pytest tests/ -q
ruff check .
python scripts/audit_harness.py

cd frontend
npm test
npm run build
```

Local Docker run:

```powershell
docker compose up --build
```

## 📁 Project Structure

```text
CodePilot/
├── backend/          # FastAPI backend, parsers, LLM providers, review pipeline
├── frontend/         # Next.js/React/TypeScript frontend
├── contracts/        # Report section contract files
├── docs/             # Architecture, setup, evaluation and release docs
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

- Strengthen report evidence chains: bind snippets, impact scope, and refactoring priority.
- Improve real LLM stability: schema validation, automatic retries, and fallback paths.
- Harden external repository sandboxing: directory isolation, file count / file size limits, and timeout controls.
- Expand multi-language support, starting with JavaScript / TypeScript on tree-sitter.
- Build a more product-oriented evaluation dashboard.

## ⚠️ Current Limitations

- Python repositories are the current priority.
- User repository code is not executed; analysis is static only.
- Real LLM validation has only completed one end-to-end run on httpx.
- The baseline comparison is a qualitative single-repository validation, not a large-scale statistical conclusion.
- This is an MVP, not a commercial code review product.
- JavaScript / TypeScript parsing entry points and tests exist, but analysis depth is currently weaker than Python.
- SQLite review history depends on the actual storage configuration; temporary environments such as Render Free may lose history after restarts.

## 📄 License

MIT License
