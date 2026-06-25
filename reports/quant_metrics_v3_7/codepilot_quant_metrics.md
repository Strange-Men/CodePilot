# CodePilot Quant Metrics Report

## Metadata
- Generated at: 2026-06-25T07:33:33.400761+00:00
- Mode: both
- Token method: tiktoken

## Benchmark
| Repo | Source | Python Files | Eligible Files | Threshold |
| --- | --- | ---: | ---: | --- |
| httpx | first_clone | 60 | 60 | upper_limit |
| click | first_clone | 63 | 63 | upper_limit |
| uvicorn | first_clone | 79 | 79 | upper_limit |

## Noise
| Repo | Git tracked | Eligible | Reduction |
| --- | ---: | ---: | ---: |
| httpx | 125 | 60 | 52.0% |
| click | 150 | 63 | 58.0% |
| uvicorn | 126 | 79 | 37.3% |

## Token
| Repo | Source Tokens | Context Tokens | Compression |
| --- | ---: | ---: | ---: |
| httpx | 134046 | 4157 | 96.9% |
| click | 206719 | 4470 | 97.8% |
| uvicorn | 114429 | 4937 | 95.7% |

## Code Understanding
| Repo | AST Success | Symbol Coverage | Functions | Classes | Dependency Edges |
| --- | ---: | ---: | ---: | ---: | ---: |
| httpx | 100.0% | 93.3% | 857 | 99 | 110 |
| click | 100.0% | 96.8% | 908 | 160 | 61 |
| uvicorn | 100.0% | 84.8% | 658 | 93 | 205 |

## Agent Quality
| Repo | Mode | Success | Findings | Evidence Binding | Generic Rate | Sections |
| --- | --- | --- | ---: | ---: | ---: | --- |
| httpx | mock | True | 4 | 100.0% | 0.0% | True |
| httpx | real_llm | True | 7 | 100.0% | 0.0% | True |
| click | mock | True | 4 | 100.0% | 0.0% | True |
| uvicorn | mock | True | 4 | 100.0% | 0.0% | True |

## Baseline
- Attempted: 1; succeeded: 0.
- Limitation: Baseline runs only one small repo and is qualitative, not a large-scale controlled experiment.

## Performance
| Repo | E2E | Clone | Context | Mock | Real | Baseline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| httpx | 3.21s | 5.09s | 2.32s | 0.73s | 400.02s | 364.77s |
| click | 3.39s | 2.46s | 2.79s | 1.17s | n/a | n/a |
| uvicorn | 2.49s | 2.42s | 1.99s | 0.71s | n/a | n/a |

## Quality
- pytest_all: passed (D:\Claude_workfile\CodePilot\reports\quant_metrics_v3_7\raw_logs\pytest_all.log)
- ruff: passed (D:\Claude_workfile\CodePilot\reports\quant_metrics_v3_7\raw_logs\ruff.log)
- audit_harness: failed (D:\Claude_workfile\CodePilot\reports\quant_metrics_v3_7\raw_logs\audit_harness.log)
- frontend_tests: skipped (frontend not changed)
- frontend_build: skipped (frontend not changed)

## Resume-safe
- Across 3 benchmark repo(s), CodePilot measured 49.1% average file noise reduction and 96.8% structured-context token compression.
- Mock review success rate was 100.0% with 100.0% average evidence binding on successful runs.
- Real LLM produced one successful repo-level validation; no multi-repo Real average is claimed.

## Unsupported
- httpx: baseline - The read operation timed out
- click: real_llm_input_tokens - real mode not run or provider usage unavailable
- click: real_llm_output_tokens - real mode not run or provider usage unavailable
- click: real_llm_total_tokens - real mode not run or provider usage unavailable
- click: real_call_token_compression_rate - real mode not run or provider usage unavailable
- uvicorn: real_llm_input_tokens - real mode not run or provider usage unavailable
- uvicorn: real_llm_output_tokens - real mode not run or provider usage unavailable
- uvicorn: real_llm_total_tokens - real mode not run or provider usage unavailable
- uvicorn: real_call_token_compression_rate - real mode not run or provider usage unavailable
- quality: audit_harness - failed
- quality: frontend_tests - frontend not changed
- quality: frontend_build - frontend not changed

## Reproduction
- `python scripts/metrics/run_quant_metrics.py --benchmark evaluation/datasets/repos.json --mode both --max-repos 3 --output reports/quant_metrics_v3_7`
- `python scripts/metrics/run_quant_metrics.py --benchmark evaluation/datasets/repos.json --mode real --max-repos 1 --output reports/quant_metrics_v3_7`
- `python scripts/metrics/run_quant_metrics.py --benchmark evaluation/datasets/repos.json --mode baseline --max-repos 1 --output reports/quant_metrics_v3_7`
