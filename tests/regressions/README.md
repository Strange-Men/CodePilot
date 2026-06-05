# CodePilot Regression Tests

Regression tests capture production bugs after they are fixed. Each regression test should map to a numbered entry in `.harness/REGRESSION_RULES.md`.

## Workflow

```text
Bug -> Reproduce -> Regression Test -> Fix -> Verify
```

## Naming

- Test files: `test_regression_<number>_<short_name>.py`
- Test names: `test_regression_<number>_<expected_behavior>`

Example:

```text
test_regression_001_tree_sitter_non_ascii.py
test_regression_001_parser_handles_non_ascii_before_imports
```
