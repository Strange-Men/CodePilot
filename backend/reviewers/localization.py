"""Localization support for CodePilot review reports.

Provides deterministic Chinese translations for report headings and labels.
Agent analysis remains English/canonical — this module only translates
structural elements (headings, bold labels) for display and export.
"""

from __future__ import annotations

import re
from typing import Literal

Language = Literal["en", "zh"]

VALID_LANGUAGES: set[str] = {"en", "zh"}

REPORT_HEADING_TRANSLATIONS: dict[str, str] = {
    "Executive Summary": "执行摘要",
    "Top Risks": "主要风险",
    "What This Repository Is": "仓库概览",
    "How It Works": "工作方式",
    "Key Architecture Map": "架构地图",
    "Cycle Groups": "循环依赖组",
    "Agent Summary": "Agent 总结",
    "Agent Findings": "Agent 问题发现",
    "Architecture Summary": "架构分析",
    "Code Smells": "代码质量问题",
    "Maintainability Issues": "可维护性问题",
    "Refactoring Suggestions": "重构建议",
    "Action Plan": "行动计划",
    "Evidence Appendix": "证据附录",
    "Repository Metrics": "仓库指标",
    "Diff Review Scope": "差异审查范围",
    "Priority Recommendations": "优先处理建议",
}

LABEL_TRANSLATIONS: dict[str, str] = {
    "**Type:**": "**类型：**",
    "**Primary components:**": "**主要组件：**",
    "**Scope analyzed:**": "**分析范围：**",
    "**Repository summary:**": "**仓库摘要：**",
    "**Why it matters:**": "**为什么重要：**",
    "**Where:**": "**涉及文件：**",
    "**Likely responsibility area:**": "**责任范围：**",
    "**First step:**": "**建议先做：**",
    "**Change risk:**": "**变更风险：**",
    "**Evidence:**": "**证据引用：**",
    "**Validation tests:**": "**验证方式：**",
    "**Caveat:**": "**注意事项：**",
    "**Recommendation:**": "**建议：**",
    "**Impact:**": "**影响：**",
    "**First safe step:**": "**建议先做：**",
    "**Category:**": "**问题类型：**",
    "**Grounding:**": "**证据说明：**",
    "**Status:**": "**状态：**",
}

# English prose sentences that appear in report_composer output.
# These are replaced wholesale in zh mode so the report reads naturally.
# Longer keys are matched first to avoid partial-match collisions.
PROSE_REPLACEMENTS: dict[str, str] = {
    # How It Works section — static sentences
    "This description is based on paths, symbols, routes, and resolved internal dependencies.": (
        "以上描述基于文件路径、符号信息、路由信息和已解析的内部依赖关系生成，不推断证据中不存在的运行时语义。"
    ),
    "It does not claim runtime semantics that were not present in the analyzed evidence.": (
        "不推断分析证据中未出现的运行时语义。"
    ),
    # How It Works — dynamic sentence prefixes (file paths follow)
    "Execution begins around": "执行入口主要集中在",
    "then delegates into": "，随后调用",
    "Supporting behavior is organized around": "支撑行为分布在",
    "No explicit runtime entry point was detected.": "未检测到明确的运行时入口。",
    "Consumers appear to enter through the reusable interfaces around": "调用方似乎通过以下可复用接口进入：",
    "The static index did not identify a stable entry-point-to-core flow.": (
        "静态索引未能识别稳定的入口到核心模块的调用流。"
    ),
    "Start with the architecture map and evidence-backed findings before assuming runtime behavior.": (
        "请先参考架构地图和基于证据的发现，再推断运行时行为。"
    ),
    # Architecture Map table
    "Trace startup and top-level composition here.": (
        "这些文件通常承担启动入口、应用组装或顶层流程控制职责，修改前应优先确认调用链和兼容性影响。"
    ),
    "These files define central behavior and change boundaries.": (
        "这些文件定义了核心行为和变更边界，是仓库中最关键的模块。"
    ),
    "Changes can affect several internal consumers.": (
        "这些模块被多个内部模块依赖，改动可能产生较广泛的连锁影响。"
    ),
    # Architecture Map table headers
    "| Area | Files | Why It Matters |": "| 区域 | 文件 | 重要性 |",
    # Evidence Appendix
    "Only validated references are shown. Source snippets are intentionally omitted.": (
        "仅展示已验证的证据引用。为保持报告简洁，不展开源码片段。"
    ),
    "Source snippets are intentionally omitted.": "为保持报告简洁，不展开源码片段。",
    # Evidence Appendix table headers
    "| Evidence ID | Location | Kind | Symbols |": "| 证据 ID | 位置 | 类型 | 符号 |",
    # Repository Metrics labels
    "Supported source files:": "支持的源文件数：",
    "Analyzed files:": "已分析文件数：",
    "Skipped files:": "已跳过文件数：",
    "Total lines:": "总行数：",
    "Average complexity estimate:": "平均复杂度估计：",
    # Agent Summary table headers
    "| Agent | Status | Findings | Severity Mix | Avg Confidence | Evidence |": (
        "| Agent | 状态 | 问题数 | 严重性分布 | 平均置信度 | 证据数 |"
    ),
    # Agent Findings section
    "Findings are grouped by the agent that produced them. Evidence references remain compact and snippet-free.": (
        "以下问题按产出 Agent 分组展示，证据引用保持紧凑，不展开源码片段。"
    ),
    "Evidence references remain compact and snippet-free.": "证据引用保持紧凑，不展开源码片段。",
    # Agent finding table headers
    "| Severity | Finding | Confidence | Files | Evidence |": (
        "| 严重性 | 问题 | 置信度 | 文件 | 证据 |"
    ),
    # Agent status text
    "Status:": "状态：",
    "validation:": "验证：",
    # Action Plan section
    "No evidence-grounded action is recommended yet. Gather targeted evidence before changing boundaries.": (
        "暂无基于证据的行动建议。请在修改代码边界前收集针对性证据。"
    ),
    # Change risk phrases
    "Higher structural risk because at least one cited file participates in a dependency cycle.": (
        "结构性风险较高，因为至少一个引用文件参与了循环依赖。"
    ),
    "Changes can affect up to": "变更可能影响多达",
    "resolved internal consumers of the cited files.": "个引用文件的内部依赖方。",
    "finding risk;": "问题风险；",
    "keep the change local to the validated evidence and verify behavior before widening scope.": (
        "将变更控制在已验证的证据范围内，扩大范围前先验证行为。"
    ),
    # Common status text — natural Chinese wording
    "No validated findings.": "暂未发现明确的问题。",
    "No validated finding was produced.": "暂未产出需要单独列出的问题发现。",
    "No validated evidence was cited": "未引用已验证的证据",
    "No validated evidence reference.": "无已验证的证据引用。",
    "Error:": "错误：",
    # Confidence display patterns
    "confidence=": "置信度=",
    "confidence ": "置信度 ",
    # Repository identity
    "no dominant directory boundary detected": "未检测到明显的目录边界",
    "No repository summary was available.": "暂无仓库摘要。",
    # Cycle groups heading (may appear as ## in report)
    "## Cycle Groups": "## 循环依赖组",
    # Executive Summary dynamic patterns
    "CodePilot analyzed": "CodePilot 审查了",
    "and produced": "并产出了",
    "evidence-grounded findings": "基于证据的问题发现",
    "no validated risks": "暂无已验证的风险",
    # Top risk line patterns
    "; evidence:": "；证据引用：",
    # Action Plan patterns
    "No evidence-grounded action is recommended yet.": "暂无基于证据的行动建议。",
    "Gather targeted evidence before changing boundaries.": "请在修改代码边界前收集针对性证据。",
    # Fallback report patterns
    "The full report could not be composed due to an LLM error during report generation.": (
        "由于 LLM 报告生成过程中出现错误，无法组装完整报告。"
    ),
    "Agent pipeline completed": "Agent 流水线已完成",
    "agents;": "个 Agent；",
    "failed.": "个失败。",
    # No related test file
    "No related test file was identified by name.": "未通过名称匹配到相关测试文件。",
    "Add a focused characterization test for": "为以下目标添加针对性的表征测试：",
    "then run the repository test suite.": "然后运行仓库测试套件。",
    # Agent status text
    "Status: **completed**; validation: **validated**.": "状态：**已完成**；验证：**已通过**。",
    "Status: **completed**; validation: **pending**.": "状态：**已完成**；验证：**待验证**。",
    "Not available": "暂无数据",
    "none": "无",
    "none detected": "未检测到",
    # Bare English labels from to_markdown() in contract sections
    # (these lack the bold ** wrappers that LABEL_TRANSLATIONS handles)
    "  Recommendation: ": "  建议：",
    "  Impact: ": "  影响：",
    "  First step: ": "  建议先做：",
    "  Validation tests: ": "  验证方式：",
    "  Caveat: ": "  注意事项：",
    "  Grounding: ": "  证据说明：",
    "Category: ": "问题类型：",
    "Files: ": "涉及文件：",
    "Evidence: ": "证据引用：",
}

# Agent display names for zh mode
# Severity value translations (used in report prose and tables)
SEVERITY_TRANSLATIONS: dict[str, str] = {
    "critical": "严重",
    "high": "高",
    "medium": "中",
    "low": "低",
    "informational": "信息",
}

# Status value translations (used in agent summary tables)
STATUS_VALUE_TRANSLATIONS: dict[str, str] = {
    "completed": "已完成",
    "validated": "已验证",
    "failed": "失败",
    "skipped": "已跳过",
    "pending": "等待中",
    "running": "运行中",
    "not_applicable": "不适用",
}

# Category value translations
CATEGORY_TRANSLATIONS: dict[str, str] = {
    "architecture": "架构",
    "code_smell": "代码质量",
    "maintainability": "可维护性",
    "refactor": "重构",
}

AGENT_DISPLAY_NAMES: dict[str, str] = {
    "ArchitectureAgent": "架构分析 Agent",
    "CodeSmellAgent": "代码质量 Agent",
    "MaintainabilityAgent": "可维护性 Agent",
    "RefactorAgent": "重构建议 Agent",
}

# Reverse mapping for headings that appear in Chinese reports
# (used by frontend parseReport to recognize Chinese headings)
CHINESE_TO_ENGLISH_HEADINGS: dict[str, str] = {
    zh: en for en, zh in REPORT_HEADING_TRANSLATIONS.items()
}


def normalize_language(lang: str | None) -> Language:
    """Normalize a language string to 'en' or 'zh'.

    Returns 'en' for None, empty string, or any unrecognized value.
    """
    if lang and lang.strip().lower() in VALID_LANGUAGES:
        return lang.strip().lower()  # type: ignore[return-value]
    return "en"


def translate_report_heading(heading: str) -> str:
    """Translate a single report heading to Chinese if a mapping exists.

    Returns the original heading if no translation is available.
    """
    return REPORT_HEADING_TRANSLATIONS.get(heading, heading)


def translate_report_headings(report_markdown: str, lang: Language) -> str:
    """Replace Markdown headings with Chinese equivalents.

    Only modifies top-level (# ) and second-level (## ) headings that
    match known English report section titles. Content below headings
    is preserved unchanged.
    """
    if lang != "zh":
        return report_markdown

    lines = report_markdown.split("\n")
    translated: list[str] = []
    for line in lines:
        match = re.match(r"^(#{1,2})\s+(.+)$", line)
        if match:
            prefix = match.group(1)
            heading_text = match.group(2).strip()
            zh_heading = REPORT_HEADING_TRANSLATIONS.get(heading_text, heading_text)
            translated.append(f"{prefix} {zh_heading}")
        else:
            translated.append(line)
    return "\n".join(translated)


def translate_finding_labels(text: str | None, lang: Language) -> str | None:
    """Translate bold labels within finding text to Chinese.

    Only translates label prefixes like '**Why it matters:**' — the
    content after the label remains in English (canonical agent output).
    Returns None if input is None.
    """
    if lang != "zh" or text is None:
        return text
    result = text
    for en_label, zh_label in LABEL_TRANSLATIONS.items():
        result = result.replace(en_label, zh_label)
    return result


def translate_report_labels(report_markdown: str, lang: Language) -> str:
    """Translate bold labels within report body text to Chinese."""
    if lang != "zh":
        return report_markdown
    result = report_markdown
    for en_label, zh_label in LABEL_TRANSLATIONS.items():
        result = result.replace(en_label, zh_label)
    return result


def translate_report_prose(report_markdown: str, lang: Language) -> str:
    """Replace known English prose sentences with Chinese equivalents.

    Applies after headings and labels have been translated.
    Uses longest-first ordering to avoid partial matches.
    """
    if lang != "zh":
        return report_markdown
    result = report_markdown
    for en, zh in sorted(PROSE_REPLACEMENTS.items(), key=lambda x: -len(x[0])):
        result = result.replace(en, zh)
    return result


def translate_agent_name(agent_id: str, lang: Language) -> str:
    """Return the localized display name for an agent ID."""
    if lang != "zh":
        return agent_id
    return AGENT_DISPLAY_NAMES.get(agent_id, agent_id)


def translate_enum_values(report_markdown: str, lang: Language) -> str:
    """Translate raw enum values (severity, status, category) in report text.

    Handles values that appear in table cells and inline prose.
    Uses word-boundary-aware replacement to avoid partial matches.
    """
    if lang != "zh":
        return report_markdown
    result = report_markdown

    # Translate status values in table cells (| completed |, | validated |, etc.)
    for en, zh in STATUS_VALUE_TRANSLATIONS.items():
        result = result.replace(f"| {en} |", f"| {zh} |")
        result = result.replace(f"| {en}|", f"| {zh}|")

    # Translate severity values in table cells
    for en, zh in SEVERITY_TRANSLATIONS.items():
        result = result.replace(f"| {en} |", f"| {zh} |")
        result = result.replace(f"| {en}|", f"| {zh}|")

    # Translate category values in bold labels (**Category:** architecture)
    for en, zh in CATEGORY_TRANSLATIONS.items():
        result = result.replace(f"**类型：** {en}", f"**类型：** {zh}")

    # Translate status in bold labels (**Status:** completed)
    for en, zh in STATUS_VALUE_TRANSLATIONS.items():
        result = result.replace(f"**状态：** {en}", f"**状态：** {zh}")

    # Translate severity mix patterns like "H1 M2 L0" in agent summary
    severity_abbrev = {"C": "严重", "H": "高", "M": "中", "L": "低"}
    for abbrev, zh_name in severity_abbrev.items():
        # Match patterns like "H1" or "M2" (single uppercase letter + digits)
        pattern = rf'\b{abbrev}(\d+)\b'
        result = re.sub(pattern, rf'{zh_name}\1', result)

    # Translate "medium=N, low=N" severity count patterns
    for en, zh in SEVERITY_TRANSLATIONS.items():
        result = result.replace(f"{en}=", f"{zh}=")

    # Translate inline severity+confidence patterns in top-risk lines
    # Pattern: "(medium, confidence 0.90)" → "（严重程度：中，置信度：0.90）"
    # Note: 'confidence' may already be translated to '置信度' by prose replacements,
    # so we match both variants.
    for en_sev, zh_sev in SEVERITY_TRANSLATIONS.items():
        pattern = rf'\({en_sev}, (?:confidence|置信度) (\d+\.\d+)\)'
        replacement = f"（严重程度：{zh_sev}，置信度：\\1）"
        result = re.sub(pattern, replacement, result)

    # Translate standalone severity labels in parenthetical patterns
    # Pattern: "(medium)" → "（中）" when not already translated
    for en_sev, zh_sev in SEVERITY_TRANSLATIONS.items():
        result = result.replace(f"({en_sev})", f"（{zh_sev}）")

    # Translate "in `file`" pattern after confidence parenthetical
    # Pattern: "）in `path`" or ") in `path1`, `path2`" → "）\n  - 涉及文件：`path`"
    # Handles both fullwidth ） and ASCII ) before "in", and multiple comma-separated paths.
    result = re.sub(
        r'[）)]\s*in ((?:`[^`]+`(?:,\s*)?)+)',
        lambda m: f"）\n  - 涉及文件：{m.group(1)}",
        result,
    )

    return result
