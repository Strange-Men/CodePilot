# CodePilot

CodePilot is a repository-intelligence tool for reviewing Python, JavaScript, TypeScript, and mixed GitHub repositories.

Workflow:

`GitHub Repo URL -> Clone Repo -> Parse Source -> Build Review Context -> Generate Review Report -> Display Report -> Export Markdown`

Every report preserves these four compatible sections:

1. Architecture Summary
2. Code Smells
3. Maintainability Issues
4. Refactoring Suggestions

V3.4 engines add a human-readable executive summary, repository and architecture map, agent summary, grouped findings,
action plan, and snippet-free evidence appendix around those sections.

## Quick Start

Run in Windows PowerShell:

```powershell
cd D:\Claude_workfile\CodePilot
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\start-demo.ps1
```

Open [http://localhost:3000](http://localhost:3000).

If `conda.exe` is not on PATH, point CodePilot at it before setup:

```powershell
$env:CODEPILOT_CONDA = "D:\Miniconda3\Scripts\conda.exe"
.\scripts\setup.ps1
```

Run the backend workflow smoke test:

```powershell
.\scripts\smoke-backend.ps1
```

The app runs in mock LLM mode by default. To use a real OpenAI-compatible API, edit `.env`:

```text
USE_MOCK_LLM=false
ENABLE_REAL_LLM=true
OPENAI_API_KEY=your-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

The default review engine is `v3_multi_agent`. Override to use a different engine:

```text
REVIEW_ENGINE=v2
REVIEW_ENGINE=v3_single_agent
REVIEW_ENGINE=v3_multi_agent
```

## Developer Workflows

V3.3 adds CLI, CI, optional MCP, and diff-aware review wrappers around the existing pipeline:

```powershell
python -m backend.cli review https://github.com/owner/repo --output reports/review.md --json-output reports/review.json
python -m backend.cli ci https://github.com/owner/repo --fail-on high --json-output reports/ci.json
python -m backend.cli diff https://github.com/owner/repo --changed-file backend/main.py --output reports/diff.md
```

See `docs/V3_3_WORKFLOWS.md` for details.

V3.4 report design and deterministic quality checks are documented in `docs/V3_4_REPORT_QUALITY.md`.

## Stack

- Frontend: Next.js, TypeScript, Tailwind, shadcn/ui-style components
- Backend: FastAPI, Python 3.11
- Parser: registry-backed Python, JavaScript, and TypeScript analysis
- Storage: SQLite
- LLM: OpenAI-compatible chat completions or mock mode

## Limits

CodePilot uses static, heuristic analysis and does not execute repository code. It analyzes at most 300 supported source files and skips files over 200KB.
