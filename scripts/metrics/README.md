# CodePilot Quant Metrics Runner

This runner produces reproducible V3.7 quant metrics without changing CodePilot core logic.

## Commands

```powershell
python scripts/metrics/run_quant_metrics.py --benchmark evaluation/datasets/repos.json --mode both --max-repos 3 --output reports/quant_metrics_v3_7
python scripts/metrics/run_quant_metrics.py --benchmark evaluation/datasets/repos.json --mode real --max-repos 1 --output reports/quant_metrics_v3_7
python scripts/metrics/run_quant_metrics.py --benchmark evaluation/datasets/repos.json --mode baseline --max-repos 1 --output reports/quant_metrics_v3_7
python scripts/metrics/run_quant_metrics.py --repo-url <url> --mode both --output reports/quant_metrics_v3_7
python scripts/metrics/run_quant_metrics.py --repo-path <path> --mode scan-only --output reports/quant_metrics_v3_7
```

`both` means scan + Mock CodePilot review + Real LLM CodePilot review + one small-repo direct LLM baseline.

## Outputs

The default output directory is `reports/quant_metrics_v3_7/`:

- `codepilot_quant_metrics.json`
- `codepilot_quant_metrics.md`
- `mock_review_outputs/`
- `real_llm_review_outputs/`
- `baseline_direct_llm_outputs/`
- `raw_logs/`

Repo/mode artifacts use `{repo_name}_{mode}.md/json`, for example `flask_mock.md` or `flask_baseline_direct_llm.json`.

## Notes

- Successful existing repo+mode artifacts are skipped unless `--rerun` is passed.
- Real LLM failures are recorded as failures and never replaced with Mock output.
- Token counts use `tiktoken` when installed; otherwise CodePilot's existing fallback counter is reported.
- Baseline is intentionally limited to the first selected repo to avoid unnecessary Real LLM spend.
