from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from backend.reviewers.evidence_display import EvidenceDisplayMap


class BilingualTextField(BaseModel):
    """Display text in one language for a single prose field."""

    title: str | None = None
    description: str | None = None
    recommendation: str | None = None
    impact: str | None = None
    first_step: str | None = None
    validation_tests: list[str] = Field(default_factory=list)
    confidence_rationale: str | None = None
    caveat: str | None = None


class DisplayFields(BaseModel):
    """Bilingual display fields for a finding.

    Structural fields (severity, confidence, evidence_ids, files, category)
    remain language-neutral and are NOT included here.
    """

    en: BilingualTextField = Field(default_factory=BilingualTextField)
    zh: BilingualTextField = Field(default_factory=BilingualTextField)


class RawLLMFinding(BaseModel):
    title: str
    description: str
    category: str
    severity: str = "informational"
    confidence: float = 0.5
    recommendation: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    impact: str | None = None
    first_step: str | None = None
    validation_tests: list[str] = Field(default_factory=list)
    confidence_rationale: str | None = None
    caveat: str | None = None
    display: DisplayFields | None = None


class ReviewFinding(BaseModel):
    section: str
    description: str
    title: str | None = None
    severity: str = "informational"
    category: str | None = None
    confidence: float | None = None
    files: list[str] = Field(default_factory=list)
    recommendation: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    impact: str | None = None
    first_step: str | None = None
    validation_tests: list[str] = Field(default_factory=list)
    confidence_rationale: str | None = None
    caveat: str | None = None
    display: DisplayFields | None = None

    def _display_field(self, field: str, lang: str = "en") -> str | None:
        """Get a display field value for the given language, falling back to English."""
        if self.display is not None:
            lang_fields = getattr(self.display, lang, None) or self.display.en
            value = getattr(lang_fields, field, None)
            if value is not None:
                return value
        # Fallback to canonical English field
        return getattr(self, field, None)

    def _display_validation_tests(self, lang: str = "en") -> list[str]:
        """Get validation_tests for the given language, falling back to English."""
        if self.display is not None:
            lang_fields = getattr(self.display, lang, None) or self.display.en
            if lang_fields.validation_tests:
                return lang_fields.validation_tests
        return self.validation_tests

    def _format_evidence_ids(self, display_map: EvidenceDisplayMap | None = None) -> str:
        """Format evidence IDs using display map if available."""
        if not self.evidence_ids:
            return ""
        if display_map is not None:
            return " ".join(display_map.ref_bracket(eid) for eid in self.evidence_ids)
        return ", ".join(self.evidence_ids)

    def to_markdown(self, display_map: EvidenceDisplayMap | None = None) -> str:
        if self.title is None:
            return self.description.strip()

        heading = f"- **{self.title}:** {self.description.strip()}"
        if self.category or self.confidence is not None:
            confidence = f"{self.confidence:.2f}" if self.confidence is not None else "n/a"
            heading = f"{heading} Category: {self.category or 'general'}; confidence={confidence}."
        if self.files:
            heading = f"{heading} Files: {', '.join(f'`{path}`' for path in self.files)}."
        if self.evidence_ids:
            heading = f"{heading} Evidence: {self._format_evidence_ids(display_map)}."
        if self.recommendation:
            heading = f"{heading}\n  Recommendation: {self.recommendation.strip()}"
        if self.impact:
            heading = f"{heading}\n  Impact: {self.impact.strip()}"
        if self.first_step:
            heading = f"{heading}\n  First step: {self.first_step.strip()}"
        if self.validation_tests:
            heading = f"{heading}\n  Validation tests: {', '.join(self.validation_tests)}"
        if self.caveat:
            heading = f"{heading}\n  Caveat: {self.caveat.strip()}"
        if self.evidence:
            heading = f"{heading}\n  Grounding: {'; '.join(self.evidence)}"
        return heading

    def to_localized_markdown(self, lang: str = "en", display_map: EvidenceDisplayMap | None = None) -> str:
        """Generate localized markdown using bilingual display fields.

        For lang='en', equivalent to to_markdown().
        For lang='zh', uses display.zh fields and Chinese labels.
        Code symbols, file paths, evidence IDs are never translated.
        """
        title = self._display_field("title", lang) or self.title
        description = self._display_field("description", lang) or self.description
        if title is None:
            return (description or "").strip()

        # Use Chinese labels for zh, English for en
        if lang == "zh":
            return self._to_zh_markdown(title, description or "", display_map=display_map)
        return self._to_en_localized_markdown(title, description or "", lang, display_map=display_map)

    def _to_zh_markdown(self, title: str, description: str, *, display_map: EvidenceDisplayMap | None = None) -> str:
        """Generate Chinese-native markdown with proper labels."""
        heading = f"- **{title}：** {description.strip()}"
        if self.category or self.confidence is not None:
            confidence = f"{self.confidence:.2f}" if self.confidence is not None else "n/a"
            heading = f"{heading} 问题类型：{self.category or '通用'}；置信度：{confidence}。"
        if self.files:
            heading = f"{heading} 涉及文件：{', '.join(f'`{path}`' for path in self.files)}。"
        if self.evidence_ids:
            heading = f"{heading} 证据引用：{self._format_evidence_ids(display_map)}。"
        recommendation = self._display_field("recommendation", "zh")
        if recommendation:
            heading = f"{heading}\n  建议：{recommendation.strip()}"
        impact = self._display_field("impact", "zh")
        if impact:
            heading = f"{heading}\n  影响：{impact.strip()}"
        first_step = self._display_field("first_step", "zh")
        if first_step:
            heading = f"{heading}\n  建议先做：{first_step.strip()}"
        validation_tests = self._display_validation_tests("zh")
        if validation_tests:
            heading = f"{heading}\n  验证方式：{', '.join(validation_tests)}"
        caveat = self._display_field("caveat", "zh")
        if caveat:
            heading = f"{heading}\n  注意事项：{caveat.strip()}"
        if self.evidence:
            heading = f"{heading}\n  证据说明：{'; '.join(self.evidence)}"
        return heading

    def _to_en_localized_markdown(
        self, title: str, description: str, lang: str, *,
        display_map: EvidenceDisplayMap | None = None,
    ) -> str:
        """Generate localized markdown for non-zh languages (uses English labels)."""
        heading = f"- **{title}:** {description.strip()}"
        if self.category or self.confidence is not None:
            confidence = f"{self.confidence:.2f}" if self.confidence is not None else "n/a"
            heading = f"{heading} Category: {self.category or 'general'}; confidence={confidence}."
        if self.files:
            heading = f"{heading} Files: {', '.join(f'`{path}`' for path in self.files)}."
        if self.evidence_ids:
            heading = f"{heading} Evidence: {self._format_evidence_ids(display_map)}."
        recommendation = self._display_field("recommendation", lang)
        if recommendation:
            heading = f"{heading}\n  Recommendation: {recommendation.strip()}"
        impact = self._display_field("impact", lang)
        if impact:
            heading = f"{heading}\n  Impact: {impact.strip()}"
        first_step = self._display_field("first_step", lang)
        if first_step:
            heading = f"{heading}\n  First step: {first_step.strip()}"
        validation_tests = self._display_validation_tests(lang)
        if validation_tests:
            heading = f"{heading}\n  Validation tests: {', '.join(validation_tests)}"
        caveat = self._display_field("caveat", lang)
        if caveat:
            heading = f"{heading}\n  Caveat: {caveat.strip()}"
        if self.evidence:
            heading = f"{heading}\n  Grounding: {'; '.join(self.evidence)}"
        return heading


class StructuredReviewDraft(BaseModel):
    findings: list[ReviewFinding] = Field(default_factory=list)

    def findings_for(self, section: str) -> list[ReviewFinding]:
        return [finding for finding in self.findings if finding.section == section]

    def section_markdown(self, section: str, display_map: EvidenceDisplayMap | None = None) -> str:
        return "\n\n".join(
            finding.to_markdown(display_map)
            for finding in self.findings_for(section)
        ).strip()

    def section_localized_markdown(
        self, section: str, lang: str = "en",
        display_map: EvidenceDisplayMap | None = None,
    ) -> str:
        return "\n\n".join(
            finding.to_localized_markdown(lang, display_map)
            for finding in self.findings_for(section)
        ).strip()
