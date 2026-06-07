from __future__ import annotations

from pydantic import BaseModel, Field


class ReviewFinding(BaseModel):
    section: str
    description: str
    title: str | None = None
    severity: str = "informational"
    files: list[str] = Field(default_factory=list)
    recommendation: str | None = None

    def to_markdown(self) -> str:
        if self.title is None:
            return self.description.strip()

        heading = f"- **{self.title}:** {self.description.strip()}"
        if self.files:
            heading = f"{heading} Files: {', '.join(f'`{path}`' for path in self.files)}."
        if self.recommendation:
            heading = f"{heading}\n  Recommendation: {self.recommendation.strip()}"
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
