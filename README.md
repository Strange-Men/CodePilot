# CodePilot

CodePilot is a repository-intelligence MVP for reviewing Python, JavaScript, TypeScript, and mixed GitHub repositories.

Workflow:

`GitHub Repo URL -> Clone Repo -> Parse Source -> Build Review Context -> Generate Review Report -> Display Report -> Export Markdown`

The review report contains exactly:

1. Architecture Summary
2. Code Smells
3. Maintainability Issues
4. Refactoring Suggestions

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

## Stack

- Frontend: Next.js, TypeScript, Tailwind, shadcn/ui-style components
- Backend: FastAPI, Python 3.11
- Parser: registry-backed Python, JavaScript, and TypeScript analysis
- Storage: SQLite
- LLM: OpenAI-compatible chat completions or mock mode

## Limits

CodePilot uses static, heuristic analysis and does not execute repository code. It analyzes at most 300 supported source files and skips files over 200KB.
