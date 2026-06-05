# CodePilot Evaluation Harness

This harness runs CodePilot's real backend review pipeline against known repositories and checks for production-safe outcomes.

## Targets

Targets are listed in `evaluation/repos.txt`.

Initial repositories:

- `https://github.com/Strange-Men/EnterpriseAiDataAgent.git`
- `https://github.com/pallets/flask.git`

## What It Verifies

- The review task reaches `completed` or a controlled `failed` state.
- Completed reviews include all four required report sections:
  - Architecture Summary
  - Code Smells
  - Maintainability Issues
  - Refactoring Suggestions
- Failed reviews include non-empty, user-facing error text.
- Failed reviews do not expose Python internals such as tracebacks or `IndexError`.

## Run

```powershell
python evaluation/run_eval.py
```

Use a persistent work directory when debugging:

```powershell
python evaluation/run_eval.py --work-dir .eval-work --keep-work-dir
```

The harness uses `USE_MOCK_LLM=true` through local settings, so it does not require LLM credentials. It still depends on network access to clone public GitHub repositories.
