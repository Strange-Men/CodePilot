from __future__ import annotations

import pytest

from backend.services.scoring import (
    ScoreInput,
    detect_entry_point,
    importance_label,
    score_files,
)


@pytest.mark.parametrize(
    ("score", "label"),
    [
        (100, "Critical"),
        (90, "Critical"),
        (89.99, "High"),
        (70, "High"),
        (69.99, "Medium"),
        (40, "Medium"),
        (39.99, "Low"),
        (20, "Low"),
        (19.99, "Peripheral"),
        (0, "Peripheral"),
    ],
)
def test_importance_labels_cover_score_range(score: float, label: str) -> None:
    assert importance_label(score) == label


def test_scores_are_normalized_and_apply_path_modifiers() -> None:
    scored = score_files(
        [
            ScoreInput("src/feature.py", line_count=100, complexity_estimate=0),
            ScoreInput("core/feature.py", line_count=100, complexity_estimate=0),
            ScoreInput("tests/test_feature.py", line_count=100, complexity_estimate=0),
            ScoreInput("docs/example.py", line_count=100, complexity_estimate=0),
        ]
    )

    assert scored["core/feature.py"].score == 100
    assert scored["core/feature.py"].label == "Critical"
    assert scored["src/feature.py"].score == 75
    assert scored["src/feature.py"].label == "High"
    assert scored["tests/test_feature.py"].score == 25
    assert scored["tests/test_feature.py"].label == "Low"
    assert scored["docs/example.py"].score == 12.5
    assert scored["docs/example.py"].label == "Peripheral"
    assert all(0 <= file.score <= 100 for file in scored.values())


@pytest.mark.parametrize(
    ("path", "source"),
    [
        ("main.py", "pass"),
        ("pkg/app.py", "pass"),
        ("server.py", "pass"),
        ("manage.py", "pass"),
        ("cli.py", "pass"),
        ("pkg/__main__.py", "pass"),
        ("pkg/main_worker.py", "pass"),
        ("worker.py", "if __name__ == '__main__':\n    run()"),
        ("bootstrap.py", "app = FastAPI()"),
        ("src/index.ts", "const app = express()"),
    ],
)
def test_entry_point_detection(path: str, source: str) -> None:
    assert detect_entry_point(path, source)


def test_non_bootstrap_module_is_not_an_entry_point() -> None:
    assert not detect_entry_point("services/review.py", "def review():\n    return True")


def test_dependency_metrics_increase_normalized_importance() -> None:
    scored = score_files(
        [
            ScoreInput("plain.py", line_count=100, complexity_estimate=10),
            ScoreInput(
                "connected.py",
                line_count=100,
                complexity_estimate=10,
                fan_in=3,
                fan_out=2,
                in_dependency_cycle=True,
            ),
        ]
    )

    assert scored["connected.py"].score == 100
    assert scored["plain.py"].score < scored["connected.py"].score
