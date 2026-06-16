"""Deterministic priority layer for Chinese reports.

Groups findings into P1/P2/P3 and generates the 优先处理建议 section.
No LLM calls — all logic is deterministic based on finding metadata.
"""

from __future__ import annotations

from backend.models.structured_review import ReviewFinding

SEVERITY_WEIGHT = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
    "informational": 0,
}

CATEGORY_WEIGHT = {
    "architecture": 2,
    "code_smell": 1,
    "maintainability": 1,
    "refactor": 0,
}

# Thresholds for priority assignment
_P1_SEVERITY_MIN = 3  # high or critical
_P1_CONFIDENCE_MIN = 0.7
_P2_SEVERITY_MIN = 2  # medium or above


def _priority_score(finding: ReviewFinding) -> float:
    """Compute a numeric priority score for a finding.

    Higher score = higher priority.
    """
    severity = (finding.severity or "informational").lower()
    sev_weight = SEVERITY_WEIGHT.get(severity, 0)
    confidence = finding.confidence or 0.0
    file_count = len(finding.files or [])
    category = (finding.category or "").lower()
    cat_weight = CATEGORY_WEIGHT.get(category, 0)

    # Weighted formula: severity dominates, confidence amplifies,
    # file count adds breadth, category adds structural importance
    score = sev_weight * 3.0
    score += confidence * 2.0
    score += min(file_count, 5) * 0.5
    score += cat_weight * 0.5
    return score


def assign_priority(finding: ReviewFinding) -> str:
    """Assign P1, P2, or P3 to a finding deterministically."""
    severity = (finding.severity or "informational").lower()
    confidence = finding.confidence or 0.0
    sev_weight = SEVERITY_WEIGHT.get(severity, 0)

    if sev_weight >= _P1_SEVERITY_MIN and confidence >= _P1_CONFIDENCE_MIN:
        return "P1"
    if sev_weight >= _P2_SEVERITY_MIN:
        return "P2"
    return "P3"


def _why_important(finding: ReviewFinding) -> str:
    """Generate a natural Chinese explanation of why this finding matters."""
    impact = (finding.impact or "").strip()
    if impact:
        return impact
    description = (finding.description or "").strip()
    if description:
        return description
    return "该问题可能影响代码质量或可维护性。"


def _suggested_first_action(finding: ReviewFinding) -> str:
    """Generate a natural Chinese first action suggestion."""
    first_step = (finding.first_step or "").strip()
    if first_step:
        return first_step
    recommendation = (finding.recommendation or "").strip()
    if recommendation:
        return recommendation
    return "建议先收集更多证据，再制定修复方案。"


def _evidence_citation(finding: ReviewFinding) -> str:
    """Format evidence IDs for display."""
    if not finding.evidence_ids:
        return "暂无证据引用"
    return ", ".join(f"`{eid}`" for eid in finding.evidence_ids[:3])


def _files_involved(finding: ReviewFinding) -> str:
    """Format file list for display."""
    if not finding.files:
        return "未指定文件"
    visible = ", ".join(f"`{f}`" for f in finding.files[:4])
    if len(finding.files) > 4:
        visible += f"，另有 {len(finding.files) - 4} 个文件"
    return visible


def generate_priority_section(findings: list[ReviewFinding]) -> str:
    """Generate the 优先处理建议 section for Chinese reports.

    Returns empty string if no findings exist.
    """
    if not findings:
        return ""

    # Assign priorities and group
    grouped: dict[str, list[tuple[ReviewFinding, float]]] = {
        "P1": [],
        "P2": [],
        "P3": [],
    }
    for finding in findings:
        priority = assign_priority(finding)
        score = _priority_score(finding)
        grouped[priority].append((finding, score))

    # Sort each group by score descending
    for priority in grouped:
        grouped[priority].sort(key=lambda x: -x[1])

    lines = ["# 优先处理建议"]

    # P1
    if grouped["P1"]:
        lines.append("")
        lines.append("## P1：建议优先处理")
        for finding, _ in grouped["P1"][:5]:
            title = finding.title or finding.description or "未命名问题"
            lines.append("")
            lines.append(f"* **{title}**")
            lines.append(f"  * 为什么重要：{_why_important(finding)}")
            lines.append(f"  * 建议先做：{_suggested_first_action(finding)}")
            lines.append(f"  * 涉及文件：{_files_involved(finding)}")
            lines.append(f"  * 证据引用：{_evidence_citation(finding)}")
    else:
        lines.append("")
        lines.append("本次未发现需要立即处理的 P1 问题。")

    # P2
    if grouped["P2"]:
        lines.append("")
        lines.append("## P2：建议排期优化")
        for finding, _ in grouped["P2"][:5]:
            title = finding.title or finding.description or "未命名问题"
            lines.append("")
            lines.append(f"* **{title}**")
            lines.append(f"  * 为什么重要：{_why_important(finding)}")
            lines.append(f"  * 建议先做：{_suggested_first_action(finding)}")
            lines.append(f"  * 涉及文件：{_files_involved(finding)}")
            lines.append(f"  * 证据引用：{_evidence_citation(finding)}")

    # P3
    if grouped["P3"]:
        lines.append("")
        lines.append("## P3：低风险改进")
        for finding, _ in grouped["P3"][:3]:
            title = finding.title or finding.description or "未命名问题"
            lines.append("")
            lines.append(f"* **{title}**")
            lines.append(f"  * 为什么重要：{_why_important(finding)}")
            lines.append(f"  * 建议先做：{_suggested_first_action(finding)}")
            lines.append(f"  * 涉及文件：{_files_involved(finding)}")

    return "\n".join(lines)
