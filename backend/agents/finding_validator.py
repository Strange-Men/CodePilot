from __future__ import annotations

from backend.core.report_contract import REPORT_SECTIONS
from backend.models.context import EvidenceRecord, ReviewContext
from backend.models.structured_review import RawLLMFinding, ReviewFinding
from backend.services.evidence import EvidenceStore


class FindingValidator:
    def __init__(self, context: ReviewContext) -> None:
        self.store = EvidenceStore.from_context(context)

    def validate(self, finding: RawLLMFinding, *, section: str) -> ReviewFinding | None:
        if section not in REPORT_SECTIONS or not finding.evidence_ids:
            return None
        evidence: list[EvidenceRecord] = []
        for evidence_id in finding.evidence_ids:
            try:
                evidence.append(self.store.resolve(evidence_id))
            except KeyError:
                return None
        files = list(dict.fromkeys(record.file_path for record in evidence))
        grounding = [
            f"{record.evidence_id} -> {record.file_path}:{record.start_line}-{record.end_line}"
            for record in evidence
        ]
        return ReviewFinding(
            section=section,
            title=finding.title,
            description=finding.description,
            category=finding.category,
            severity=finding.severity,
            confidence=finding.confidence,
            files=files,
            recommendation=finding.recommendation,
            evidence_ids=[record.evidence_id for record in evidence],
            evidence=grounding,
            impact=finding.impact,
            first_step=finding.first_step,
            validation_tests=finding.validation_tests,
            confidence_rationale=finding.confidence_rationale,
            caveat=finding.caveat,
        )
