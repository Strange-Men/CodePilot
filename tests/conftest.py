from __future__ import annotations

from pathlib import Path

import pytest

from backend.models.review import CodeFileSummary, RepositoryContext


@pytest.fixture
def sample_context() -> RepositoryContext:
    return RepositoryContext(
        repo_url="https://github.com/example/project",
        total_python_files=2,
        analyzed_files=2,
        skipped_files=0,
        total_lines=150,
        avg_complexity=6.5,
        repository_summary="Python repository with service and API modules.",
        file_summaries=[
            CodeFileSummary(
                path="app.py",
                classes=["App"],
                functions=["create_app"],
                purpose="Application entry point.",
                summary="app.py: purpose=Application entry point; classes=App; functions=create_app.",
                line_count=100,
                function_count=1,
                complexity_estimate=8,
                importance_score=100.0,
                importance_label="Critical",
                file_role="Entry Point",
                is_entry_point=True,
                dependencies=["services/review.py"],
                fan_out=1,
            ),
            CodeFileSummary(
                path="services/review.py",
                classes=[],
                functions=["review"],
                purpose="Implements review behavior.",
                summary="services/review.py: purpose=Implements review behavior; classes=none; functions=review.",
                line_count=50,
                function_count=1,
                complexity_estimate=5,
                importance_score=80.06,
                importance_label="High",
                file_role="Core Module",
                fan_in=1,
                is_hub=True,
            ),
        ],
        entry_points=["app.py"],
        core_modules=["services/review.py"],
        dependency_edges={
            "app.py": ["services/review.py"],
            "services/review.py": [],
        },
        hub_files=["services/review.py"],
    )


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    return repo
