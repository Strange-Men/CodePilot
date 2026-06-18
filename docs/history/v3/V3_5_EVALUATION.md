# CodePilot V3.5 Evaluation Platform

V3.5 evaluates CodePilot report quality, grounding, model usage, cost metadata, and latency without replacing the
existing review engine. Mock mode remains deterministic and credential-free. Real LLM evaluation is optional and
explicitly enabled per command.

## Evaluation Modes

### Deterministic Local Fixture

```powershell
python -m evaluation.run_eval `
  --dataset evaluation/datasets/v3_5_fixtures.json `
  --output-dir evaluation/runs
```

This path uses a local Flask-like fixture, the real parser/indexer/reviewer pipeline, `SandboxFilter`, SQLite
persistence, and the mock LLM. It does not use network access or credentials.

### Public Repository Evaluation

```powershell
python -m evaluation.run_eval `
  --dataset evaluation/datasets/v3_golden_repos.json `
  --max-repos 2 `
  --output-dir evaluation/runs
```

Mock LLM behavior remains deterministic, but cloning public repositories requires network access and repository
contents can change over time.

### Optional Real LLM Evaluation

```powershell
$env:OPENAI_API_KEY = "<configured outside the repository>"
python -m evaluation.run_eval `
  --dataset evaluation/datasets/v3_5_fixtures.json `
  --real-llm `
  --provider openai `
  --model gpt-4o-mini `
  --max-repos 1 `
  --output-dir evaluation/runs
```

`--real-llm` is required. Without it, the evaluator always uses mock mode. When the flag is present but
`OPENAI_API_KEY` is absent, the command exits with code 2 before creating a run directory or making a request.
`openai-compatible` is also accepted as provider metadata and uses the existing `OPENAI_BASE_URL` setting.

No credentials are written to run JSON, reports, tests, fixtures, or documentation.

## Dataset And Run Registry

Every JSON dataset has a required version, description, and repository list. The run registry stores:

- Dataset version, absolute source path, SHA-256 digest, and repository count.
- Run ID with a UTC timestamp and random suffix.
- Engine, mock/real mode, provider, model, start/end time, and duration.
- Per-repository status, quality checks, bounded `report_markdown`, report path, finding/evidence counts, and safe agent
  summaries.
- Agent prompt tokens, completion tokens, LLM calls, and duration when available.

Fixture entries use `source.type=fixture` and are copied into an evaluation workspace before entering the unchanged
`ReviewPipeline`. Public entries continue to use canonical GitHub URLs.

## Report Quality Score

The deterministic score has five equally weighted dimensions:

| Dimension | Deterministic checks |
| --- | --- |
| Readability | Executive summary, action plan, bounded sections, bounded cycle chains, no repeated long boilerplate |
| Actionability | File, impact explanation, first step, and validation guidance |
| Grounding | Evidence IDs, known evidence references, evidence appendix, no raw snippet leakage |
| Agent visibility | Agent summary, grouped findings, and persisted agent names |
| Classification quality | Flask-like precedence, generic Request/Response guard, production recommendations before tests |

Each check is boolean. A dimension score is the percentage of its checks that pass; the aggregate is the arithmetic
mean of the five dimension scores. Failed check IDs are persisted so regressions remain inspectable.

This is a product rubric, not a human-preference or semantic-correctness score.

## Cost And Latency

Per-agent duration is measured around agent execution. Prompt tokens, completion tokens, and LLM calls come from the
existing structured LLM `CostTracker`. Per-repository runtime includes clone, parse, review, persistence, and export.

Pricing is optional:

```powershell
python -m evaluation.run_eval `
  --dataset evaluation/datasets/v3_5_fixtures.json `
  --pricing-config evaluation/configs/pricing.example.json
```

The pricing JSON maps an exact model name to prompt and completion prices per million tokens. If the model is missing,
`estimated_cost` is `null`; token usage remains available. Pricing is isolated from code so stale provider prices are
not silently embedded in the evaluator.

Token counts are local tokenizer estimates, not provider invoice records. Cost is therefore an estimate even when a
pricing entry exists.

## Artifacts

Each run is stored under `evaluation/runs/<run-id>/` by default:

```text
run.json
summary.json
summary.md
quality-summary.json
quality-summary.md
cost-summary.json
cost-summary.md
repos/<repo-id>/result.json
repos/<repo-id>/report.md
comparison.json             # only with a comparable previous run
comparison.md               # only with a comparable previous run
```

`report_markdown` in JSON is bounded to 5,000 characters. The full safe Markdown report remains in `report.md`.
Persisted evidence contains IDs and references, never unredacted snippets.

## Regression Comparison

Use:

```powershell
python -m evaluation.run_eval `
  --dataset evaluation/datasets/v3_5_fixtures.json `
  --compare-previous
```

The helper selects the latest completed run that matches dataset SHA-256, engine, mode, provider, and model. Run ID is
used as a deterministic tie-breaker. It reports per-repository:

- Quality score delta.
- Newly failed and resolved checks.
- Estimated cost delta when both runs have priced cost.
- Runtime delta.

Runs with different datasets or model metadata are not compared.

## CI And Limitations

- Normal tests and CI use mock mode and need no credentials.
- Live real-LLM tests are intentionally excluded because they are nondeterministic, network-dependent, and billable.
- The deterministic fixture proves evaluation plumbing and rubric behavior, not broad model quality.
- Public repositories can move unless callers pin their own fixture snapshots.
- V3.5 has no human preference labels, benchmark leaderboard, dashboard, or automatic model selection.

## Why LangGraph Is Deferred

V3.5 measures the current fixed orchestration before changing it. CodePilot still has no measured need for dynamic
routing, cyclic agent workflows, checkpoint/resume, or human approval nodes. LangGraph can be planned for V3.6 only
after V3.5 evidence identifies a workflow problem that the existing `ReviewState` boundary cannot solve.
