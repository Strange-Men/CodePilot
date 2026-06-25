# CodePilot

**AI Code Review & Refactor Agent for Large Repositories**

CodePilot clones public GitHub repositories, analyzes source files, builds structured context, and generates actionable four-section review reports with evidence-backed findings. It runs a multi-agent pipeline that produces architecture summaries, code smells, maintainability issues, and refactoring suggestions — all with `[E1]`/`[E2]` evidence references traceable to specific source locations.

---

## Live Demo

| Component | URL |
|-----------|-----|
| **Frontend** | [https://code-pilot-red.vercel.app](https://code-pilot-red.vercel.app) |
| **Backend API** | `https://codepilot-i189.onrender.com` |
| **Health Check** | [https://codepilot-i189.onrender.com/health](https://codepilot-i189.onrender.com/health) |

**Recommended for demo:** Use **Mock mode** (the default). It is deterministic, requires no API key, and produces stable bilingual output. Real LLM mode is optional and depends on provider availability.

> **Note:** The Render free tier has ephemeral storage — review history is lost after a container restart. This is expected for a demo deployment.

---

## What CodePilot Does

CodePilot is an end-to-end AI code review agent. Given a public GitHub repository URL, it:

1. **Clones** the repository into a local workspace
2. **Parses** source files using tree-sitter (Python, JavaScript, TypeScript)
3. **Builds** structured context — no raw source code is sent to the LLM
4. **Runs** four parallel specialist agents (Architecture, CodeSmell, Maintainability, Refactor)
5. **Composes** a four-section review report with executive summary and action plan
6. **Displays** findings with `[E1]`/`[E2]` evidence references linked to source locations
7. **Exports** the full report as Markdown with a self-contained evidence appendix

---

## Core Features

- **Repository Intelligence** — tree-sitter parsing, AST extraction, and structured context building for Python, JavaScript, and TypeScript
- **Multi-Agent Review** — parallel specialist agents produce structured findings with severity, category, and evidence links
- **Evidence System** — every finding links to `[E1]`/`[E2]` evidence references with file paths and line numbers; raw IDs are never exposed
- **Bilingual Output** — global zh/en language switch with localStorage persistence; all reports, findings, UI labels, and error messages follow the active language
- **Markdown Export** — one-click export of the full review report with evidence appendix
- **Mock Demo Mode** — deterministic, credential-free demo path that runs out of the box
- **Real LLM Mode** — optional MiMo, Doubao, or DeepSeek provider for production use

---

## Architecture Overview

```
┌──────────────────────────┐         ┌──────────────────────────┐
│   Vercel (Frontend)      │         │   Render (Backend)       │
│   Next.js 15 + React 19  │────────▶│   FastAPI + SQLite       │
│   TypeScript + Tailwind   │  HTTPS  │   tree-sitter parser     │
│   code-pilot-red.vercel.app│        │   codepilot-*.onrender.com│
└──────────────────────────┘         └──────────────────────────┘
```

**Pipeline:**

```
GitHub URL → Clone → Parse (tree-sitter) → Build Context → Multi-Agent Review → Compose Report → Display + Export
                                                    ↓
                                        Architecture Agent
                                        CodeSmell Agent
                                        Maintainability Agent
                                        Refactor Agent
                                                    ↓
                                        Structured Findings + Evidence Map → [E1]/[E2] References
```

Each agent receives structured context (not raw source code) and returns bilingual findings with severity, category, and evidence links. The report composer merges agent outputs into a four-section report with executive summary, action plan, and self-contained evidence appendix.

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15.5, React 19, TypeScript 5.7, Tailwind CSS 3.4 |
| Backend | FastAPI, Python 3.11, SQLite (WAL), in-process ThreadPoolExecutor |
| Parser | tree-sitter with AST fallback (Python, JS, TS) |
| LLM | OpenAI-compatible chat completions or deterministic mock mode |
| Hosting | Vercel (frontend) + Render (backend) |
| CI | GitHub Actions on windows-latest (ruff + pytest + npm build) |

---

## Online Deployment Configuration

### Vercel (Frontend)

| Setting | Value |
|---------|-------|
| Framework Preset | Next.js |
| Root Directory | `frontend` |
| Build Command | `npm run build` |
| Environment Variable | `NEXT_PUBLIC_API_BASE=https://codepilot-i189.onrender.com` |

The `NEXT_PUBLIC_API_BASE` variable must be set before the build runs. Redeploy after changing it.

### Render (Backend)

| Setting | Value |
|---------|-------|
| Runtime | Docker |
| Dockerfile Path | `./Dockerfile.backend` |
| Instance Type | Free |

Required environment variables:

```text
USE_MOCK_LLM=true
DATABASE_PATH=/app/backend/data/codepilot.db
WORKSPACE_PATH=/app/backend/workspace
REPORTS_PATH=/app/reports
CORS_ALLOW_ORIGINS=https://code-pilot-red.vercel.app
MAX_FILES=300
MAX_FILE_SIZE_BYTES=204800
```

### Mock Mode (Default)

Mock mode is enabled with `USE_MOCK_LLM=true`. No API key is needed. The `MockLLMClient` returns pre-built bilingual findings deterministically. This is the stable demo path.

### Real LLM Mode (Optional)

To use a real LLM provider, set:

```text
USE_MOCK_LLM=false
ENABLE_REAL_LLM=true
REAL_LLM_PROVIDER=mimo
```

The frontend sends only the selected provider. API keys stay in the backend `.env`; the frontend never stores provider API keys. The default provider is `mimo`.

For MiMo:

```text
MIMO_API_KEY=your-key
MIMO_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
MIMO_MODEL_NAME=mimo-v2.5-pro
```

For Doubao:

```text
DOUBAO_API_KEY=your-key
DOUBAO_BASE_URL=your-openai-compatible-base-url
DOUBAO_MODEL_NAME=your-model
```

For DeepSeek:

```text
DEEPSEEK_API_KEY=your-key
DEEPSEEK_BASE_URL=your-openai-compatible-base-url
DEEPSEEK_MODEL_NAME=your-model
```

Real LLM mode supports MiMo, Doubao, and DeepSeek through backend OpenAI-compatible configuration. Provider availability depends on backend env configuration, network access, and API key validity. Output quality varies by model. MiMo Chinese output may have occasional unnatural wording.

---

## Local Quick Start

For developers who want to run CodePilot locally:

```powershell
git clone https://github.com/Strange-Men/CodePilot.git
cd CodePilot
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\start-demo.ps1
```

Open [http://localhost:3000](http://localhost:3000).

If `conda.exe` is not on PATH, set it before running setup:

```powershell
$env:CODEPILOT_CONDA = "path\to\your\conda.exe"
.\scripts\setup.ps1
```

---

## Demo Flow

1. Open [https://code-pilot-red.vercel.app](https://code-pilot-red.vercel.app)
2. Enter a public GitHub repository URL (e.g. `https://github.com/pallets/flask`)
3. Click **Run Review** — Mock mode is the default and requires no API key
4. View the structured report with executive summary, findings, and evidence
5. Toggle **EN / zh** to switch the full UI and report language
6. Click **Export** to download the report as Markdown
7. Browse findings by severity, category, or agent — each links to `[E1]`/`[E2]` evidence

---

## CLI Workflows

```powershell
python -m backend.cli review https://github.com/owner/repo --output reports/review.md --json-output reports/review.json
python -m backend.cli ci https://github.com/owner/repo --fail-on high --json-output reports/ci.json
python -m backend.cli diff https://github.com/owner/repo --changed-file backend/main.py --output reports/diff.md
```

See [`docs/history/v3/V3_3_WORKFLOWS.md`](docs/history/v3/V3_3_WORKFLOWS.md) for details.

---

## Testing

```powershell
# Backend
pytest                    # 995 tests passed, 1 skipped
ruff check .              # All checks passed

# Frontend
cd frontend
npm test                  # 104 tests passed
npm run build             # Production build succeeds

# Smoke test
.\scripts\smoke-backend.ps1
```

---

## Known Limitations

- **MiMo Chinese output** — may still have occasional unnatural wording in zh reports; mock mode zh is deterministic and stable
- **Ephemeral storage** — free Render/tmp SQLite may lose review history after restart; this is expected for demo deployments
- **Real LLM dependency** — production-quality output requires a working API key and network access to the provider
- **Language support** — analysis is strongest for Python; JavaScript and TypeScript support is functional but less deep
- **No production workflow yet** — GitHub OAuth, PR bot, MCP integration, vector DB, and LangGraph workflows are not implemented
- **Static analysis only** — CodePilot does not execute repository code; it uses heuristic and AST-based analysis
- **File limits** — analyzes at most 300 supported source files, skips files over 200KB

---

## Project Status

**V3.7** — Stable demo release. CI green. 995 backend tests + 104 frontend tests passing. Mock mode is the recommended demo path. Real LLM mode is optional with known provider-dependent limitations.

| Document | Description |
|----------|-------------|
| [V3.7 Release Notes](docs/releases/v3.7/V3.7_RELEASE_NOTES.md) | Highlights, fixes, test results, known limitations |
| [V3.7 Project Closure](docs/releases/v3.7/V3.7_PROJECT_CLOSURE.md) | Full closure report, verification results |
| [Deployment Guide](docs/setup/DEPLOYMENT.md) | Backend/frontend deployment to Render and Vercel |
| [Vercel Deployment](docs/setup/VERCEL_DEPLOYMENT.md) | Frontend deployment to Vercel |
| [Setup Guide](docs/setup/SETUP.md) | Local installation and environment configuration |
| [Architecture](docs/architecture/ARCHITECTURE.md) | System design, module map, data flow |
| [Full Documentation Index](docs/README.md) | All project documentation |

---

## License

This project is for educational and portfolio purposes.
