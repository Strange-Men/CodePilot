from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.metrics import run_quant_metrics as metrics


def _init_repo(path: Path) -> None:
    path.mkdir()
    (path / "app.py").write_text(
        "import os\n\nclass App:\n    pass\n\ndef main():\n    return os.getcwd()\n",
        encoding="utf-8",
    )
    (path / "README.md").write_text("# sample\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=path, check=True, capture_output=True, text=True)


def test_token_estimator_runs() -> None:
    counter = metrics.PromptTokenCounter("gpt-4o-mini")
    assert counter.count("hello world") > 0
    assert metrics.token_method()


def test_scan_only_local_repo_generates_reports(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    output = tmp_path / "out"
    monkeypatch.setattr(metrics, "run_quality_checks", lambda output, skip_frontend: {})

    exit_code = metrics.main(["--repo-path", str(repo), "--mode", "scan-only", "--output", str(output)])

    assert exit_code == 0
    data = json.loads((output / "codepilot_quant_metrics.json").read_text(encoding="utf-8"))
    markdown = (output / "codepilot_quant_metrics.md").read_text(encoding="utf-8")
    assert data["metadata"]["mode"] == "scan-only"
    assert data["repos"][0]["scan"]["eligible_files"] == 1
    assert "## Noise" in markdown
    assert "## Reproduction" in markdown
    assert "mock" not in data["repos"][0]


def test_markdown_report_can_be_rendered(tmp_path: Path) -> None:
    report = {
        "metadata": {
            "generated_at": "2026-06-25T00:00:00+00:00",
            "mode": "scan-only",
            "token_estimation_method": "test",
            "commands": {"scan": "python scripts/metrics/run_quant_metrics.py --repo-path x --mode scan-only"},
        },
        "repos": [
            {
                "name": "repo",
                "source": "local_path",
                "benchmark_threshold": {"label": "small"},
                "scan": {
                    "python_files": 1,
                    "eligible_files": 1,
                    "repo_git_tracked_files": 2,
                    "file_noise_reduction_rate": 50.0,
                },
                "tokens": {
                    "baseline_source_tokens": 10,
                    "structured_context_tokens": 5,
                    "token_compression_rate": 50.0,
                },
                "code_understanding": {
                    "ast_parse_success_rate": 100.0,
                    "symbol_extraction_coverage": 100.0,
                    "total_functions": 1,
                    "total_classes": 1,
                    "dependency_edges": 0,
                },
                "performance": {
                    "e2e_duration_seconds": 0.1,
                    "clone_duration_seconds": None,
                    "context_build_duration_seconds": 0.1,
                },
            }
        ],
        "baseline": {"attempted": 0, "succeeded": 0, "limitations": "test"},
        "quality": {},
        "resume_safe": ["test claim"],
        "unsupported": [],
    }

    markdown = metrics.render_markdown(report)

    assert "# CodePilot Quant Metrics Report" in markdown
    assert "## Resume-safe" in markdown
    assert "test claim" in markdown


def test_json_schema_basic_fields_exist(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    output = tmp_path / "out"
    monkeypatch.setattr(metrics, "run_quality_checks", lambda output, skip_frontend: {})

    metrics.main(["--repo-path", str(repo), "--mode", "scan-only", "--output", str(output)])
    data = json.loads((output / "codepilot_quant_metrics.json").read_text(encoding="utf-8"))

    for key in ("metadata", "repos", "aggregate", "mock", "real", "baseline", "quality", "resume_safe", "unsupported"):
        assert key in data
