from __future__ import annotations

from pydantic import BaseModel, Field


class RawLLMFinding(BaseModel):
    title: str
    description: str
    category: str
    severity: str = "informational"
    confidence: float = 0.5
    recommendation: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


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

    def to_markdown(self) -> str:
        if self.title is None:
            return self.description.strip()

        heading = f"- **{self.title}:** {self.description.strip()}"
        if self.category or self.confidence is not None:
            confidence = f"{self.confidence:.2f}" if self.confidence is not None else "n/a"
            heading = f"{heading} Category: {self.category or 'general'}; confidence={confidence}."
        if self.files:
            heading = f"{heading} Files: {', '.join(f'`{path}`' for path in self.files)}."
        if self.evidence_ids:
            heading = f"{heading} Evidence: {', '.join(self.evidence_ids)}."
        if self.recommendation:
            heading = f"{heading}\n  Recommendation: {self.recommendation.strip()}"
        if self.evidence:
            heading = f"{heading}\n  Grounding: {'; '.join(self.evidence)}"
        return heading


class StructuredReviewDraft(BaseModel):
    findings: list[ReviewFinding] = Field(default_factory=list)

    def findings_for(self, section: str) -> list[ReviewFinding]:
        return [finding for finding in self.findings if finding.section == section]

    def section_markdown(self, section: str) -> str:
        return "\n\n".join(
            finding.to_markdown()
            for finding in self.findings_for(section)
        ).strip()
