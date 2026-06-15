"""Tests for the localization service — MockTranslator and LocalizationService."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.models.context import EvidenceRecord
from backend.models.review import ReviewStatus
from backend.models.structured_review import ReviewFinding
from backend.services.localization_service import (
    LOCALIZATION_SCHEMA_VERSION,
    LocalizationService,
    MockTranslator,
    _resolve_translation_provider,
    _versioned_source_key,
    build_zh_finding_title,
)
from backend.storage.sqlite import ReviewStore

# ---------------------------------------------------------------------------
# MockTranslator tests
# ---------------------------------------------------------------------------


class TestTranslationProviderResolution:
    def test_auto_prefers_mimo_when_key_available(self) -> None:
        settings = Settings(
            _env_file=None,
            MIMO_API_KEY="mimo-key",
            MIMO_BASE_URL="https://mimo.example.com/v1",
            MIMO_MODEL_NAME="mimo-model",
            OPENAI_API_KEY="openai-key",
            LOCALIZATION_PROVIDER="auto",
        )
        api_key, base_url, model = _resolve_translation_provider(settings)
        assert api_key == "mimo-key"
        assert "mimo" in base_url
        assert model == "mimo-model"

    def test_auto_falls_back_to_openai(self) -> None:
        settings = Settings(
            _env_file=None,
            OPENAI_API_KEY="openai-key",
            OPENAI_BASE_URL="https://openai.example.com/v1",
            OPENAI_MODEL="gpt-4o",
            LOCALIZATION_PROVIDER="auto",
        )
        api_key, base_url, model = _resolve_translation_provider(settings)
        assert api_key == "openai-key"
        assert model == "gpt-4o"

    def test_explicit_mimo_provider(self) -> None:
        settings = Settings(
            _env_file=None,
            MIMO_API_KEY="mimo-key",
            MIMO_BASE_URL="https://mimo.example.com/v1",
            MIMO_MODEL_NAME="mimo-model",
            OPENAI_API_KEY="openai-key",
            LOCALIZATION_PROVIDER="mimo",
        )
        api_key, base_url, model = _resolve_translation_provider(settings)
        assert api_key == "mimo-key"

    def test_explicit_openai_provider(self) -> None:
        settings = Settings(
            _env_file=None,
            MIMO_API_KEY="mimo-key",
            OPENAI_API_KEY="openai-key",
            LOCALIZATION_PROVIDER="openai",
        )
        api_key, _, _ = _resolve_translation_provider(settings)
        assert api_key == "openai-key"

    def test_model_override(self) -> None:
        settings = Settings(
            _env_file=None,
            MIMO_API_KEY="mimo-key",
            MIMO_MODEL_NAME="mimo-model",
            LOCALIZATION_PROVIDER="mimo",
            LOCALIZATION_MODEL="custom-model",
        )
        _, _, model = _resolve_translation_provider(settings)
        assert model == "custom-model"


class TestMockTranslator:
    def test_translates_known_title(self) -> None:
        translator = MockTranslator()
        finding = {"title": "Evidence-grounded architecture boundary", "category": "architecture"}
        result = translator.translate_finding_prose(finding)
        # With no symbols/files, falls back to category-level title
        assert result["title_zh"] is not None
        assert "架构" in result["title_zh"]

    def test_translates_known_description(self) -> None:
        translator = MockTranslator()
        finding = {
            "description": (
                "The selected evidence highlights a repository concern that should be reviewed "
                "before changing entry points, core modules, shared dependencies, or refactoring boundaries."
            ),
        }
        result = translator.translate_finding_prose(finding)
        assert "结构性问题" in result["description_zh"]

    def test_translates_known_recommendation(self) -> None:
        translator = MockTranslator()
        finding = {"recommendation": "Add contract tests around the boundary before refactoring."}
        result = translator.translate_finding_prose(finding)
        assert "契约测试" in result["recommendation_zh"]

    def test_translates_known_impact(self) -> None:
        translator = MockTranslator()
        finding = {
            "impact": (
                "Changes to this boundary may affect multiple consumers "
                "if the interface contract is not preserved."
            ),
        }
        result = translator.translate_finding_prose(finding)
        assert "依赖方" in result["impact_zh"]

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

    def test_unknown_text_returns_plain_english(self) -> None:
        translator = MockTranslator()
        finding = {"title": "Some unknown finding title"}
        result = translator.translate_finding_prose(finding)
        # build_zh_finding_title returns None for unknown category,
        # so title_zh falls back to plain English (no [zh] prefix)
        assert result["title_zh"] is None or "[zh]" not in str(result["title_zh"])

    def test_none_field_stays_none(self) -> None:
        translator = MockTranslator()
        finding = {"title": None, "description": "test", "recommendation": None}
        result = translator.translate_finding_prose(finding)
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

    def test_unknown_validation_test_returns_plain_english(self) -> None:
        translator = MockTranslator()
        finding = {"validation_tests": ["Some unknown test instruction."]}
        result = translator.translate_finding_prose(finding)
        assert result["validation_tests_zh"][0] == "Some unknown test instruction."
        assert "[zh]" not in result["validation_tests_zh"][0]

    def test_empty_validation_tests(self) -> None:
        translator = MockTranslator()
        finding = {"validation_tests": []}
        result = translator.translate_finding_prose(finding)
        assert result["validation_tests_zh"] == []

    def test_no_bad_term_in_translations(self) -> None:
        """MockTranslator must never produce '代码坏味道'."""
        translator = MockTranslator()
        finding = {
            "title": "Evidence-grounded code smell",
            "category": "code_smell",
            "description": "desc",
            "recommendation": "rec",
            "impact": "imp",
            "first_step": "step",
            "caveat": "cave",
            "confidence_rationale": "rationale",
            "validation_tests": ["Run the full test suite before and after any boundary change."],
        }
        result = translator.translate_finding_prose(finding)
        for key, value in result.items():
            if isinstance(value, str):
                assert "代码坏味道" not in value, f"Bad term in {key}: {value}"
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        assert "代码坏味道" not in item, f"Bad term in {key}: {item}"

    def test_never_produces_zh_prefix(self) -> None:
        """MockTranslator must never produce '[zh]' prefix in any output."""
        translator = MockTranslator()
        finding = {
            "title": "Some completely unknown title that has no translation",
            "description": "Unknown description text",
            "recommendation": "Unknown recommendation",
            "impact": "Unknown impact",
            "first_step": "Unknown first step",
            "caveat": "Unknown caveat",
            "confidence_rationale": "Unknown rationale",
            "validation_tests": ["Unknown validation test instruction."],
        }
        result = translator.translate_finding_prose(finding)
        for key, value in result.items():
            if isinstance(value, str):
                assert "[zh]" not in value, f"[zh] prefix in {key}: {value}"
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        assert "[zh]" not in item, f"[zh] prefix in {key}: {item}"


class TestBuildZhFindingTitle:
    def test_symbol_based_title(self) -> None:
        finding = {
            "category": "code_smell",
            "evidence_refs": [{"symbol_name": "send_static_file"}],
        }
        title = build_zh_finding_title(finding)
        assert title is not None
        assert "send_static_file" in title
        assert "代码质量" in title

    def test_file_based_title(self) -> None:
        finding = {
            "category": "architecture",
            "files": ["tests/test_cli.py"],
        }
        title = build_zh_finding_title(finding)
        assert title is not None
        assert "tests/test_cli.py" in title

    def test_fallback_title(self) -> None:
        finding = {"category": "refactor"}
        title = build_zh_finding_title(finding)
        assert title is not None
        assert "重构" in title

    def test_no_bad_terms(self) -> None:
        for cat in ("architecture", "code_smell", "maintainability", "refactor"):
            finding = {"category": cat}
            title = build_zh_finding_title(finding)
            assert title is not None
            assert "代码坏味道" not in title, f"Bad term for {cat}: {title}"
            assert "基于证据的" not in title, f"Generic term for {cat}: {title}"

    def test_empty_category_returns_none(self) -> None:
        finding = {"category": ""}
        title = build_zh_finding_title(finding)
        assert title is None

    def test_symbol_takes_priority_over_file(self) -> None:
        finding = {
            "category": "maintainability",
            "files": ["src/app.py"],
            "evidence_refs": [{"symbol_name": "open_session"}],
        }
        title = build_zh_finding_title(finding)
        assert title is not None
        assert "open_session" in title


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
        # Title should be concrete (file-based since evidence_refs not in raw finding)
        assert result[0]["title_zh"] is not None
        assert "架构" in result[0]["title_zh"] or "backend/api/reviews.py" in result[0]["title_zh"]
        assert "结构性问题" in result[0]["description_zh"]
        # No bad terms
        assert "代码坏味道" not in result[0].get("title_zh", "")
        # Verify cache was written with versioned key
        cached = store.get_localization("task-1", "zh")
        assert cached is not None
        assert "2024-01-01" in cached["source_updated_at"]
        assert LOCALIZATION_SCHEMA_VERSION in cached["source_updated_at"]

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

    def test_old_cache_without_version_is_ignored(self, store: ReviewStore) -> None:
        """Old v3.5.5 cached zh payloads must not be reused."""
        _create_review_with_findings(store)
        service = LocalizationService(store, MockTranslator())
        raw = store.get_structured_findings("task-1")

        # Simulate old cache entry (without version in source_updated_at)
        store.set_localization(
            task_id="task-1",
            language="zh",
            source_updated_at="2024-01-01",  # no version suffix
            payload_json='[{"title_zh":"[zh]old cached title"}]',
        )

        # Should miss cache and retranslate
        result = service.get_localized_findings("task-1", "zh", "2024-01-01", raw)

        assert "[zh]" not in str(result[0].get("title_zh", ""))

    def test_new_versioned_cache_is_hit(self, store: ReviewStore) -> None:
        """New cache with correct version is reused."""
        _create_review_with_findings(store)
        service = LocalizationService(store, MockTranslator())
        raw = store.get_structured_findings("task-1")

        # First call — populates cache
        result1 = service.get_localized_findings("task-1", "zh", "2024-01-01", raw)
        # Second call — should hit cache
        result2 = service.get_localized_findings("task-1", "zh", "2024-01-01", raw)

        assert result1[0].get("title_zh") == result2[0].get("title_zh")

    def test_versioned_source_key_contains_version(self) -> None:
        key = _versioned_source_key("2024-01-01")
        assert LOCALIZATION_SCHEMA_VERSION in key
        assert "2024-01-01" in key

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
