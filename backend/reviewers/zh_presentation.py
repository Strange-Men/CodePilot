"""Centralized Chinese presentation pipeline for CodePilot.

Owns all Chinese quality rules for zh reports:
- zh field validation (detect English leakage in display.zh fields)
- zh field repair (replace English/mixed fields with safe Chinese templates)
- zh metadata repair (fix evidence appendix labels, repo summary metadata)
- final zh markdown cleanup (delegate to zh_quality.normalize_zh_markdown)

All other modules call this module for Chinese quality. They must not
contain new phrase tables or ad-hoc Chinese replacements.

Deterministic rule-based — no LLM calls.
"""

from __future__ import annotations

import re

from backend.models.structured_review import (
    BilingualTextField,
    DisplayFields,
    ReviewFinding,
)
from backend.reviewers.zh_quality import (
    _CODE_SYMBOL_RE,
    _COMMON_ENGLISH_WORDS,
    _EVIDENCE_REF_RE,
    _TECH_NAMES,
    normalize_zh_markdown,
)

# ---------------------------------------------------------------------------
# Chinese character detection
# ---------------------------------------------------------------------------

_ZH_CHAR_RE = re.compile(r'[一-鿿]')

# Command prefixes for validation test detection (matches zh_quality._COMMAND_PREFIXES)
_TEST_COMMAND_PREFIXES = (
    "pytest", "npm", "python", "pip", "git", "docker", "make", "cargo",
    "go ", "yarn", "pnpm", "npx", "node", "deno", "bun", "curl", "wget",
    "chmod", "mkdir", "rm ", "mv ", "cp ", "ls ", "cat ", "grep", "sed",
    "awk", "find", "powershell", "cmd", "bash", "sh ",
)

# ---------------------------------------------------------------------------
# Category-specific Chinese templates for field repair
# ---------------------------------------------------------------------------

_IMPACT_TEMPLATES: dict[str, str] = {
    "code_smell": "该问题会增加维护成本，并提高后续修改遗漏或引入回归的风险。",
    "architecture": "该边界变更可能影响多个依赖方，需要谨慎处理。",
    "maintainability": "该区域的可维护性较差，后续修改和调试成本较高。",
    "refactor": "该区域结构较复杂，后续扩展和调试成本较高。",
}

_RECOMMENDATION_TEMPLATES: dict[str, str] = {
    "code_smell": "先确认该逻辑是否确实重复；如果重复，应在保持公共 API 兼容的前提下提取公共实现。",
    "architecture": "在修改该边界前，先添加契约测试确保接口行为不变。",
    "maintainability": "检查引用的代码路径，优先降低复杂度最高的职责。",
    "refactor": "先为当前行为补充针对性测试，再进行小步重构。",
}

_FIRST_STEP_TEMPLATES: dict[str, str] = {
    "code_smell": "先确认重复逻辑是否确实存在，再决定是否提取公共实现。",
    "architecture": "为当前公共接口添加表征测试，锁定现有行为。",
    "maintainability": "识别复杂度最高的职责，将其提取到独立接口中。",
    "refactor": "先为当前行为补充针对性测试，再进行小步重构。",
}

_CAVEAT_TEMPLATES: dict[str, str] = {
    "public_api": "如果该逻辑属于公共 API，变更前需要确认兼容性影响。",
    "generic": "该发现基于结构化信号；行动前请结合生产行为确认。",
}

_TITLE_TEMPLATES: dict[str, str] = {
    "architecture": "架构边界需要审查",
    "code_smell": "代码质量问题需要关注",
    "maintainability": "可维护性风险需要改善",
    "refactor": "重构候选需要评估",
}

_DESCRIPTION_TEMPLATE = "该问题需要关注和审查。"

_CONFIDENCE_RATIONALE_TEMPLATE = "基于提示上下文中提供的证据记录。"

_GENERIC_IMPACT = "该问题可能影响代码质量和后续维护。"
_GENERIC_RECOMMENDATION = "修改代码前先审查引用的证据，确认影响范围。"
_GENERIC_FIRST_STEP = "为引用的边界添加针对性测试，然后审查依赖方向。"
_GENERIC_CAVEAT = "该发现基于结构化信号；行动前请结合生产行为确认。"

_VALIDATION_TEST_REPLACEMENT = "运行测试套件，确认没有新增警告或失败。"


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def _has_chinese(text: str) -> bool:
    """Check if text contains any Chinese characters."""
    return bool(_ZH_CHAR_RE.search(text))


def _is_test_command(text: str) -> bool:
    """Check if text looks like a shell/test command (should stay English)."""
    lower = text.strip().lower()
    return any(lower.startswith(prefix) for prefix in _TEST_COMMAND_PREFIXES)


def is_english_leakage(text: str | None) -> bool:
    """Check if a zh field contains English natural-language leakage.

    Returns True if the field has no Chinese characters and is not
    a pure code/path/command/tech-name/evidence-ref field.

    Heuristic: a zh field with no Chinese characters and multiple
    English words is likely English leakage that should be repaired.
    """
    if not text or not text.strip():
        return False
    if _has_chinese(text):
        return False

    stripped = text.strip()

    # File path (contains separator)
    if "/" in stripped or "\\" in stripped:
        return False

    # Code symbol (snake_case, camelCase, PascalCase, UPPER_SNAKE)
    if _CODE_SYMBOL_RE.match(stripped):
        return False

    # Command (starts with known tool)
    if _is_test_command(stripped):
        return False

    # Evidence ref ([E1], [E2], etc.)
    if _EVIDENCE_REF_RE.match(stripped):
        return False

    # Tech name (Flask, FastAPI, API, etc.)
    if stripped.lower() in _TECH_NAMES:
        return False

    # Single word: check if it's a common English word
    words = stripped.split()
    if len(words) <= 1:
        return stripped.lower() in _COMMON_ENGLISH_WORDS

    # Multiple words, no Chinese — likely English leakage
    return True


# ---------------------------------------------------------------------------
# Field repair
# ---------------------------------------------------------------------------


def repair_zh_field(
    text: str | None,
    field_name: str,
    category: str = "",
) -> str | None:
    """Repair a single zh field if it contains English leakage.

    If the field is English (no Chinese chars), replaces it with a safe
    Chinese template based on category and field_name.

    Returns the original text if it's already Chinese, or a template if
    it was English. Returns None if input is None.
    """
    if text is None:
        return None
    if not is_english_leakage(text):
        return text

    cat = (category or "").strip().lower()

    if field_name == "impact":
        return _IMPACT_TEMPLATES.get(cat, _GENERIC_IMPACT)
    elif field_name == "recommendation":
        return _RECOMMENDATION_TEMPLATES.get(cat, _GENERIC_RECOMMENDATION)
    elif field_name == "first_step":
        return _FIRST_STEP_TEMPLATES.get(cat, _GENERIC_FIRST_STEP)
    elif field_name == "caveat":
        lower_text = (text or "").lower()
        if "public api" in lower_text or "backward compat" in lower_text:
            return _CAVEAT_TEMPLATES["public_api"]
        return _CAVEAT_TEMPLATES.get(cat, _GENERIC_CAVEAT)
    elif field_name == "confidence_rationale":
        return _CONFIDENCE_RATIONALE_TEMPLATE
    elif field_name == "title":
        return _TITLE_TEMPLATES.get(cat, text)
    elif field_name == "description":
        return _DESCRIPTION_TEMPLATE
    else:
        return text


def repair_zh_validation_tests(
    tests: list[str] | None,
    category: str = "",
) -> list[str] | None:
    """Repair validation_tests list if entries contain English leakage.

    Commands and file paths are preserved. English natural-language
    entries are replaced with a generic Chinese test instruction.
    """
    if not tests:
        return tests

    repaired = []
    changed = False
    for test in tests:
        if is_english_leakage(test) and not _is_test_command(test):
            repaired.append(_VALIDATION_TEST_REPLACEMENT)
            changed = True
        else:
            repaired.append(test)
    return repaired if changed else tests


# ---------------------------------------------------------------------------
# Finding-level repair
# ---------------------------------------------------------------------------


def repair_zh_display_fields(finding: ReviewFinding) -> ReviewFinding:
    """Repair all display.zh fields on a finding.

    Validates each zh prose field. If it's English (no Chinese chars),
    replaces with a safe Chinese template based on category.

    Returns a new ReviewFinding with repaired display.zh fields.
    Does NOT modify the original finding.
    """
    if finding.display is None:
        return finding

    zh = finding.display.zh
    if zh is None:
        return finding

    category = finding.category or ""

    repaired_title = repair_zh_field(zh.title, "title", category)
    repaired_desc = repair_zh_field(zh.description, "description", category)
    repaired_rec = repair_zh_field(zh.recommendation, "recommendation", category)
    repaired_impact = repair_zh_field(zh.impact, "impact", category)
    repaired_first_step = repair_zh_field(zh.first_step, "first_step", category)
    repaired_caveat = repair_zh_field(zh.caveat, "caveat", category)
    repaired_conf = repair_zh_field(zh.confidence_rationale, "confidence_rationale", category)
    repaired_tests = repair_zh_validation_tests(zh.validation_tests, category)

    # Check if any field was actually repaired
    changes_made = (
        repaired_title != zh.title
        or repaired_desc != zh.description
        or repaired_rec != zh.recommendation
        or repaired_impact != zh.impact
        or repaired_first_step != zh.first_step
        or repaired_caveat != zh.caveat
        or repaired_conf != zh.confidence_rationale
        or repaired_tests != zh.validation_tests
    )

    if not changes_made:
        return finding

    new_zh = BilingualTextField(
        title=repaired_title,
        description=repaired_desc,
        recommendation=repaired_rec,
        impact=repaired_impact,
        first_step=repaired_first_step,
        validation_tests=repaired_tests or [],
        confidence_rationale=repaired_conf,
        caveat=repaired_caveat,
    )
    new_display = DisplayFields(
        en=finding.display.en,
        zh=new_zh,
    )

    return finding.model_copy(update={"display": new_display})


def repair_zh_findings(findings: list[ReviewFinding]) -> list[ReviewFinding]:
    """Repair display.zh fields on all findings.

    Returns a new list with repaired findings.
    """
    return [repair_zh_display_fields(f) for f in findings]


# ---------------------------------------------------------------------------
# Metadata repair (post-render)
# ---------------------------------------------------------------------------


def repair_zh_metadata(markdown: str) -> str:
    """Repair zh metadata patterns in rendered markdown.

    Fixes evidence appendix labels, repo summary metadata, and
    other English fragments that the rendering pipeline produces
    but doesn't translate.

    This is a targeted cleanup — not a blanket phrase replacement.
    """
    result = markdown

    # Evidence appendix labels (from evidence_display.build_evidence_appendix)
    result = result.replace("* Type：", "* 类型：")
    result = result.replace("* Symbol：", "* 符号：")
    result = result.replace("* Description：", "* 说明：")
    result = result.replace("* Related findings：", "* 关联问题：")

    # Repo summary metadata
    result = result.replace("Python 仓库 with", "Python 仓库，包含")
    result = result.replace("Python source files", "Python 源文件")
    result = result.replace("Python files", "Python 源文件")
    result = result.replace("Supporting modules", "支撑模块")
    result = result.replace("Dependency structure", "依赖结构")
    result = result.replace(
        "The selected evidence highlights",
        "以下证据指出",
    )
    result = result.replace(
        "This evidence was derived from parsed code symbols or structured repository context.",
        "该证据来自已解析的代码符号或结构化仓库上下文。",
    )
    result = result.replace(
        "This evidence was derived",
        "该证据来自",
    )

    # Evidence appendix description/snippet patterns
    result = result.replace(
        "Source snippet was not persisted; only file location and symbol info are available.",
        "源码片段未持久化，仅保留文件位置和符号信息。",
    )
    result = result.replace(
        "Remaining evidence entries were omitted. Re-run the review to see full context.",
        "其余证据已省略，可在重新运行审查后查看完整上下文。",
    )

    return result


# ---------------------------------------------------------------------------
# Validation (for testing and debugging)
# ---------------------------------------------------------------------------


def validate_zh_fields(finding: ReviewFinding) -> list[str]:
    """Validate display.zh fields on a finding.

    Returns a list of field names that contain English leakage.
    Empty list means all zh fields are clean.
    """
    issues: list[str] = []
    if finding.display is None or finding.display.zh is None:
        return issues

    zh = finding.display.zh
    for field_name in (
        "title", "description", "recommendation", "impact",
        "first_step", "caveat", "confidence_rationale",
    ):
        value = getattr(zh, field_name, None)
        if is_english_leakage(value):
            issues.append(field_name)

    for i, test in enumerate(zh.validation_tests or []):
        if is_english_leakage(test) and not _is_test_command(test):
            issues.append(f"validation_tests[{i}]")

    return issues


# ---------------------------------------------------------------------------
# Pipeline entry points
# ---------------------------------------------------------------------------


def prepare_zh_report(
    findings: list[ReviewFinding],
    report_markdown: str,
) -> tuple[list[ReviewFinding], str]:
    """Full zh presentation pipeline — pre-render step.

    1. Repair display.zh fields on all findings
    2. Return repaired findings and unchanged markdown

    The caller should then render the report and call
    finalize_zh_report() on the rendered markdown.
    """
    repaired_findings = repair_zh_findings(findings)
    return repaired_findings, report_markdown


def finalize_zh_report(markdown: str) -> str:
    """Final zh presentation cleanup — post-render step.

    1. Repair metadata patterns (evidence labels, repo summary)
    2. Final normalize_zh_markdown fallback (phrase/label cleanup)

    Call this after rendering the zh report markdown.
    """
    result = repair_zh_metadata(markdown)
    result = normalize_zh_markdown(result)
    return result
