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

_DESCRIPTION_TEMPLATES: dict[str, str] = {
    "architecture": "相关证据显示该区域涉及模块发现、入口识别或公共边界，变更前需要确认现有行为。",
    "code_smell": "相关证据显示该区域存在重复逻辑、复杂职责或维护风险。",
    "maintainability": "相关证据显示该区域后续维护成本较高，建议优先补充测试和边界说明。",
    "refactor": "相关证据显示该区域存在可简化的结构或路径处理逻辑，适合在测试保护下小步重构。",
}

_CONFIDENCE_RATIONALE_TEMPLATE = "基于提示上下文中提供的证据记录。"

_GENERIC_IMPACT = "该问题可能影响代码质量和后续维护。"
_GENERIC_RECOMMENDATION = "修改代码前先审查引用的证据，确认影响范围。"
_GENERIC_FIRST_STEP = "为引用的边界添加针对性测试，然后审查依赖方向。"
_GENERIC_CAVEAT = "该发现基于结构化信号；行动前请结合生产行为确认。"

_VALIDATION_TEST_REPLACEMENT = "运行测试套件，确认没有新增警告或失败。"

# ---------------------------------------------------------------------------
# Indexer metadata English→Chinese repairs (post-render)
# ---------------------------------------------------------------------------

_INDEXER_METADATA_REPAIRS: list[tuple[str, str]] = [
    # Full phrase patterns from indexer.py (longest first)
    (
        r"resolved internal relationships",
        "已解析内部依赖关系",
    ),
    (
        r"modules participate in cycles",
        "个模块参与循环依赖",
    ),
    (
        r"hubs:",
        "依赖枢纽：",
    ),
    (
        r"Entry points:",
        "入口文件：",
    ),
    (
        r"Core modules:",
        "核心模块：",
    ),
    (
        r"Supporting modules:",
        "支撑模块：",
    ),
    (
        r"Dependency structure:",
        "依赖结构：",
    ),
    # "analyzed X and skipped Y" pattern
    (
        r"analyzed\s+(\d+)\s+and\s+skipped\s+(\d+)",
        r"已分析 \1 个，已跳过 \2 个",
    ),
    # "Python repository with N Python files"
    (
        r"Python repository with\s+(\d+)\s+Python files",
        r"Python 仓库，包含 \1 个 Python 源文件",
    ),
    # Standalone "Python files" after the above has run
    (
        r"Python files",
        "Python 源文件",
    ),
]

# ---------------------------------------------------------------------------
# MiMo English sentence starters (final gate)
# ---------------------------------------------------------------------------

_MIMO_ENGLISH_SENTENCE_STARTERS: tuple[str, ...] = (
    "The test cases",
    "The tests",
    "Consider simplifying",
    "Consider rewriting",
    "Consider refactoring",
    "May lead to",
    "Might lead to",
    "Could lead to",
    "Future changes to",
    "Future modifications",
    "Need to ensure",
    "Needs to ensure",
    "This is an established",
    "The current implementation",
    "The selected evidence",
    "This evidence was derived",
    "If this boundary",
    "shared dependencies",
    "This finding is based",
    "Evidence-grounded",
    "Execution begins",
    "The analysis identified",
    "This pattern",
    "This approach",
    "This code",
    "These changes",
    "This refactor",
    "The codebase",
    "The module",
    "The function",
    "The class",
    "Note that",
    "Please note",
    "It is important",
    "It should be",
    "It is recommended",
    "You should",
    "We recommend",
    "We suggest",
    "One option",
    "One approach",
    "A possible",
    "A potential",
    "An alternative",
    "Instead of",
    "Rather than",
    "In order to",
    "As a result",
    "Due to the",
    "Because of",
    "In the future",
    "Going forward",
    "For example",
    "For instance",
    # V3.10 MiMo English prose starters
    "This is a long-standing",
    "This is a public API",
    "Should be done carefully",
    "Run tests for",
    "the path manipulation",
    "creates inconsistent",
    "makes the code harder",
    "changing the discovery",
    "that might break",
    "that don't inherit",
    "session implementations",
    "inherit from ABC",
    "pathlib.PurePath",
    "os.path APIs",
    "the discovery mechanism",
    "existing applications",
    "backward compatibility",
    "request processing",
    "API usage",
    "code harder",
)


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


# ---------------------------------------------------------------------------
# Mixed Chinese+English prose detection
# ---------------------------------------------------------------------------

# Consecutive common-English-word threshold for mixed-line detection
_MIXED_PROSE_THRESHOLD = 3


def _strip_allowed_tokens(text: str) -> str:
    """Remove allowed English tokens from text, leaving only prose.

    Strips: inline code, evidence refs, file paths, tech names, code symbols.
    Plain lowercase English words (prose) are preserved so they can be
    counted by the consecutive-word detector.
    """
    result = text
    # 1. Remove inline code spans
    result = re.sub(r"`[^`]+`", "", result)
    # 2. Remove evidence refs [E1], [E2], etc.
    result = _EVIDENCE_REF_RE.sub("", result)
    # 3. Remove file paths (tokens containing / or \)
    result = re.sub(r"\S*[/\\]\S*", "", result)
    # 4. Remove tech names (longest first, word boundary)
    for name in sorted(_TECH_NAMES, key=len, reverse=True):
        result = re.sub(
            rf"(?<![a-zA-Z0-9_]){re.escape(name)}(?![a-zA-Z0-9_])",
            "",
            result,
            flags=re.IGNORECASE,
        )
    # 5. Remove code symbols — but keep plain lowercase words (prose).
    #    Strip: snake_case (has _), camelCase/PascalCase (has uppercase
    #    after first char), UPPER_SNAKE (all uppercase, len > 1).
    def _strip_code_sym(match: re.Match[str]) -> str:
        token = match.group(0)
        if "_" in token:  # snake_case
            return ""
        if any(c.isupper() for c in token[1:]):  # camelCase / PascalCase
            return ""
        if token.isupper() and len(token) > 1:  # UPPER_SNAKE
            return ""
        return token  # plain lowercase word — keep as potential prose

    result = re.sub(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", _strip_code_sym, result)
    return result


def _has_english_prose(text: str) -> bool:
    """Check if text contains English natural-language prose.

    Returns True if, after stripping allowed tokens (tech names, code
    symbols, paths, evidence refs, inline code), the text still contains
    3+ consecutive common English words.

    This catches mixed Chinese+English sentences like:
      "以下证据指出 a repository concern that should be reviewed"
    where the English portion is prose, not code.
    """
    cleaned = _strip_allowed_tokens(text)
    words = re.findall(r"[a-zA-Z]+", cleaned)
    consecutive = 0
    for w in words:
        if w.lower() in _COMMON_ENGLISH_WORDS:
            consecutive += 1
            if consecutive >= _MIXED_PROSE_THRESHOLD:
                return True
        else:
            consecutive = 0
    return False


def is_english_leakage(text: str | None) -> bool:
    """Check if a zh field contains English natural-language leakage.

    Returns True if the field contains English prose — even when mixed
    with Chinese characters.  Pure code/path/command/tech-name/evidence-ref
    fields are never flagged.

    Detection has two paths:
    1. Pure English (no Chinese chars): multi-word text that is not a
       code symbol, path, command, tech name, or evidence ref.
    2. Mixed Chinese+English: text with Chinese chars that also contains
       3+ consecutive common English words after stripping allowed tokens.
    """
    if not text or not text.strip():
        return False

    stripped = text.strip()

    # --- Path 1: pure English (no Chinese chars) ---
    if not _has_chinese(stripped):
        # File path (contains separator) — only if the entire text looks like a path
        if ("/" in stripped or "\\" in stripped) and len(stripped.split()) <= 4:
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

    # --- Path 2: mixed Chinese+English ---
    # Even with Chinese present, check for English prose leakage
    return _has_english_prose(stripped)


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
        return _DESCRIPTION_TEMPLATES.get(cat, _DESCRIPTION_TEMPLATE)
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
    display = finding.display or DisplayFields()
    zh = display.zh

    category = finding.category or ""

    repaired_title = repair_zh_field(zh.title or finding.title, "title", category)
    repaired_desc = repair_zh_field(zh.description or finding.description, "description", category)
    repaired_rec = repair_zh_field(zh.recommendation or finding.recommendation, "recommendation", category)
    repaired_impact = repair_zh_field(zh.impact or finding.impact, "impact", category)
    repaired_first_step = repair_zh_field(zh.first_step or finding.first_step, "first_step", category)
    repaired_caveat = repair_zh_field(zh.caveat or finding.caveat, "caveat", category)
    repaired_conf = repair_zh_field(
        zh.confidence_rationale or finding.confidence_rationale,
        "confidence_rationale",
        category,
    )
    source_tests = zh.validation_tests or finding.validation_tests
    repaired_tests = repair_zh_validation_tests(source_tests, category)

    # Check if any field was actually repaired
    changes_made = (
        finding.display is None
        or repaired_title != zh.title
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
        en=display.en,
        zh=new_zh,
    )

    return finding.model_copy(update={"display": new_display})


def repair_zh_findings(findings: list[ReviewFinding]) -> list[ReviewFinding]:
    """Repair display.zh fields on all findings.

    Returns a new list with repaired findings.
    """
    return [repair_zh_display_fields(f) for f in findings]


# ---------------------------------------------------------------------------
# Final zh markdown gate
# ---------------------------------------------------------------------------


def assert_no_english_natural_language_zh(markdown: str) -> list[str]:
    """Final gate: detect English natural-language leakage in zh markdown.

    Ignores code blocks, inline code, file paths, code symbols, tech names,
    and evidence refs.  Catches English prose even when mixed with Chinese.

    Returns a list of detected leak fragments.  Empty list = clean.
    Useful for testing and post-render validation.
    """
    leaks: list[str] = []

    # Split into code blocks and non-code segments
    code_block_re = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)
    segments: list[tuple[str, bool]] = []
    last_end = 0
    for match in code_block_re.finditer(markdown):
        if match.start() > last_end:
            segments.append((markdown[last_end:match.start()], False))
        segments.append((match.group(0), True))
        last_end = match.end()
    if last_end < len(markdown):
        segments.append((markdown[last_end:], False))

    for segment_text, is_code in segments:
        if is_code:
            continue

        # Replace inline code with placeholders
        cleaned = re.sub(r"`[^`]+`", "", segment_text)

        for line in cleaned.split("\n"):
            line_s = line.strip()
            if not line_s:
                continue

            # Skip markdown headings
            if re.match(r"^#{1,6}\s", line_s):
                continue

            # Skip table rows
            if line_s.startswith("|"):
                continue

            # Check for English prose using the mixed-text detector
            if _has_english_prose(line_s):
                leaks.append(line_s[:120])

            # Also check for known English sentence starters
            for starter in _MIMO_ENGLISH_SENTENCE_STARTERS:
                if line_s.startswith(starter):
                    if line_s[:120] not in leaks:
                        leaks.append(line_s[:120])
                    break

    return leaks


# ---------------------------------------------------------------------------
# Mixed-line repair helpers
# ---------------------------------------------------------------------------


def _repair_mixed_zh_line(line: str) -> str | None:
    """Repair a single line that mixes Chinese and English prose.

    Returns the repaired line, or None if no repair is needed.
    Strategy: remove common English prose words, keep Chinese, tech terms,
    code symbols, paths, evidence refs, and non-common English words.
    """
    if not _has_chinese(line) or not _has_english_prose(line):
        return None

    # Split into tokens, preserving spacing
    tokens = re.findall(r"\S+|\s+", line)
    kept: list[str] = []
    for token in tokens:
        if token.isspace():
            kept.append(token)
            continue

        # Extract the alphabetic core of the token
        bare = re.sub(r"[^a-zA-Z]", "", token)
        if not bare:
            kept.append(token)
            continue

        # Keep tokens that are allowed English
        lower = bare.lower()

        # Tech names — keep
        if lower in _TECH_NAMES:
            kept.append(token)
            continue

        # Evidence refs — keep
        if _EVIDENCE_REF_RE.match(token.strip()):
            kept.append(token)
            continue

        # File paths — keep
        if "/" in token or "\\" in token:
            kept.append(token)
            continue

        # Code symbols — keep
        if _CODE_SYMBOL_RE.match(bare):
            kept.append(token)
            continue

        # Common English prose word — drop
        if lower in _COMMON_ENGLISH_WORDS:
            continue

        # Unknown English word — keep (might be a proper noun or domain term)
        if re.match(r"[a-zA-Z]", bare):
            kept.append(token)
            continue

        # Non-English token (Chinese, punctuation, numbers) — keep
        kept.append(token)

    repaired = "".join(kept)
    # Clean up double spaces
    repaired = re.sub(r"[ \t]{2,}", " ", repaired).strip()
    if repaired and repaired != line.strip():
        return repaired
    return None


# ---------------------------------------------------------------------------
# Metadata repair (post-render)
# ---------------------------------------------------------------------------


def repair_zh_metadata(markdown: str) -> str:
    """Repair zh metadata patterns in rendered markdown.

    Fixes evidence appendix labels, repo summary metadata, and
    other English fragments that the rendering pipeline produces
    but doesn't translate.

    Four-layer approach:
    1. Full-sentence replacements (before partial matches corrupt them)
    2. Indexer metadata repairs (resolved relationships, hubs, cycles)
    3. Phrase-level targeted replacements
    4. Generic mixed-line sweep (catch-all for remaining English prose)
    """
    result = markdown

    # === Layer 0: [[E?]] double-bracket cleanup ===
    # MiMo may produce [[E?]] instead of [E?]; normalize to [E?]
    result = result.replace("[[E?]]", "[E?]")
    # Also fix any other double-bracket evidence refs like [[E1]]
    result = re.sub(r"\[\[E(\d+)\]\]", r"[E\1]", result)

    # === Layer 1: full-sentence replacements (longest first) ===

    result = result.replace(
        "This evidence was derived from parsed code symbols or structured repository context.",
        "该证据来自已解析的代码符号或结构化仓库上下文。",
    )
    result = result.replace(
        "Source snippet was not persisted; only file location and symbol info are available.",
        "源码片段未持久化，仅保留文件位置和符号信息。",
    )
    result = result.replace(
        "Remaining evidence entries were omitted. Re-run the review to see full context.",
        "其余证据已省略，可在重新运行审查后查看完整上下文。",
    )
    # Catch "The selected evidence highlights <anything>." — full sentence
    result = re.sub(
        r"The selected evidence highlights[^。\n]*?(?:\.)",
        "以下证据指出需要关注的仓库问题。",
        result,
    )
    # Catch "This evidence was derived <anything>." — partial after full above
    result = re.sub(
        r"This evidence was derived[^。\n]*?(?:\.)",
        "该证据来自已解析的代码符号或结构化仓库上下文。",
        result,
    )
    # Catch mixed "以下证据指出 a repository concern..." (from prior partial fix)
    result = re.sub(
        r"以下证据指出\s+(?:a\s+)?(?:repository\s+)?concern[^。\n]*?(?:入口文件|文件|。|$)",
        "以下证据指出需要在变更入口文件前审查的仓库问题。",
        result,
    )
    # Catch "If this boundary is part of a 公共 API, changing it may break..."
    result = re.sub(
        r"If this boundary is part of[^。\n]*?(?:consumers|下游)[^。\n]*?(?:\.|。|$)",
        "如果该边界属于公共 API，变更可能影响下游使用方。",
        result,
    )
    # Catch "shared dependencies, or refactoring boundaries"
    result = result.replace(
        "shared dependencies, or refactoring boundaries",
        "共享依赖或重构边界",
    )

    # === Layer 1.5: indexer metadata repairs ===
    # The indexer generates English metadata strings that leak into zh reports.
    # Apply regex replacements in order (longest/most-specific first).
    for pattern, replacement in _INDEXER_METADATA_REPAIRS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    # === Layer 2: phrase-level targeted replacements ===

    # Evidence appendix labels (from evidence_display.build_evidence_appendix)
    result = result.replace("* Type：", "* 类型：")
    result = result.replace("* Symbol：", "* 符号：")
    result = result.replace("* Description：", "* 说明：")
    result = result.replace("* Related findings：", "* 关联问题：")

    # Repo summary metadata (remaining after indexer repairs)
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
        "This evidence was derived",
        "该证据来自",
    )

    # === Layer 3: generic mixed-line sweep ===
    # After targeted fixes, catch any remaining mixed Chinese+English prose lines.

    code_block_re = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)
    segments: list[tuple[str, bool]] = []
    last_end = 0
    for match in code_block_re.finditer(result):
        if match.start() > last_end:
            segments.append((result[last_end:match.start()], False))
        segments.append((match.group(0), True))
        last_end = match.end()
    if last_end < len(result):
        segments.append((result[last_end:], False))

    rebuilt_parts: list[str] = []
    for segment_text, is_code in segments:
        if is_code:
            rebuilt_parts.append(segment_text)
            continue

        lines = segment_text.split("\n")
        repaired_lines: list[str] = []
        for line in lines:
            # Skip table rows and headings (structural, not prose)
            stripped = line.strip()
            if stripped.startswith("|") or re.match(r"^#{1,6}\s", stripped):
                repaired_lines.append(line)
                continue

            repaired = _repair_mixed_zh_line(line)
            repaired_lines.append(repaired if repaired is not None else line)

        rebuilt_parts.append("\n".join(repaired_lines))

    return "".join(rebuilt_parts)


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
