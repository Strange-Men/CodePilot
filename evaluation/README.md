# CodePilot Evaluation Harness

## Overview

The evaluation harness runs CodePilot's full review pipeline (clone, parse,
index, review) against a curated dataset of 20 public repositories and
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

`evaluation/datasets/repos.json` contains 20 repositories across three dimensions:

- **Size**: small (<50 supported source files), medium (50-200), large (200+)
- **Language**: python, javascript/TypeScript, mixed
- **Health**: healthy (standard layout), problematic (unusual structure)

## Configuration

`evaluation/configs/default.json` defines:
- Per-category runtime expectations
- Per-language parser expectations
- Per-health outcome expectations
- Report output settings

Dataset and language `min_source_files` / `max_source_files` thresholds are enforced in pass/fail logic.

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
- JavaScript and TypeScript repos produce parsed source summaries and controlled outcomes.
- Large repos complete within timeout bounds.

## Dependencies

No additional dependencies beyond the main backend requirements.
The harness uses `USE_MOCK_LLM=true` through local settings.
Network access is required to clone public GitHub repositories.

## V3.4 Deterministic Report Quality

V3.4 also includes a local, network-free report quality suite:

```powershell
python -m evaluation.report_quality
```

It uses synthetic Flask-like, test-heavy, and circular-dependency signals with validated structured findings. The suite
checks classification, production-first recommendations, readable cycles, agent visibility, actionable next steps,
evidence grounding, bounded output, and snippet leakage. It does not call a real LLM.
