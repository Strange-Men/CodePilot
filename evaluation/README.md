# CodePilot Evaluation Harness

## Overview

The evaluation harness runs CodePilot's full review pipeline (clone, parse,
index, review) against a curated dataset of 18 public repositories and
produces structured metrics and reports.

## Quick Start

```powershell
# Run full evaluation
python evaluation/run_eval.py

# Run with persistent work directory
python evaluation/run_eval.py --work-dir .eval-work --keep-work-dir

# Filter by category
python evaluation/run_eval.py --filter-size small
python evaluation/run_eval.py --filter-language python
python evaluation/run_eval.py --filter-id flask

# Legacy mode (flat repo list)
python evaluation/run_eval.py --repos evaluation/repos.txt
```

## Dataset

`evaluation/datasets/repos.json` contains 18 repositories across three dimensions:

- **Size**: small (<50 .py files), medium (50-200), large (200+)
- **Language**: python, javascript (0 .py files), mixed
- **Health**: healthy (standard layout), problematic (unusual structure)

## Configuration

`evaluation/configs/default.json` defines:
- Per-category runtime expectations
- Per-language parser expectations
- Per-health outcome expectations
- Report output settings

## Metrics

The harness computes:

| Metric | Description |
|--------|-------------|
| Review Success Rate | Repos reaching pass state / total repos |
| Clone Failure Rate | Failures attributable to clone stage |
| Parse Failure Rate | Unexpected parse outcomes (e.g., 0 files for python repos) |
| Report Completeness | Completed repos with all 4 sections / total completed |
| Average Runtime | Mean wall-clock time per repo |

Metrics are aggregated by size, language, and health category.

## Reports

Reports are written to `evaluation/reports/` (gitignored):
- JSON: machine-readable with full detail
- Markdown: human-readable summary tables

## What It Verifies

- The review task reaches `completed` or a controlled `failed` state.
- Completed reviews include all four required report sections.
- Failed reviews include non-empty, user-facing error text.
- Failed reviews do not expose Python internals (tracebacks, IndexError).
- JavaScript repos produce controlled outcomes (no crashes).
- Large repos complete within timeout bounds.

## Dependencies

No additional dependencies beyond the main backend requirements.
The harness uses `USE_MOCK_LLM=true` through local settings.
Network access is required to clone public GitHub repositories.
