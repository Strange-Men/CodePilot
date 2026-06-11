# CodePilot Evaluation Harness

## Overview

The V3.5 evaluation harness runs CodePilot's existing review pipeline against deterministic local fixtures or optional
public repositories. It measures pipeline completion, report quality, grounding, agent visibility, token usage, cost
metadata, and latency. Mock mode is the credential-free default.

## Quick Start

```powershell
# Run the deterministic local fixture
python -m evaluation.run_eval --dataset evaluation/datasets/v3_5_fixtures.json

# Run with persistent work directory
python -m evaluation.run_eval --work-dir .eval-work --keep-work-dir

# Filter by category
python -m evaluation.run_eval --filter-size small
python -m evaluation.run_eval --filter-language python
python -m evaluation.run_eval --filter-id flask

# Legacy mode (flat repo list)
python -m evaluation.run_eval --repos evaluation/repos.txt

# Optional real LLM mode
python -m evaluation.run_eval --real-llm --provider openai --model gpt-4o-mini --max-repos 1

# Compare with the latest compatible run
python -m evaluation.run_eval --dataset evaluation/datasets/v3_5_fixtures.json --compare-previous
```

## Dataset

`evaluation/datasets/v3_5_fixtures.json` is network-free. `evaluation/datasets/repos.json` contains 20 optional public
repositories across three dimensions:

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

## V3.5 Metrics

The harness computes:

| Metric | Description |
|--------|-------------|
| Review Success Rate | Repos reaching pass state / total repos |
| Clone Failure Rate | Failures attributable to clone stage |
| Parse Failure Rate | Unexpected parse outcomes (e.g., 0 files for python repos) |
| Report Completeness | Completed repos with all 4 sections / total completed |
| Average Runtime | Mean wall-clock time per repo |
| Report Quality | Five deterministic dimensions scored from 0-100 |
| Agent Usage | Prompt/completion tokens, LLM calls, and duration when available |
| Estimated Cost | Optional exact-model pricing lookup; unknown pricing remains null |

Metrics are aggregated by size, language, and health category.

## Artifacts

Runs are written to `evaluation/runs/<run-id>/` (gitignored). Each run contains `run.json`, `summary.json`,
`summary.md`, quality and cost summaries, plus per-repository `result.json` and `report.md`. Optional comparison
artifacts are generated with `--compare-previous`.

## What It Verifies

- The review task reaches `completed` or a controlled `failed` state.
- Completed reviews include all four required report sections.
- Failed reviews include non-empty, user-facing error text.
- Failed reviews do not expose Python internals (tracebacks, IndexError).
- JavaScript and TypeScript repos produce parsed source summaries and controlled outcomes.
- Large repos complete within timeout bounds.

## Dependencies

No additional dependencies beyond the main backend requirements. Local fixtures need no network. Public repository
datasets require network access. Real LLM mode requires explicit `--real-llm` and `OPENAI_API_KEY`.

## V3.4 Deterministic Report Quality

V3.4 also includes a local, network-free report quality suite:

```powershell
python -m evaluation.report_quality
```

It uses synthetic Flask-like, test-heavy, and circular-dependency signals with validated structured findings. The suite
checks classification, production-first recommendations, readable cycles, agent visibility, actionable next steps,
evidence grounding, bounded output, and snippet leakage. It does not call a real LLM.

See `docs/V3_5_EVALUATION.md` for the run registry, scoring rubric, pricing format, artifact contract, comparison
rules, and limitations.
