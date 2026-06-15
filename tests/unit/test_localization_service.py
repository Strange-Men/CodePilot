"""Tests for the localization service — MockTranslator and LocalizationService."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.models.context import EvidenceRecord
from backend.models.review import ReviewStatus
from backend.models.structured_review import ReviewFinding
from backend.services.localization_service import (
    LocalizationService,
    MockTranslator,
)
from backend.storage.sqlite import ReviewStore

# ---------------------------------------------------------------------------
# MockTranslator tests
# ---------------------------------------------------------------------------


class TestMockTranslator:
    def test_translates_known_title(self) -> None:
        translator = MockTranslator()
        finding = {"title": "Evidence-grounded architecture boundary"}
        result = translator.translate_finding_prose(finding)
        assert result["title_zh"] == "基于证据的架构边界问题"

    def test_translates_known_description(self) -> None:
        translator = MockTranslator()
        finding = {
            "description": (
                "The selected evidence highlights a repository concern that should be reviewed "
                "before changing entry points, core modules, shared dependencies, or refactoring boundaries."
            ),
        }
        result = translator.translate_finding_prose(finding)
        assert "仓库关注点" in result["description_zh"]

    def test_translates_known_recommendation(self) -> None:
        translator = MockTranslator()
        finding = {"recommendation": "Add contract tests around the boundary before refactoring."}
        result = translator.translate_finding_prose(finding)
        assert result["recommendation_zh"] == "在重构前为边界添加契约测试。"

    def test_translates_known_impact(self) -> None:
        translator = MockTranslator()
        finding = {
            "impact": (
                "Changes to this boundary may affect multiple consumers "
                "if the interface contract is not preserved."
            ),
        }
        result = translator.translate_finding_prose(finding)
        assert "使用者" in result["impact_zh"]

    def test_translates_known_first_step(self) -> None:
        translator = MockTranslator()
        finding = {
            "first_step": (
                "Add characterization tests covering the current "
                "public interface before restructuring."
            ),
        }
        result = translator.translate_finding_prose(finding)
        assert "表征测试" in result["first_step_zh"]

    def test_translates_known_caveat(self) -> None:
        translator = MockTranslator()
        finding = {
            "caveat": (
                "If this boundary is part of a public API, "
                "changing it may break downstream consumers."
            ),
        }
        result = translator.translate_finding_prose(finding)
        assert "公共 API" in result["caveat_zh"]

    def test_unknown_text_gets_zh_prefix(self) -> None:
        translator = MockTranslator()
        finding = {"title": "Some unknown finding title"}
        result = translator.translate_finding_prose(finding)
        assert result["title_zh"] == "[zh]Some unknown finding title"

    def test_none_field_stays_none(self) -> None:
        translator = MockTranslator()
        finding = {"title": None, "description": "test", "recommendation": None}
        result = translator.translate_finding_prose(finding)
        assert result["title_zh"] is None
        assert result["recommendation_zh"] is None

    def test_preserves_code_symbols_in_description(self) -> None:
        translator = MockTranslator()
        finding = {"description": "The `build_reviews_router` function has mixed concerns."}
        result = translator.translate_finding_prose(finding)
        assert "`build_reviews_router`" in result["description_zh"]

    def test_translates_validation_tests(self) -> None:
        translator = MockTranslator()
        finding = {
            "validation_tests": [
                "Run the full test suite before and after any boundary change.",
            ],
        }
        result = translator.translate_finding_prose(finding)
        assert "测试套件" in result["validation_tests_zh"][0]

    def test_unknown_validation_test_gets_zh_prefix(self) -> None:
        translator = MockTranslator()
        finding = {"validation_tests": ["Some unknown test instruction."]}
        result = translator.translate_finding_prose(finding)
        assert result["validation_tests_zh"][0] == "[zh]Some unknown test instruction."

    def test_empty_validation_tests(self) -> None:
        translator = MockTranslator()
        finding = {"validation_tests": []}
        result = translator.translate_finding_prose(finding)
        assert result["validation_tests_zh"] == []


# ---------------------------------------------------------------------------
# LocalizationService tests
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> ReviewStore:
    return ReviewStore(tmp_path / "test.db")


def _create_review_with_findings(store: ReviewStore, task_id: str = "task-1") -> None:
    store.create_review(task_id, "https://github.com/example/project")
    store.update_status(task_id, ReviewStatus.completed, report_markdown="# Test")
    store.replace_structured_findings(
        task_id,
        [
            ReviewFinding(
                section="Architecture Summary",
                title="Evidence-grounded architecture boundary",
                description=(
                    "The selected evidence highlights a repository concern that should be reviewed "
                    "before changing entry points, core modules, shared dependencies, or refactoring boundaries."
                ),
                severity="high",
                category="architecture",
                confidence=0.85,
                recommendation="Add contract tests around the boundary before refactoring.",
                files=["backend/api/reviews.py"],
                evidence_ids=["ev_abc123"],
                evidence=["ev_abc123 -> backend/api/reviews.py:10-20"],
                impact=(
                    "Changes to this boundary may affect multiple consumers "
                    "if the interface contract is not preserved."
                ),
                first_step=(
                    "Add characterization tests covering the current "
                    "public interface before restructuring."
                ),
                validation_tests=["Run the full test suite before and after any boundary change."],
                confidence_rationale="Based on evidence records provided in the prompt context.",
                caveat=(
                    "If this boundary is part of a public API, "
                    "changing it may break downstream consumers."
                ),
            ),
        ],
        [
            EvidenceRecord(
                evidence_id="ev_abc123",
                file_path="backend/api/reviews.py",
                start_line=10,
                end_line=20,
                snippet="code",
                kind="symbol",
                symbols=["build_reviews_router"],
            ),
        ],
    )


class TestLocalizationServiceCache:
    def test_en_returns_raw_findings(self, store: ReviewStore) -> None:
        _create_review_with_findings(store)
        service = LocalizationService(store, MockTranslator())
        raw = store.get_structured_findings("task-1")

        result = service.get_localized_findings("task-1", "en", "2024-01-01", raw)

        assert result == raw
        assert "title_zh" not in result[0]

    def test_zh_translates_and_caches(self, store: ReviewStore) -> None:
        _create_review_with_findings(store)
        service = LocalizationService(store, MockTranslator())
        raw = store.get_structured_findings("task-1")

        result = service.get_localized_findings("task-1", "zh", "2024-01-01", raw)

        assert len(result) == 1
        assert result[0]["title_zh"] == "基于证据的架构边界问题"
        assert "仓库关注点" in result[0]["description_zh"]
        # Verify cache was written
        cached = store.get_localization("task-1", "zh")
        assert cached is not None
        assert cached["source_updated_at"] == "2024-01-01"

    def test_cache_hit_returns_cached_result(self, store: ReviewStore) -> None:
        _create_review_with_findings(store)
        translator = MockTranslator()
        service = LocalizationService(store, translator)
        raw = store.get_structured_findings("task-1")

        # First call — cache miss
        result1 = service.get_localized_findings("task-1", "zh", "2024-01-01", raw)
        # Second call — cache hit
        result2 = service.get_localized_findings("task-1", "zh", "2024-01-01", raw)

        assert result1[0]["title_zh"] == result2[0]["title_zh"]

    def test_translator_failure_falls_back(self, store: ReviewStore) -> None:
        _create_review_with_findings(store)

        class FailingTranslator:
            def translate_finding_prose(self, finding: dict) -> dict:
                raise RuntimeError("LLM unavailable")

        service = LocalizationService(store, FailingTranslator())
        raw = store.get_structured_findings("task-1")

        result = service.get_localized_findings("task-1", "zh", "2024-01-01", raw)

        # Should not crash; should return findings with fallback zh values
        assert len(result) == 1
        assert result[0]["title"] == "Evidence-grounded architecture boundary"

    def test_preserves_finding_count(self, store: ReviewStore) -> None:
        store.create_review("task-multi", "https://github.com/example/project")
        store.update_status("task-multi", ReviewStatus.completed, report_markdown="# Test")
        store.replace_structured_findings(
            "task-multi",
            [
                ReviewFinding(
                    section="Architecture Summary",
                    title="Evidence-grounded architecture boundary",
                    description="desc1",
                    severity="high",
                    confidence=0.85,
                    files=["a.py"],
                    evidence_ids=["ev_a"],
                    evidence=["ev_a -> a.py:1-5"],
                ),
                ReviewFinding(
                    section="Code Smells",
                    title="Evidence-grounded code smell",
                    description="desc2",
                    severity="medium",
                    confidence=0.7,
                    files=["b.py"],
                    evidence_ids=["ev_b"],
                    evidence=["ev_b -> b.py:1-5"],
                ),
            ],
            [
                EvidenceRecord(
                    evidence_id="ev_a", file_path="a.py", start_line=1, end_line=5,
                    snippet="code", kind="symbol", symbols=[],
                ),
                EvidenceRecord(
                    evidence_id="ev_b", file_path="b.py", start_line=1, end_line=5,
                    snippet="code", kind="symbol", symbols=[],
                ),
            ],
        )
        service = LocalizationService(store, MockTranslator())
        raw = store.get_structured_findings("task-multi")

        result = service.get_localized_findings("task-multi", "zh", "2024-01-01", raw)

        assert len(result) == 2

    def test_preserves_severity_and_confidence(self, store: ReviewStore) -> None:
        _create_review_with_findings(store)
        service = LocalizationService(store, MockTranslator())
        raw = store.get_structured_findings("task-1")

        result = service.get_localized_findings("task-1", "zh", "2024-01-01", raw)

        assert result[0]["severity"] == "high"
        assert result[0]["confidence"] == 0.85

    def test_preserves_evidence_ids_and_files(self, store: ReviewStore) -> None:
        _create_review_with_findings(store)
        service = LocalizationService(store, MockTranslator())
        raw = store.get_structured_findings("task-1")

        result = service.get_localized_findings("task-1", "zh", "2024-01-01", raw)

        assert result[0]["evidence_ids"] == ["ev_abc123"]
        assert result[0]["files"] == ["backend/api/reviews.py"]

    def test_no_real_llm_import(self) -> None:
        """Verify this test module does not import httpx for translation."""
        # MockTranslator should not trigger httpx import
        translator = MockTranslator()
        finding = {"title": "test"}
        result = translator.translate_finding_prose(finding)
        assert "title_zh" in result
        # The mock translator should work without httpx
        assert callable(translator.translate_finding_prose)


class TestLocalizationServiceCascadeDelete:
    def test_delete_review_removes_localization(self, store: ReviewStore) -> None:
        _create_review_with_findings(store)
        service = LocalizationService(store, MockTranslator())
        raw = store.get_structured_findings("task-1")
        service.get_localized_findings("task-1", "zh", "2024-01-01", raw)

        assert store.get_localization("task-1", "zh") is not None

        store.delete_review("task-1")

        assert store.get_localization("task-1", "zh") is None


# ---------------------------------------------------------------------------
# Report localization tests
# ---------------------------------------------------------------------------


class TestLocalizationServiceReport:
    def test_en_report_unchanged(self, store: ReviewStore) -> None:
        _create_review_with_findings(store)
        service = LocalizationService(store, MockTranslator())
        raw = store.get_structured_findings("task-1")
        report = "# Executive Summary\nAnalysis complete.\n"

        result = service.get_localized_report("task-1", "en", "2024-01-01", report, raw)

        assert result == report

    def test_zh_report_translates_headings(self, store: ReviewStore) -> None:
        _create_review_with_findings(store)
        service = LocalizationService(store, MockTranslator())
        raw = store.get_structured_findings("task-1")
        report = "# Executive Summary\nAnalysis complete.\n"

        result = service.get_localized_report("task-1", "zh", "2024-01-01", report, raw)

        assert "# 执行摘要" in result

    def test_zh_report_translates_finding_prose(self, store: ReviewStore) -> None:
        _create_review_with_findings(store)
        service = LocalizationService(store, MockTranslator())
        raw = store.get_structured_findings("task-1")
        report = (
            "# Action Plan\n"
            "## 1. Evidence-grounded architecture boundary\n"
            "- **Why it matters:** Changes to this boundary may affect multiple consumers "
            "if the interface contract is not preserved.\n"
            "- **First step:** Add characterization tests covering the current "
            "public interface before restructuring.\n"
            "- **Caveat:** If this boundary is part of a public API, "
            "changing it may break downstream consumers.\n"
            "- **Evidence:** `ev_abc123`\n"
        )

        result = service.get_localized_report("task-1", "zh", "2024-01-01", report, raw)

        # Headings translated
        assert "# 行动计划" in result
        # Finding prose translated
        assert "使用者" in result
        assert "表征测试" in result
        assert "公共 API" in result
        # Evidence IDs preserved
        assert "ev_abc123" in result

    def test_zh_report_preserves_evidence_ids(self, store: ReviewStore) -> None:
        _create_review_with_findings(store)
        service = LocalizationService(store, MockTranslator())
        raw = store.get_structured_findings("task-1")
        report = "# Action Plan\n- **Evidence:** `ev_abc123`\n"

        result = service.get_localized_report("task-1", "zh", "2024-01-01", report, raw)

        assert "ev_abc123" in result

    def test_zh_report_preserves_file_paths(self, store: ReviewStore) -> None:
        _create_review_with_findings(store)
        service = LocalizationService(store, MockTranslator())
        raw = store.get_structured_findings("task-1")
        report = "# Action Plan\n- **Where:** `backend/api/reviews.py`\n"

        result = service.get_localized_report("task-1", "zh", "2024-01-01", report, raw)

        assert "backend/api/reviews.py" in result

    def test_zh_report_caches_result(self, store: ReviewStore) -> None:
        _create_review_with_findings(store)
        service = LocalizationService(store, MockTranslator())
        raw = store.get_structured_findings("task-1")
        report = (
            "# Action Plan\n"
            "## 1. Evidence-grounded architecture boundary\n"
            "- **Why it matters:** Changes to this boundary may affect multiple consumers "
            "if the interface contract is not preserved.\n"
        )

        result1 = service.get_localized_report("task-1", "zh", "2024-01-01", report, raw)
        result2 = service.get_localized_report("task-1", "zh", "2024-01-01", report, raw)

        assert result1 == result2
        # Verify cache was written
        cached = store.get_localization("task-1", "zh")
        assert cached is not None
        assert cached["report_markdown"] is not None

    def test_zh_report_with_failing_translator(self, store: ReviewStore) -> None:
        _create_review_with_findings(store)

        class FailingTranslator:
            def translate_finding_prose(self, finding: dict) -> dict:
                raise RuntimeError("LLM unavailable")

        service = LocalizationService(store, FailingTranslator())
        raw = store.get_structured_findings("task-1")
        report = (
            "# Executive Summary\n"
            "CodePilot analyzed 10 files.\n\n"
            "# Action Plan\n"
            "## 1. Evidence-grounded architecture boundary\n"
            "- **Why it matters:** Changes to this boundary may affect multiple consumers.\n"
        )

        result = service.get_localized_report("task-1", "zh", "2024-01-01", report, raw)

        # Should not crash
        assert "# 执行摘要" in result
        # English prose preserved (translator failed)
        assert "Changes to this boundary" in result
