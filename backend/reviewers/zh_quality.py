"""Chinese report quality guard for CodePilot.

Deterministic rule-based checks to detect and fix English natural-language
leakage in Chinese reports. Does NOT call any LLM — all logic is regex/string
based.

Allowed English in zh reports:
  - file paths: src/flask/app.py
  - code symbols: send_static_file, OpenAICompatibleClient
  - commands: pytest tests/test_cli.py
  - framework/library names: Flask, FastAPI, React, SQLite
  - model/provider names: MiMo, OpenAI
  - evidence display refs: [E1], [E2]
  - code blocks (``` ... ```)

Disallowed English in zh reports:
  - English natural-language sentences
  - English labels like Recommendation, Impact, Caveat, Grounding
  - severity values like medium/low/high shown as user-facing text
  - internal phrases like "validated symbols"
  - raw ev_* IDs in user-facing report
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Allowed English tokens (not flagged as leakage)
# ---------------------------------------------------------------------------

# Common tech/framework/library names that are acceptable in zh reports
_TECH_NAMES: set[str] = {
    "api", "cli", "css", "dns", "dom", "git", "gpu", "html", "http",
    "https", "ide", "json", "jwt", "lts", "npm", "oauth", "orm", "pdf",
    "rest", "rpc", "sdk", "sql", "ssh", "ssl", "tcp", "tls", "udp",
    "ui", "url", "utf", "uuid", "xml", "yaml", "yml",
    "ast", "ci", "cd", "pr", "mr", "wip", "async", "await", "class", "def", "import", "return", "yield",
    "null", "none", "true", "false", "nan", "inf",
    "utf-8", "utf8", "ascii", "base64", "hex", "sha256", "md5",
    # Framework/library names
    "flask", "fastapi", "django", "react", "vue", "angular", "nextjs",
    "next", "express", "spring", "rails", "laravel", "sqlite", "mysql",
    "postgresql", "redis", "kafka", "rabbitmq", "docker", "kubernetes",
    "nginx", "apache", "terraform", "ansible", "webpack", "vite", "rollup",
    "babel", "eslint", "prettier", "pytest", "jest", "mocha", "vitest",
    "tailwind", "bootstrap", "sass", "less",
    # Model/provider names
    "mimo", "openai", "anthropic", "gemini", "claude", "gpt", "llm",
    "codex", "copilot",
    # CodePilot internal
    "codepilot", "agent", "agents",
}

# Patterns that look like code identifiers (snake_case, camelCase, etc.)
_CODE_SYMBOL_RE = re.compile(
    r"^[a-z_][a-z0-9_]*$"  # snake_case
    r"|^[a-z][a-zA-Z0-9]*$"  # camelCase
    r"|^[A-Z][a-z][a-zA-Z0-9]+$"  # PascalCase (must have 2+ lower after initial upper)
    r"|^[A-Z_][A-Z0-9_]*$"  # UPPER_SNAKE_CASE
)

# File path pattern: contains / or \ and looks like a path
_FILE_PATH_RE = re.compile(
    r"[/\\]"  # has separator
    r"|^\w+\.\w+$"  # or simple filename.ext
    r"|^\.\./"  # or relative path
    r"|^src/"  # or common source dirs
    r"|^test"
    r"|^docs?/"
    r"|^backend/"
    r"|^frontend/"
    r"|^scripts/"
    r"|^config/"
)

# Command patterns
_COMMAND_PREFIXES = (
    "pytest", "npm", "python", "pip", "git", "docker", "make", "cargo",
    "go ", "yarn", "pnpm", "npx", "node", "deno", "bun", "curl", "wget",
    "chmod", "mkdir", "rm ", "mv ", "cp ", "ls ", "cat ", "grep", "sed",
    "awk", "find", "powershell", "cmd", "bash", "sh ",
)

# Evidence display ref pattern: [E1], [E2], etc.
_EVIDENCE_REF_RE = re.compile(r"^\[E\d+\]$")

# Raw evidence ID pattern
_RAW_EV_RE = re.compile(r"\bev_[0-9a-f]{20}\b")


def is_allowed_english_token(token: str) -> bool:
    """Check if an English token is allowed in zh reports.

    Returns True for file paths, code symbols, commands, tech names,
    and evidence refs.
    """
    t = token.strip()
    if not t:
        return True

    lower = t.lower()

    # Evidence refs: [E1], [E2]
    if _EVIDENCE_REF_RE.match(t):
        return True

    # Tech names
    if lower in _TECH_NAMES:
        return True

    # Common English words are NOT code symbols (even if they match snake_case etc.)
    if lower in _COMMON_ENGLISH_WORDS:
        return False

    # Code symbols (snake_case, camelCase, PascalCase, UPPER_SNAKE)
    if _CODE_SYMBOL_RE.match(t):
        return True

    # File paths
    if _FILE_PATH_RE.search(t):
        return True

    # Commands
    if any(lower.startswith(prefix) for prefix in _COMMAND_PREFIXES):
        return True

    return False


# ---------------------------------------------------------------------------
# English natural language detection
# ---------------------------------------------------------------------------

# Common English words that indicate natural language (not code/tech)
_COMMON_ENGLISH_WORDS: set[str] = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "must",
    "this", "that", "these", "those", "it", "its",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "under", "over", "up", "down", "out", "off",
    "and", "but", "or", "nor", "not", "so", "yet",
    "if", "then", "else", "when", "while", "until", "unless", "because",
    "since", "although", "though", "whereas", "whether",
    "which", "who", "whom", "whose", "what", "where", "how",
    "all", "each", "every", "both", "few", "more", "most", "other",
    "some", "such", "no", "any", "only", "same", "very",
    "also", "just", "still", "already", "even", "now", "here",
    "there", "why", "about", "against", "along", "among", "around", "behind",
    "beside", "beyond", "despite", "except", "inside", "near", "outside",
    "per", "than", "toward", "upon", "within", "without",
    # Common verbs in technical writing
    "require", "requires", "required", "change", "changes", "changed",
    "identify", "identified", "identifies", "consider", "considered",
    "rewrite", "rewriting", "reduce", "reduced", "reduces",
    "increase", "increased", "increases",
    "create", "created", "creates", "update", "updated", "updates",
    "modify", "modified", "modifies",
    "remove", "removed", "removes", "add", "added", "adds",
    "use", "used", "uses", "make", "made", "makes",
    "run", "running", "runs", "check", "checked", "checks",
    "test", "tested", "tests",
    "lead", "leads", "affect", "affects", "impact", "impacts",
    "improve", "improved", "improves", "maintain", "maintained",
    "extend", "extended", "extends",
    "debug", "debugging", "detect", "detected", "detects",
    "delegate", "delegates",
    # Common adjectives/adverbs
    "complex", "simple", "common", "specific", "general", "internal",
    "external", "current", "existing", "new", "old", "multiple",
    "single", "several", "various", "different", "similar", "related",
    "relevant", "important", "critical", "necessary", "possible",
    "available", "consistent", "compatible", "additional", "alternative",
    "potential", "structural", "behavioral", "functional", "technical",
    "unfamiliar", "intentional", "correct", "incorrect", "valid",
    "invalid", "safe", "unsafe", "local", "global", "public", "private",
    "protected", "static", "dynamic", "explicit", "implicit",
    "likely", "unlikely", "probably", "possibly", "certainly",
    "further", "furthermore", "however", "therefore", "otherwise",
    "instead", "rather", "quite", "nearly", "almost", "hardly",
    "particularly", "especially", "typically", "usually", "often",
    "sometimes", "always", "never", "rarely", "frequently",
    # Common nouns in technical writing
    "code", "function", "method", "class", "module", "file", "path",
    "directory", "folder", "component", "service", "controller", "model",
    "view", "route", "handler", "middleware", "plugin", "library",
    "framework", "database", "table", "record", "field", "schema",
    "query", "request", "response", "client", "server", "endpoint",
    "interface", "abstract", "instance", "object", "array", "list",
    "string", "number", "value", "type", "parameter", "argument",
    "variable", "constant", "expression", "statement", "block", "scope",
    "context", "state", "data", "input", "output", "error", "exception",
    "behavior", "pattern", "structure", "architecture", "design",
    "implementation", "dependency", "dependencies", "risk", "issue",
    "problem", "solution", "approach", "strategy", "technique",
    "readability", "maintainability", "performance", "security",
    "compatibility", "functionality", "reliability", "availability",
    "scalability", "flexibility", "extensibility",
    "developers", "developer", "maintainer", "maintainers",
    "user", "users", "consumer", "consumers", "caller",
    "analysis", "review", "finding", "evidence", "recommendation",
    "validation", "verification", "coverage", "duplication",
    "testing", "spec", "specification",
    "bug", "bugs", "defect", "defects", "vulnerability",
    "refactor", "refactoring", "migration", "upgrade",
    "production", "development", "staging", "environment",
    "configuration", "setting", "option", "flag", "documentation", "comment", "annotation", "metadata",
    "version", "release", "deployment", "build", "compilation",
    "branch", "commit", "merge", "pull", "push", "fetch", "clone",
    "operation", "action", "task", "process", "workflow", "pipeline",
    "step", "phase", "stage", "iteration", "cycle",
    "boundary", "boundaries", "range", "limit", "threshold",
    "entry", "entries", "exit", "return", "throw", "catch", "finally",
    "source", "target", "destination", "origin", "reference",
    "symbol", "symbols", "token", "identifier", "name", "namespace",
    "snippet", "excerpt", "fragment", "portion", "section", "segment",
    "properly", "correctly", "safely", "efficiently", "effectively",
    "significantly", "substantially", "considerably",
    # Additional common nouns/verbs that match identifier patterns
    "locations", "location", "risks", "effort", "efforts",
    "approaches", "methods", "modules",
    "options", "issues", "actions",
    "steps", "areas", "levels",
    "results", "values", "types",
    "items", "indices",
    "messages", "warnings",
    "configs",
    "resources", "requests",
    "responses", "events",
    "contexts", "scopes", "instances",
    "interfaces",
}

# Minimum number of common English words in a fragment to flag as leakage
_LEAK_WORD_THRESHOLD = 4

# Known English label patterns (exact match after stripping)
_ENGLISH_LABEL_PATTERNS: list[str] = [
    "Recommendation:",
    "Impact:",
    "First step:",
    "Validation tests:",
    "Caveat:",
    "Grounding:",
    "Category:",
    "Files:",
    "Evidence:",
    "Severity:",
    "Confidence:",
    "Status:",
    "Recommendation",
    "Impact",
    "First step",
    "Validation tests",
    "Caveat",
    "Grounding",
    "Category",
    "Files",
    "Evidence",
    "Severity",
    "Confidence",
]

# Specific English phrases commonly generated by MiMo that should be replaced
_PHRASE_REPLACEMENTS: dict[str, str] = {
    # Action/analysis phrases
    "Changes require updates in multiple locations, increasing bug risk and maintenance effort.":
        "变更需要同时修改多个位置，会增加遗漏、缺陷和维护成本。",
    (
        "Identify if a common base class exists or create a helper function "
        "that both Flask app and Blueprint classes can delegate to."
    ): "先确认是否存在可复用的公共基类；如果没有，可提取一个辅助函数，让 Flask app 和 Blueprint 共同复用。",
    "Reduced readability for developers unfamiliar with recursion":
        "对不熟悉递归的维护者来说，可读性会下降。",
    "Consider rewriting using an iterative approach":
        "可以考虑改为迭代写法，以提升可读性。",
    "This duplication may be intentional":
        "这种重复可能是出于兼容性或公共 API 设计考虑。",
    "Complex code increases risk of bugs and makes it harder to extend or debug.":
        "复杂代码会增加缺陷风险，也会让后续扩展和调试更困难。",
    "Could lead to incorrect module detection, affecting CLI commands.":
        "可能导致模块识别错误，从而影响 CLI 命令行为。",
    "validated symbols": "已验证符号",
    "Changes require updates in multiple locations":
        "变更需要同时修改多个位置",
    "increasing bug risk and maintenance effort":
        "会增加遗漏、缺陷和维护成本",
    "Reduced readability for developers unfamiliar with":
        "对不熟悉该代码的维护者来说，可读性会下降",
    "Consider rewriting using an iterative approach to improve readability":
        "可以考虑改为迭代写法，以提升可读性",
    "This duplication may be intentional for backward compatibility":
        "这种重复可能是出于向后兼容性考虑",
    "Complex code increases the risk of bugs":
        "复杂代码会增加缺陷风险",
    "Could lead to incorrect module detection":
        "可能导致模块识别错误",
    "Path detection is critical for":
        "路径识别对于以下功能很关键：",
    "public API backward compatibility":
        "公共 API 向后兼容性",
    "backward compatibility": "向后兼容性",
    "public API": "公共 API",
}

# English label → Chinese label replacements (for inline text, not bold labels)
_INLINE_LABEL_REPLACEMENTS: dict[str, str] = {
    "Recommendation": "建议",
    "Impact": "影响",
    "First step": "建议先做",
    "Validation tests": "验证方式",
    "Caveat": "注意事项",
    "Grounding": "证据说明",
    "Category": "问题类型",
    "Severity": "严重性",
    "Confidence": "置信度",
    "validated symbols": "已验证符号",
}

# Severity value replacements (for user-facing text in zh reports)
_SEVERITY_REPLACEMENTS: dict[str, str] = {
    "medium": "中",
    "low": "低",
    "high": "高",
    "info": "信息",
    "informational": "信息",
    "critical": "严重",
}

# Status value replacements
_STATUS_REPLACEMENTS: dict[str, str] = {
    "completed": "已完成",
    "validated": "已验证",
    "failed": "失败",
    "skipped": "已跳过",
    "pending": "等待中",
    "running": "运行中",
    "not_applicable": "不适用",
}


def _strip_code_blocks(markdown: str) -> list[tuple[str, bool]]:
    """Split markdown into (text, is_code_block) segments.

    Code blocks (``` ... ```) are marked as is_code_block=True.
    """
    segments: list[tuple[str, bool]] = []
    pattern = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)
    last_end = 0
    for match in pattern.finditer(markdown):
        # Text before code block
        if match.start() > last_end:
            segments.append((markdown[last_end:match.start()], False))
        # Code block itself
        segments.append((match.group(0), True))
        last_end = match.end()
    # Remaining text
    if last_end < len(markdown):
        segments.append((markdown[last_end:], False))
    return segments


def _strip_inline_code(text: str) -> str:
    """Replace inline code spans with placeholders for analysis."""
    return re.sub(r"`[^`]+`", "§CODE§", text)


def _count_common_english_words(text: str) -> int:
    """Count common English words in text (excluding code placeholders)."""
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return sum(1 for w in words if w in _COMMON_ENGLISH_WORDS)


def detect_english_natural_language_leak(text: str) -> list[str]:
    """Detect English natural-language fragments in Chinese report text.

    Returns a list of detected leak fragments. Empty list means no leaks.
    Only examines non-code-block text. Inline code spans are excluded from
    analysis.

    Heuristic: a fragment with 4+ common English words (outside code blocks
    and inline code) is likely English natural language.
    """
    leaks: list[str] = []
    segments = _strip_code_blocks(text)

    for segment_text, is_code in segments:
        if is_code:
            continue

        # Replace inline code with placeholders
        cleaned = _strip_inline_code(segment_text)

        # Split into lines and check each line
        for line in cleaned.split("\n"):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Skip markdown headings (already handled by localization)
            if re.match(r"^#{1,6}\s", line_stripped):
                continue

            # Skip table rows
            if line_stripped.startswith("|"):
                continue

            # Skip list items that are just code/file refs
            if re.match(r"^[-*]\s+§CODE§", line_stripped):
                continue

            # Check for English label patterns at line start
            for label in _ENGLISH_LABEL_PATTERNS:
                if line_stripped.startswith(label):
                    leaks.append(line_stripped[:100])
                    break
            else:
                # Check word count
                word_count = _count_common_english_words(line_stripped)
                if word_count >= _LEAK_WORD_THRESHOLD:
                    # Verify it's mostly English (not a mixed Chinese+English line)
                    chinese_chars = len(re.findall(r"[一-鿿]", line_stripped))
                    total_alpha = len(re.findall(r"[a-zA-Z]", line_stripped))
                    # If there are Chinese chars, it's likely intentional bilingual content
                    if chinese_chars == 0 and total_alpha > 10:
                        leaks.append(line_stripped[:100])

    return leaks


def normalize_zh_text(text: str) -> str:
    """Normalize a single text field for Chinese display.

    Applies phrase and label replacements. Does NOT modify code blocks
    or inline code spans.
    """
    result = text

    # Apply phrase replacements (longest first)
    for en, zh in sorted(_PHRASE_REPLACEMENTS.items(), key=lambda x: -len(x[0])):
        result = result.replace(en, zh)

    return result


def normalize_zh_markdown(markdown: str) -> str:
    """Normalize Chinese markdown report for quality.

    - Replaces known English phrases with Chinese equivalents
    - Replaces English labels with Chinese equivalents
    - Preserves code blocks, inline code, file paths, commands
    - Handles raw ev_* IDs (replaces with [E?] if no display map)
    - Translates severity/status values in non-code context
    """
    segments = _strip_code_blocks(markdown)
    result_parts: list[str] = []

    for segment_text, is_code in segments:
        if is_code:
            result_parts.append(segment_text)
            continue

        result = segment_text

        # Apply phrase replacements (longest first to avoid partial matches)
        for en, zh in sorted(_PHRASE_REPLACEMENTS.items(), key=lambda x: -len(x[0])):
            result = result.replace(en, zh)

        # Apply inline label replacements (within non-code text)
        # Use word-boundary-aware replacement for labels
        for en_label, zh_label in _INLINE_LABEL_REPLACEMENTS.items():
            # Replace "Label:" pattern at line start or after bullet
            result = re.sub(
                rf"(?<![a-zA-Z]){re.escape(en_label)}(?::(?= ))?",
                zh_label,
                result,
            )

        # Translate severity values in non-code context
        # Pattern: standalone severity words (not inside backticks or table headers)
        for en_sev, zh_sev in _SEVERITY_REPLACEMENTS.items():
            # In parenthetical: "(medium)" → "（中）" (half-width input)
            result = result.replace(f"({en_sev})", f"（{zh_sev}）")
            # Also handle full-width parentheses: "（medium）" → "（中）"
            result = result.replace(f"（{en_sev}）", f"（{zh_sev}）")
            # After Chinese label: "严重性：medium" → "严重性：中"
            result = re.sub(
                rf"(严重性[：:])\s*{re.escape(en_sev)}\b",
                rf"\1{zh_sev}",
                result,
            )
            # In table cells: "| medium |" → "| 中 |"
            result = result.replace(f"| {en_sev} |", f"| {zh_sev} |")
            result = result.replace(f"| {en_sev}|", f"| {zh_sev}|")

        # Translate status values in non-code context
        for en_st, zh_st in _STATUS_REPLACEMENTS.items():
            # Half-width and full-width parentheses
            result = result.replace(f"({en_st})", f"（{zh_st}）")
            result = result.replace(f"（{en_st}）", f"（{zh_st}）")
            result = re.sub(
                rf"(状态[：:])\s*{re.escape(en_st)}\b",
                rf"\1{zh_st}",
                result,
            )
            result = result.replace(f"| {en_st} |", f"| {zh_st} |")
            result = result.replace(f"| {en_st}|", f"| {zh_st}|")

        # Replace raw ev_* IDs that have no display mapping with [E?]
        result = _RAW_EV_RE.sub("[E?]", result)

        result_parts.append(result)

    return "".join(result_parts)


def redact_or_replace_raw_evidence_ids(
    markdown: str,
    display_map: object | None = None,
) -> str:
    """Replace raw ev_* IDs in markdown with display refs.

    If a display_map is provided (must have ref_bracket method), uses it
    to map ev_* → [E1]/[E2]. Unknown IDs become [E?].
    If no display_map, all ev_* become [E?].
    """
    if display_map is not None and hasattr(display_map, "ref_bracket"):
        def _replace(match: re.Match[str]) -> str:
            return display_map.ref_bracket(match.group(0))
        return _RAW_EV_RE.sub(_replace, markdown)
    else:
        return _RAW_EV_RE.sub("[E?]", markdown)


def assert_no_obvious_zh_leak(markdown: str) -> list[str]:
    """Check zh markdown for obvious English leakage.

    Returns a list of detected issues. Empty list means the report
    passes quality checks. Useful for testing.
    """
    issues: list[str] = []

    # Check for raw ev_* IDs
    ev_matches = _RAW_EV_RE.findall(markdown)
    if ev_matches:
        issues.append(f"Raw ev_* IDs found: {ev_matches[:3]}")

    # Check for English natural language leaks
    leaks = detect_english_natural_language_leak(markdown)
    for leak in leaks:
        issues.append(f"English leak: {leak}")

    # Check for untranslated English labels in non-code text
    segments = _strip_code_blocks(markdown)
    for segment_text, is_code in segments:
        if is_code:
            continue
        for label in _ENGLISH_LABEL_PATTERNS:
            # Check for bold labels: **Recommendation:**
            if f"**{label}**" in segment_text or f"**{label}" in segment_text:
                issues.append(f"Untranslated bold label: {label}")
            # Check for bare labels at line start
            for line in segment_text.split("\n"):
                stripped = line.strip()
                if stripped.startswith(f"{label}:") or stripped.startswith(f"{label}："):
                    issues.append(f"Untranslated label at line start: {label}")
                    break

    return issues
