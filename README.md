# CodePilot

**AI Code Review & Refactor Agent for Large Repositories**

CodePilot clones public GitHub repositories, analyzes source files, builds structured context, and generates actionable four-section review reports with evidence-backed findings. It runs a multi-agent pipeline that produces architecture summaries, code smells, maintainability issues, and refactoring suggestions — all with `[E1]`/`[E2]` evidence references traceable to specific source locations.

## Core Features

- **Repository Intelligence** — tree-sitter parsing, AST extraction, and structured context building for Python, JavaScript, and TypeScript
- **Multi-Agent Review** — parallel specialist agents (Architecture, CodeSmell, Maintainability, Refactor) produce structured findings
- **Evidence System** — every finding links to `[E1]`/`[E2]` evidence references with file paths and line numbers; raw IDs are never exposed
- **Bilingual Output** — global zh/en language switch with localStorage persistence; all reports, findings, UI labels, and error messages follow the active language
- **Markdown Export** — one-click export of the full review report with evidence appendix
- **Mock Demo Mode** — deterministic, credential-free demo path that runs out of the box
- **Real LLM Mode** — optional MiMo/OpenAI-compatible provider for production use

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15.5, React 19, TypeScript 5.7, Tailwind CSS 3.4 |
| Backend | FastAPI, Python 3.11, SQLite (WAL), in-process ThreadPoolExecutor |
| Parser | tree-sitter with AST fallback (Python, JS, TS) |
| LLM | OpenAI-compatible chat completions or deterministic mock mode |
| CI | GitHub Actions on windows-latest (ruff + pytest + npm build) |

## Architecture

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

## Quick Start

```powershell
cd D:\Claude_workfile\CodePilot
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\start-demo.ps1
```

Open [http://localhost:3000](http://localhost:3000).

If `conda.exe` is not on PATH:

```powershell
$env:CODEPILOT_CONDA = "D:\Miniconda3\Scripts\conda.exe"
.\scripts\setup.ps1
```

## Demo Flow

1. Enter a public GitHub repository URL (e.g. `https://github.com/pallets/flask`)
2. Click **Run Review** — the default mock mode requires no API key
3. View the structured report with executive summary, findings, and evidence
4. Toggle **EN / zh** to switch the full UI and report language
5. Click **Export** to download the report as Markdown
6. Browse findings by severity, category, or agent — each links to `[E1]`/`[E2]` evidence

## Mock Mode vs Real LLM Mode

**Mock mode** (default) is the stable demo path. It uses a deterministic `MockLLMClient` that returns pre-built bilingual findings without any API calls. No credentials needed. Use this for demos, resume review, and development.

**Real LLM mode** uses MiMo or any OpenAI-compatible provider. Edit `.env`:

```text
USE_MOCK_LLM=false
ENABLE_REAL_LLM=true
OPENAI_API_KEY=your-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

For MiMo:

```text
MIMO_API_KEY=your-key
MIMO_BASE_URL=https://api.mimo.ai/v1
MIMO_MODEL=mimo-7b
```

Real LLM mode depends on provider availability, network, and API key validity. Output quality varies by model.

## CLI Workflows

```powershell
python -m backend.cli review https://github.com/owner/repo --output reports/review.md --json-output reports/review.json
python -m backend.cli ci https://github.com/owner/repo --fail-on high --json-output reports/ci.json
python -m backend.cli diff https://github.com/owner/repo --changed-file backend/main.py --output reports/diff.md
```

See `docs/history/v3/V3_3_WORKFLOWS.md` for details.

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

## Known Limitations

- **MiMo Chinese output** — may still have occasional unnatural wording in zh reports; mock mode zh is deterministic and stable
- **Ephemeral storage** — free Render/tmp SQLite may lose review history after restart; this is expected for demo deployments
- **Real LLM dependency** — production-quality output requires a working API key and network access to the provider
- **Language support** — analysis is strongest for Python; JavaScript and TypeScript support is functional but less deep
- **No production workflow yet** — GitHub OAuth, PR bot, MCP integration, vector DB, and LangGraph workflows are not implemented
- **Static analysis only** — CodePilot does not execute repository code; it uses heuristic and AST-based analysis
- **File limits** — analyzes at most 300 supported source files, skips files over 200KB

## Project Status

**V3.7** — Stable demo release. CI green. 995 backend tests + 104 frontend tests passing. Mock mode is the recommended demo path. Real LLM mode is optional with known provider-dependent limitations.

See `docs/releases/v3.7/V3.7_PROJECT_CLOSURE.md` for the full closure report and `docs/releases/v3.7/V3.7_RELEASE_NOTES.md` for release details.

Full documentation index: [`docs/README.md`](docs/README.md)

## License

This project is for educational and portfolio purposes.
