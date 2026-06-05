from __future__ import annotations

from pathlib import Path

import evaluation.run_eval as run_eval


def test_run_dataset_eval_uses_pipeline_parser_stats(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dataset = [
        {
            "id": "enterpriseai",
            "url": "https://github.com/Strange-Men/EnterpriseAiDataAgent.git",
            "name": "Strange-Men/EnterpriseAiDataAgent",
            "categories": {"size": "medium", "language": "python", "health": "healthy"},
            "tags": ["regression"],
        }
    ]

    def fake_run_repo_eval(repo_url: str, base_dir: Path) -> run_eval.EvalResult:
        return run_eval.EvalResult(
            repo_url=repo_url,
            status="completed",
            passed=True,
            details="completed with all required report sections",
            total_python_files=120,
            analyzed_files=118,
            skipped_files=2,
        )

    monkeypatch.setattr(run_eval, "run_repo_eval", fake_run_repo_eval)

    results = run_eval.run_dataset_eval(dataset, tmp_path, config={})

    assert len(results) == 1
    assert results[0].total_python_files == 120
    assert results[0].analyzed_files == 118
    assert results[0].skipped_files == 2
