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
# Localization schema version — bump to invalidate stale caches
# ---------------------------------------------------------------------------

LOCALIZATION_SCHEMA_VERSION = "v3.5.8"


def _versioned_source_key(source_updated_at: str) -> str:
    """Combine source timestamp with schema version for cache validation.

    This ensures old cached payloads (e.g. from v3.5.5 with [zh] prefixes)
    are never reused after a version bump.
    """
    return f"{source_updated_at}@{LOCALIZATION_SCHEMA_VERSION}"


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
    # Titles — these are generic fallbacks; build_zh_finding_title() is preferred
    "Evidence-grounded architecture boundary": "架构边界需要审查",
    "Evidence-grounded code smell": "代码质量问题需要关注",
    "Evidence-grounded maintainability risk": "可维护性风险需要改善",
    "Evidence-grounded refactoring candidate": "重构候选需要评估",
    "Evidence-grounded repository finding": "仓库问题需要关注",
    # Descriptions
    (
        "The selected evidence highlights a repository concern that should be reviewed "
        "before changing entry points, core modules, shared dependencies, or refactoring boundaries."
    ): "引用的证据表明该区域存在结构性问题，在修改入口点、核心模块、共享依赖或重构边界前应优先审查。",
    # Recommendations
    "Add contract tests around the boundary before refactoring.": "在重构前为该边界添加契约测试，确保接口行为不变。",
    "Inspect the cited code path and reduce the highest-complexity responsibility first.": (
        "检查引用的代码路径，优先降低复杂度最高的职责。"
    ),
    "Stabilize the cited dependency boundary and cover it with focused tests.": (
        "稳定引用的依赖边界，并用针对性测试覆盖。"
    ),
    "Extract the cited responsibility behind a smaller interface.": "将引用的职责提取到更小的接口中，降低耦合度。",
    "Review the cited evidence before changing code.": "修改代码前先审查引用的证据，确认影响范围。",
    # Impacts
    (
        "Changes to this boundary may affect multiple consumers "
        "if the interface contract is not preserved."
    ): "如果接口契约未被保留，该边界的变更可能影响多个依赖方。",
    (
        "The cited responsibility may accumulate unrelated "
        "changes, increasing merge conflict risk."
    ): "该职责可能积累不相关的变更，增加合并冲突的风险。",
    (
        "Without focused test coverage, future changes to "
        "this area may introduce silent regressions."
    ): "缺少针对性测试覆盖时，后续变更可能引入隐蔽的回归问题。",
    (
        "Leaving the current structure unaddressed makes "
        "future feature work slower and riskier."
    ): "不改善当前结构会导致后续功能开发更慢、风险更高。",
    # First steps
    (
        "Add characterization tests covering the current "
        "public interface before restructuring."
    ): "在重构前为当前公共接口添加表征测试，锁定现有行为。",
    (
        "Identify the single highest-complexity responsibility "
        "and extract it behind a focused interface."
    ): "识别复杂度最高的职责，将其提取到独立接口中。",
    (
        "Add targeted tests for the cited boundary, "
        "then review dependency directions."
    ): "为引用的边界添加针对性测试，然后审查依赖方向是否合理。",
    (
        "Write tests that pin current behavior, "
        "then extract the smallest reusable unit."
    ): "编写测试锁定当前行为，然后提取最小的可复用单元。",
    # Confidence rationale
    "Based on evidence records provided in the prompt context.": "基于提示上下文中提供的证据记录。",
    # Caveats
    (
        "If this boundary is part of a public API, "
        "changing it may break downstream consumers."
    ): "如果该边界属于公共 API，变更可能破坏下游使用者。",
    (
        "Some duplication may be intentional to "
        "preserve independent extension points."
    ): "部分重复可能是有意为之，以保留独立的扩展点。",
    (
        "This finding is based on structural signals; "
        "confirm with production behavior before acting."
    ): "该发现基于结构化信号；行动前请结合生产行为确认。",
    (
        "Refactoring should be incremental; avoid large-scope "
        "changes without intermediate verification."
    ): "重构应渐进式进行，避免未经中间验证的大范围变更。",
}

# Validation test translations
_MOCK_VALIDATION_TRANSLATIONS: dict[str, str] = {
    "Run the full test suite before and after any boundary change.": (
        "在边界变更前后运行完整测试套件，确认无回归。"
    ),
    "Run targeted unit tests for the cited module after each extraction step.": (
        "在每个提取步骤后运行引用模块的单元测试。"
    ),
    "Run the test suite and verify no new warnings or failures appear.": (
        "运行测试套件，确认没有新增警告或失败。"
    ),
    "Run the test suite after each incremental extraction.": "每次增量提取后运行测试套件。",
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
                result[zh_key] = _MOCK_TRANSLATIONS.get(value, value)
            else:
                result[zh_key] = value

        # Build concrete title from evidence when available
        concrete_title = build_zh_finding_title(finding)
        if concrete_title:
            result["title_zh"] = concrete_title

        # Handle validation_tests (list of strings)
        tests = finding.get("validation_tests") or []
        result["validation_tests_zh"] = [
            _MOCK_VALIDATION_TRANSLATIONS.get(t, t) for t in tests
        ]

        return result


# ---------------------------------------------------------------------------
# Deterministic Chinese finding title builder
# ---------------------------------------------------------------------------

_CATEGORY_ZH_TEMPLATES: dict[str, list[str]] = {
    "architecture": [
        "{symbol} 的架构边界需要审查",
        "{symbol} 相关的模块边界存在风险",
        "架构边界问题：{symbol}",
    ],
    "code_smell": [
        "{symbol} 的代码质量需要关注",
        "{symbol} 存在代码质量问题",
        "{symbol} 的复杂度较高",
    ],
    "maintainability": [
        "{symbol} 的可维护性需要改善",
        "{symbol} 存在可维护性风险",
        "{symbol} 的职责划分可以优化",
    ],
    "refactor": [
        "{symbol} 适合小步重构",
        "{symbol} 存在重构机会",
        "{symbol} 的结构可以简化",
    ],
}

_CATEGORY_ZH_FILE_TEMPLATES: dict[str, list[str]] = {
    "architecture": [
        "{file} 的模块边界需要审查",
        "{file} 存在架构边界风险",
    ],
    "code_smell": [
        "{file} 存在代码质量问题",
        "{file} 的代码质量需要关注",
    ],
    "maintainability": [
        "{file} 的可维护性需要改善",
        "{file} 存在可维护性风险",
    ],
    "refactor": [
        "{file} 存在重构机会",
        "{file} 的结构可以简化",
    ],
}

_CATEGORY_ZH_FALLBACK: dict[str, str] = {
    "architecture": "架构边界需要审查",
    "code_smell": "代码质量问题需要关注",
    "maintainability": "可维护性风险需要改善",
    "refactor": "重构候选需要评估",
}


def build_zh_finding_title(finding: dict) -> str | None:
    """Build a concrete Chinese finding title from evidence symbols/files.

    Uses the first available symbol from evidence_ids context or files
    to produce a specific, human-readable title. Returns None if no
    concrete title can be built (caller should use translated fallback).

    Rules:
    - Prefer symbol-based title when symbols are available.
    - Fall back to file-based title when files are available.
    - Never invent unsupported behavior.
    - Preserve file paths and symbols exactly.
    """
    category = finding.get("category") or ""
    # Try to get symbols from the finding's evidence context
    symbols = _extract_finding_symbols(finding)
    files = finding.get("files") or []

    if symbols and category in _CATEGORY_ZH_TEMPLATES:
        template = _CATEGORY_ZH_TEMPLATES[category][0]
        return template.format(symbol=symbols[0])

    if files and category in _CATEGORY_ZH_FILE_TEMPLATES:
        # Use the shortest file path for readability
        shortest = min(files, key=len)
        template = _CATEGORY_ZH_FILE_TEMPLATES[category][0]
        return template.format(file=shortest)

    # Fallback to category-level title
    return _CATEGORY_ZH_FALLBACK.get(category)


def _extract_finding_symbols(finding: dict) -> list[str]:
    """Extract symbol names from a finding's evidence references."""
    # Check if finding has evidence_refs with symbol names
    evidence_refs = finding.get("evidence_refs") or []
    symbols = []
    for ref in evidence_refs:
        if isinstance(ref, dict):
            name = ref.get("symbol_name")
            if name and name not in symbols:
                symbols.append(name)
    # Also check if finding has a direct symbols field
    direct_symbols = finding.get("symbols") or []
    for s in direct_symbols:
        if isinstance(s, str) and s not in symbols:
            symbols.append(s)
    return symbols


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
    "- Use these terms: 代码质量问题 (not 代码坏味道), 可维护性, 重构建议, 架构分析.\n"
    "- Prefer phrases like: 为什么重要, 建议, 安全第一步, 验证方式, 注意事项.\n"
    "- Title should be specific to the symbol or file, not generic like '基于证据的...'.\n"
    "Return only valid JSON with *_zh keys."
)

_RETRYABLE_STATUS_CODES = {408, 409, 429}
_RETRYABLE_TIMEOUT_CLASSES = (
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
)


def _resolve_translation_provider(settings: Settings) -> tuple[str, str, str]:
    """Resolve (api_key, base_url, model) for translation.

    Uses ``settings.localization_provider`` to pick the upstream:
    - ``"mimo"``: MiMo settings
    - ``"openai"``: OpenAI-compatible settings
    - ``"auto"`` (default): MiMo if key available, else OpenAI
    """
    provider = (settings.localization_provider or "auto").strip().lower()

    if provider == "mimo":
        api_key = settings.mimo_api_key or ""
        base_url = settings.mimo_base_url
        model = settings.localization_model or settings.mimo_model_name
        return api_key, base_url, model

    if provider == "openai":
        api_key = settings.openai_api_key or ""
        base_url = settings.openai_base_url
        model = settings.localization_model or settings.openai_model
        return api_key, base_url, model

    # auto: prefer MiMo, fall back to OpenAI
    if settings.mimo_api_key:
        api_key = settings.mimo_api_key
        base_url = settings.mimo_base_url
        model = settings.localization_model or settings.mimo_model_name
        return api_key, base_url, model

    api_key = settings.openai_api_key or ""
    base_url = settings.openai_base_url
    model = settings.localization_model or settings.openai_model
    return api_key, base_url, model


class LLMTranslator:
    """Production translator using an OpenAI-compatible API.

    Provider selection (``localization_provider`` setting):
    - ``"auto"`` (default): prefer MiMo if ``mimo_api_key`` is set,
      otherwise fall back to OpenAI-compatible settings.
    - ``"mimo"``: use MiMo settings exclusively.
    - ``"openai"``: use OpenAI-compatible settings exclusively.

    The ``localization_model`` setting overrides the model chosen by
    provider auto-detection.  If ``None``, the provider's default model
    is used.
    """

    def __init__(
        self,
        settings: Settings,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        api_key, base_url, model = _resolve_translation_provider(settings)
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
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

        versioned_key = _versioned_source_key(source_updated_at)
        cached = self._store.get_localization(task_id, "zh")
        if cached and cached.get("source_updated_at") == versioned_key:
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
                source_updated_at=versioned_key,
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
        versioned_key = _versioned_source_key(source_updated_at)
        cached = self._store.get_localization(task_id, "zh")
        if cached and cached.get("report_markdown"):
            if cached.get("source_updated_at") == versioned_key:
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
                source_updated_at=versioned_key,
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
