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
}

LABEL_TRANSLATIONS: dict[str, str] = {
    "**Type:**": "**类型：**",
    "**Primary components:**": "**主要组件：**",
    "**Scope analyzed:**": "**分析范围：**",
    "**Repository summary:**": "**仓库摘要：**",
    "**Why it matters:**": "**为什么重要：**",
    "**Where:**": "**位置：**",
    "**Likely responsibility area:**": "**可能的责任区域：**",
    "**First step:**": "**第一步：**",
    "**Change risk:**": "**变更风险：**",
    "**Evidence:**": "**证据：**",
    "**Validation tests:**": "**验证方式：**",
    "**Caveat:**": "**注意事项：**",
    "**Recommendation:**": "**建议：**",
    "**Impact:**": "**影响：**",
    "**First safe step:**": "**安全第一步：**",
    "**Category:**": "**类型：**",
    "**Grounding:**": "**证据定位：**",
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
    # Common status text
    "No validated findings.": "暂无已验证的问题发现。",
    "No validated finding was produced.": "未产出已验证的问题发现。",
    "No validated evidence was cited": "未引用已验证的证据",
    "No validated evidence reference.": "无已验证的证据引用。",
    "Error:": "错误：",
    # Repository identity
    "no dominant directory boundary detected": "未检测到明显的目录边界",
    "No repository summary was available.": "暂无仓库摘要。",
    # Cycle groups heading (may appear as ## in report)
    "## Cycle Groups": "## 循环依赖组",
}

# Agent display names for zh mode
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
