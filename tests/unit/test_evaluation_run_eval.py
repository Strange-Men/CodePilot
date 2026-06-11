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

    def fake_run_repo_eval(repo_url: str, base_dir: Path, review_engine: str = "v3_multi_agent") -> run_eval.EvalResult:
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


def test_run_dataset_eval_fails_completed_repo_below_min_source_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dataset = [
        {
            "id": "underparsed-js",
            "url": "https://github.com/example/underparsed-js.git",
            "name": "example/underparsed-js",
            "categories": {"size": "small", "language": "javascript", "health": "healthy"},
            "tags": ["regression"],
            "expected": {"min_source_files": 3},
        }
    ]

    def fake_run_repo_eval(repo_url: str, base_dir: Path, review_engine: str = "v3_multi_agent") -> run_eval.EvalResult:
        return run_eval.EvalResult(
            repo_url=repo_url,
            status="completed",
            passed=True,
            details="completed with all required report sections",
            total_python_files=1,
            analyzed_files=1,
            skipped_files=0,
        )

    monkeypatch.setattr(run_eval, "run_repo_eval", fake_run_repo_eval)

    results = run_eval.run_dataset_eval(dataset, tmp_path, config={})

    assert len(results) == 1
    assert results[0].passed is False
    assert results[0].details == "parsed source file count 1 is below required minimum 3"


def test_run_dataset_eval_uses_language_min_source_files_from_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dataset = [
        {
            "id": "underparsed-python",
            "url": "https://github.com/example/underparsed-python.git",
            "name": "example/underparsed-python",
            "categories": {"size": "small", "language": "python", "health": "healthy"},
            "tags": ["regression"],
        }
    ]

    def fake_run_repo_eval(repo_url: str, base_dir: Path, review_engine: str = "v3_multi_agent") -> run_eval.EvalResult:
        return run_eval.EvalResult(
            repo_url=repo_url,
            status="completed",
            passed=True,
            details="completed with all required report sections",
            total_python_files=0,
            analyzed_files=0,
            skipped_files=0,
        )

    monkeypatch.setattr(run_eval, "run_repo_eval", fake_run_repo_eval)

    results = run_eval.run_dataset_eval(
        dataset,
        tmp_path,
        config={"language_expectations": {"python": {"min_source_files": 1}}},
    )

    assert results[0].passed is False
    assert results[0].details == "parsed source file count 0 is below required minimum 1"


def test_run_dataset_eval_fails_completed_repo_above_max_source_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dataset = [
        {
            "id": "oversized-js",
            "url": "https://github.com/example/oversized-js.git",
            "name": "example/oversized-js",
            "categories": {"size": "small", "language": "javascript", "health": "healthy"},
            "tags": ["regression"],
            "expected": {"max_source_files": 2},
        }
    ]

    def fake_run_repo_eval(repo_url: str, base_dir: Path, review_engine: str = "v3_multi_agent") -> run_eval.EvalResult:
        return run_eval.EvalResult(
            repo_url=repo_url,
            status="completed",
            passed=True,
            details="completed with all required report sections",
            total_python_files=3,
            analyzed_files=3,
            skipped_files=0,
        )

    monkeypatch.setattr(run_eval, "run_repo_eval", fake_run_repo_eval)

    results = run_eval.run_dataset_eval(dataset, tmp_path, config={})

    assert results[0].passed is False
    assert results[0].details == "parsed source file count 3 is above allowed maximum 2"


def test_real_llm_cli_flags_are_explicit_and_mock_remains_default(tmp_path: Path) -> None:
    args = run_eval.parse_args(
        [
            "--real-llm",
            "--provider",
            "openai-compatible",
            "--model",
            "example-model",
            "--max-repos",
            "2",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert args.real_llm is True
    assert args.provider == "openai-compatible"
    assert args.model == "example-model"
    assert args.max_repos == 2
    assert args.output_dir == tmp_path
    assert run_eval.parse_args([]).real_llm is False


def test_real_llm_configuration_fails_gracefully_without_credentials() -> None:
    error = run_eval.validate_real_llm_configuration(
        real_llm=True,
        provider="openai",
        model="example-model",
        environ={},
    )

    assert error is not None
    assert "OPENAI_API_KEY" in error
    assert "mock mode" in error


def test_real_llm_main_does_not_create_artifacts_without_credentials(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    output_dir = tmp_path / "runs"

    exit_code = run_eval.main(
        [
            "--real-llm",
            "--model",
            "example-model",
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 2
    assert "Evaluation configuration error" in capsys.readouterr().err
    assert not output_dir.exists()
