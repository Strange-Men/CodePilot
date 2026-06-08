# CodePilot V3.3 Developer Workflow Integration

V3.3 exposes the existing review pipeline to developer workflows without replacing the engine, storage, report contract, or V2/V3 compatibility paths.

## CLI Review Mode

Run a repository review from the command line:

```powershell
python -m backend.cli review https://github.com/owner/repo `
  --engine v3_multi_agent `
  --output reports/repo-review.md `
  --json-output reports/repo-review.json `
  --mock-llm
```

Inputs:

- `repo_url`: public GitHub HTTPS repository URL.
- `--engine`: `v2`, `v3_single_agent`, or `v3_multi_agent`.
- `--output`: Markdown report path.
- `--json-output`: optional machine-readable summary built from SQLite structured data.
- `--mock-llm` / `--real-llm`: override configured LLM mode.

The command creates a normal review row, runs `ReviewPipeline`, writes the existing Markdown report, and reads structured findings/evidence refs through `ReviewStore`.

## CI Report Mode

CI mode uses the same workflow layer and defaults to non-blocking:

```powershell
python -m backend.cli ci https://github.com/owner/repo `
  --output reports/ci-report.md `
  --json-output reports/ci-summary.json
```

Optional severity gates:

```powershell
python -m backend.cli ci https://github.com/owner/repo --fail-on high
```

`--fail-on none` is the default. Review execution failures still return exit code `1`; finding-based blocking only happens when a severity threshold is requested.

## Diff-Aware Review Mode

Diff mode accepts explicit changed files or a unified diff:

```powershell
python -m backend.cli diff https://github.com/owner/repo `
  --changed-file backend/tasks/pipeline.py `
  --json-output reports/diff-summary.json
```

```powershell
python -m backend.cli diff https://github.com/owner/repo `
  --diff-file change.diff `
  --output reports/diff-review.md
```

When `--engine` is omitted, diff mode uses `v3_multi_agent` so it can reuse V3.2 tiered retrieval. `ReviewScope` limits V3 evidence retrieval to changed files plus dependency-neighbor context. The scope is additive and optional; full-repo review behavior is unchanged.

## MCP Server

`backend.mcp_server` provides optional MCP SDK integration. It registers:

- `analyze_repository`
- `get_review_status`
- `get_review_findings`
- `get_review_report`
- `get_review_evidence`

Run it when the optional MCP SDK is installed:

```powershell
python -m backend.mcp_server --require-sdk
```

The MCP tools call `ReviewWorkflow` and `ReviewStore`; they do not read repository files directly and return persisted evidence references without snippets.

## Compatibility Notes

- `ReviewPipeline`, `ReportResult`, and `ReviewStore` remain the integration boundary.
- `SandboxFilter` remains the only repository file entry point.
- SQLite schema is unchanged.
- `report_markdown` and Markdown export paths are preserved.
- Structured findings and evidence refs are read from existing persisted data.
- Mock LLM mode remains credential-free.
- The MCP SDK is optional and isolated from the default backend requirements.
