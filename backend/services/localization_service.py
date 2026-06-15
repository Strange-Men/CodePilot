"""Localization service for translating review finding prose to Chinese.

Provides an LLM-backed translation layer with SQLite caching.
Canonical English data is never modified — only display prose is translated.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Protocol

import httpx

from backend.core.config import Settings
from backend.core.logging import get_logger
from backend.storage.sqlite import ReviewStore

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Translator protocol
# ---------------------------------------------------------------------------

PROSE_FIELDS = (
    "title",
    "description",
    "recommendation",
    "impact",
    "first_step",
    "confidence_rationale",
    "caveat",
)


class TranslatorProtocol(Protocol):
    """Translates prose fields of a single finding to Chinese."""

    def translate_finding_prose(self, finding: dict) -> dict:
        """Return a dict with *_zh keys for each prose field."""
        ...


# ---------------------------------------------------------------------------
# Mock translator — deterministic, no LLM calls
# ---------------------------------------------------------------------------

_MOCK_TRANSLATIONS: dict[str, str] = {
    # Titles
    "Evidence-grounded architecture boundary": "基于证据的架构边界问题",
    "Evidence-grounded code smell": "基于证据的代码坏味道",
    "Evidence-grounded maintainability risk": "基于证据的可维护性风险",
    "Evidence-grounded refactoring candidate": "基于证据的重构候选",
    "Evidence-grounded repository finding": "基于证据的仓库发现",
    # Descriptions
    (
        "The selected evidence highlights a repository concern that should be reviewed "
        "before changing entry points, core modules, shared dependencies, or refactoring boundaries."
    ): "所选证据指出了一个仓库关注点，在修改入口点、核心模块、共享依赖或重构边界之前应先审查。",
    # Recommendations
    "Add contract tests around the boundary before refactoring.": "在重构前为边界添加契约测试。",
    "Inspect the cited code path and reduce the highest-complexity responsibility first.": (
        "检查引用的代码路径，首先降低最高复杂度的职责。"
    ),
    "Stabilize the cited dependency boundary and cover it with focused tests.": (
        "稳定引用的依赖边界，并用聚焦的测试覆盖它。"
    ),
    "Extract the cited responsibility behind a smaller interface.": "将引用的职责提取到更小的接口后面。",
    "Review the cited evidence before changing code.": "在修改代码前审查引用的证据。",
    # Impacts
    (
        "Changes to this boundary may affect multiple consumers "
        "if the interface contract is not preserved."
    ): "如果接口契约未被保留，对此边界的更改可能影响多个使用者。",
    (
        "The cited responsibility may accumulate unrelated "
        "changes, increasing merge conflict risk."
    ): "引用的职责可能积累不相关的更改，增加合并冲突风险。",
    (
        "Without focused test coverage, future changes to "
        "this area may introduce silent regressions."
    ): "如果没有聚焦的测试覆盖，对此区域的未来更改可能引入隐蔽的回归。",
    (
        "Leaving the current structure unaddressed makes "
        "future feature work slower and riskier."
    ): "不处理当前结构会使未来的功能开发更慢且风险更高。",
    # First steps
    (
        "Add characterization tests covering the current "
        "public interface before restructuring."
    ): "在重构前添加覆盖当前公共接口的表征测试。",
    (
        "Identify the single highest-complexity responsibility "
        "and extract it behind a focused interface."
    ): "识别单一最高复杂度的职责并将其提取到聚焦的接口后面。",
    (
        "Add targeted tests for the cited boundary, "
        "then review dependency directions."
    ): "为引用的边界添加有针对性的测试，然后审查依赖方向。",
    (
        "Write tests that pin current behavior, "
        "then extract the smallest reusable unit."
    ): "编写固定当前行为的测试，然后提取最小的可复用单元。",
    # Confidence rationale
    "Based on evidence records provided in the prompt context.": "基于提示上下文中提供的证据记录。",
    # Caveats
    (
        "If this boundary is part of a public API, "
        "changing it may break downstream consumers."
    ): "如果此边界是公共 API 的一部分，更改它可能破坏下游使用者。",
    (
        "Some duplication may be intentional to "
        "preserve independent extension points."
    ): "某些重复可能是有意为之，以保留独立的扩展点。",
    (
        "This finding is based on structural signals; "
        "confirm with production behavior before acting."
    ): "此发现基于结构化信号；行动前请用生产行为确认。",
    (
        "Refactoring should be incremental; avoid large-scope "
        "changes without intermediate verification."
    ): "重构应渐进式进行；避免没有中间验证的大范围更改。",
}

# Validation test translations
_MOCK_VALIDATION_TRANSLATIONS: dict[str, str] = {
    "Run the full test suite before and after any boundary change.": (
        "在任何边界更改前后运行完整测试套件。"
    ),
    "Run targeted unit tests for the cited module after each extraction step.": (
        "在每个提取步骤后为引用的模块运行有针对性的单元测试。"
    ),
    "Run the test suite and verify no new warnings or failures appear.": (
        "运行测试套件并验证没有新的警告或失败出现。"
    ),
    "Run the test suite after each incremental extraction.": "在每个增量提取后运行测试套件。",
}


class MockTranslator:
    """Deterministic translator for testing. No real LLM calls."""

    def translate_finding_prose(self, finding: dict) -> dict:
        result: dict[str, str | list[str] | None] = {}
        for field in PROSE_FIELDS:
            value = finding.get(field)
            zh_key = f"{field}_zh"
            if value is None:
                result[zh_key] = None
            elif isinstance(value, str):
                result[zh_key] = _MOCK_TRANSLATIONS.get(value, f"[zh]{value}")
            else:
                result[zh_key] = value

        # Handle validation_tests (list of strings)
        tests = finding.get("validation_tests") or []
        result["validation_tests_zh"] = [
            _MOCK_VALIDATION_TRANSLATIONS.get(t, f"[zh]{t}") for t in tests
        ]

        return result


# ---------------------------------------------------------------------------
# LLM translator — production, uses httpx
# ---------------------------------------------------------------------------

_TRANSLATION_SYSTEM_PROMPT = (
    "You are a professional translator for Chinese software engineers. "
    "Translate the following code review finding fields to natural Chinese. "
    "Rules:\n"
    "- Preserve code symbols exactly (e.g., function names, variable names).\n"
    "- Preserve file paths exactly.\n"
    "- Preserve evidence IDs exactly (e.g., ev_abc123).\n"
    "- Do not change severity or confidence values.\n"
    "- Keep concise and professional.\n"
    "- Prefer phrases like: 为什么重要, 建议, 安全第一步, 验证方式, 兼容性注意事项.\n"
    "Return only valid JSON with *_zh keys."
)

_RETRYABLE_STATUS_CODES = {408, 409, 429}
_RETRYABLE_TIMEOUT_CLASSES = (
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
)


class LLMTranslator:
    """Production translator using an OpenAI-compatible API."""

    def __init__(
        self,
        settings: Settings,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_key = settings.openai_api_key or ""
        self._base_url = settings.openai_base_url.rstrip("/")
        self._model = settings.openai_model
        self._timeout = httpx.Timeout(
            connect=settings.llm_connect_timeout,
            read=settings.llm_read_timeout,
            write=settings.llm_write_timeout,
            pool=settings.llm_pool_timeout,
        )
        self._max_retries = settings.llm_max_retries
        self.sleep = sleep

    def translate_finding_prose(self, finding: dict) -> dict:
        """Translate prose fields via LLM. Falls back to English on failure."""
        input_payload = {field: finding.get(field) for field in PROSE_FIELDS}
        input_payload["validation_tests"] = finding.get("validation_tests") or []
        input_payload["files"] = finding.get("files") or []
        input_payload["evidence_ids"] = finding.get("evidence_ids") or []

        try:
            zh_payload = self._call_llm(input_payload)
        except Exception:
            logger.warning("event=translation_failed fallback=english")
            return self._english_fallback(finding)

        result: dict[str, str | list[str] | None] = {}
        for field in PROSE_FIELDS:
            zh_key = f"{field}_zh"
            zh_value = zh_payload.get(zh_key)
            if zh_value and isinstance(zh_value, str):
                result[zh_key] = zh_value
            else:
                result[zh_key] = finding.get(field)

        tests = finding.get("validation_tests") or []
        zh_tests = zh_payload.get("validation_tests_zh")
        if isinstance(zh_tests, list) and len(zh_tests) == len(tests):
            result["validation_tests_zh"] = zh_tests
        else:
            result["validation_tests_zh"] = tests

        return result

    def _call_llm(self, input_payload: dict) -> dict:
        if not self._api_key:
            raise RuntimeError("API key not configured for translation.")

        url = f"{self._base_url}/chat/completions"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": _TRANSLATION_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(input_payload, ensure_ascii=False)},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

        with httpx.Client(timeout=self._timeout) as client:
            for retry_index in range(self._max_retries + 1):
                try:
                    response = client.post(
                        url,
                        headers={"Authorization": f"Bearer {self._api_key}"},
                        json=payload,
                    )
                    if response.status_code not in _RETRYABLE_STATUS_CODES and response.status_code < 500:
                        response.raise_for_status()
                        data = response.json()
                        content = data["choices"][0]["message"]["content"]
                        return json.loads(content)
                    if retry_index == self._max_retries:
                        response.raise_for_status()
                except _RETRYABLE_TIMEOUT_CLASSES:
                    if retry_index == self._max_retries:
                        raise
                except httpx.RequestError:
                    if retry_index == self._max_retries:
                        raise
                self.sleep(1.0 * (2 ** retry_index))
        raise RuntimeError("Translation LLM request failed without a response.")

    @staticmethod
    def _english_fallback(finding: dict) -> dict:
        result: dict[str, str | list[str] | None] = {}
        for field in PROSE_FIELDS:
            result[f"{field}_zh"] = finding.get(field)
        result["validation_tests_zh"] = finding.get("validation_tests") or []
        return result


# ---------------------------------------------------------------------------
# Localization service — orchestrates caching + translation
# ---------------------------------------------------------------------------

_TRANSLATABLE_FIELDS = (
    "title",
    "description",
    "recommendation",
    "impact",
    "first_step",
    "confidence_rationale",
    "caveat",
)


class LocalizationService:
    """Translates review findings with SQLite-backed caching."""

    def __init__(self, store: ReviewStore, translator: TranslatorProtocol) -> None:
        self._store = store
        self._translator = translator

    def get_localized_findings(
        self,
        task_id: str,
        lang: str,
        source_updated_at: str,
        raw_findings: list[dict],
    ) -> list[dict]:
        """Return findings with localized prose fields merged in.

        For lang != 'zh', returns raw_findings unchanged.
        For lang == 'zh', checks cache, translates on miss, merges *_zh keys.
        """
        if lang != "zh":
            return raw_findings

        cached = self._store.get_localization(task_id, "zh")
        if cached and cached.get("source_updated_at") == source_updated_at:
            return self._merge_cached(raw_findings, cached["payload_json"])

        # Cache miss — translate each finding
        zh_findings: list[dict] = []
        for finding in raw_findings:
            try:
                zh = self._translator.translate_finding_prose(finding)
            except Exception:
                logger.warning(
                    "event=translation_error task_id=%s finding_index=%s",
                    task_id,
                    finding.get("finding_index"),
                )
                zh = {f"{f}_zh": finding.get(f) for f in _TRANSLATABLE_FIELDS}
                zh["validation_tests_zh"] = finding.get("validation_tests") or []
            zh_findings.append(zh)

        # Cache the result
        try:
            self._store.set_localization(
                task_id=task_id,
                language="zh",
                source_updated_at=source_updated_at,
                payload_json=json.dumps(zh_findings, ensure_ascii=False, sort_keys=True),
            )
        except Exception:
            logger.warning("event=localization_cache_write_failed task_id=%s", task_id)

        return self._merge_into_findings(raw_findings, zh_findings)

    def get_localized_report(
        self,
        task_id: str,
        lang: str,
        source_updated_at: str,
        report_markdown: str,
        raw_findings: list[dict] | None = None,
    ) -> str:
        """Return localized report markdown with natural Chinese prose.

        Checks cache first. On miss, translates findings and re-renders
        the report with localized prose. Caches the result.
        """
        if lang != "zh":
            return report_markdown

        # Check cache for full Chinese report
        cached = self._store.get_localization(task_id, "zh")
        if cached and cached.get("report_markdown"):
            if cached.get("source_updated_at") == source_updated_at:
                return cached["report_markdown"]

        if raw_findings is None:
            raw_findings = []

        # Get localized findings (may use cache or translate)
        localized_findings = self.get_localized_findings(
            task_id, "zh", source_updated_at, raw_findings,
        )

        # Generate Chinese report with natural prose
        from backend.reviewers.localized_report_renderer import (
            render_localized_report_with_prose,
        )

        zh_report = render_localized_report_with_prose(
            report_markdown, localized_findings, "zh",
        )

        # Cache the result
        try:
            cached_after = self._store.get_localization(task_id, "zh")
            payload_json = cached_after["payload_json"] if cached_after else None
            self._store.set_localization(
                task_id=task_id,
                language="zh",
                source_updated_at=source_updated_at,
                payload_json=payload_json,
                report_markdown=zh_report,
            )
        except Exception:
            logger.warning(
                "event=localization_report_cache_write_failed task_id=%s", task_id,
            )

        return zh_report

    @staticmethod
    def _merge_cached(raw_findings: list[dict], payload_json: str) -> list[dict]:
        try:
            zh_list = json.loads(payload_json)
        except (json.JSONDecodeError, TypeError):
            return raw_findings

        if not isinstance(zh_list, list) or len(zh_list) != len(raw_findings):
            return raw_findings

        merged = []
        for finding, zh in zip(raw_findings, zh_list, strict=False):
            merged_finding = dict(finding)
            for field in _TRANSLATABLE_FIELDS:
                zh_key = f"{field}_zh"
                zh_value = zh.get(zh_key)
                if zh_value:
                    merged_finding[zh_key] = zh_value
            zh_tests = zh.get("validation_tests_zh")
            if isinstance(zh_tests, list):
                merged_finding["validation_tests_zh"] = zh_tests
            merged.append(merged_finding)
        return merged

    @staticmethod
    def _merge_into_findings(raw_findings: list[dict], zh_findings: list[dict]) -> list[dict]:
        merged = []
        for finding, zh in zip(raw_findings, zh_findings, strict=False):
            merged_finding = dict(finding)
            for field in _TRANSLATABLE_FIELDS:
                zh_key = f"{field}_zh"
                zh_value = zh.get(zh_key)
                if zh_value:
                    merged_finding[zh_key] = zh_value
            zh_tests = zh.get("validation_tests_zh")
            if isinstance(zh_tests, list):
                merged_finding["validation_tests_zh"] = zh_tests
            merged.append(merged_finding)
        return merged
