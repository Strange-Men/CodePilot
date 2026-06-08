from __future__ import annotations

from agents.finding_validator import FindingValidator
from backend.core.report_contract import REPORT_SECTIONS
from backend.llm.client import LLMClient
from backend.llm.structured import StructuredLLMClient
from backend.models.context import ReviewContext
from backend.models.structured_review import StructuredReviewDraft
from backend.services.evidence import EvidenceRetriever

ARCHITECTURE_SECTION = REPORT_SECTIONS[0]


class ArchitectureAgent:
    role = "ArchitectureAgent"

    def __init__(self, llm_client: LLMClient, *, model: str = "gpt-4o-mini") -> None:
        self.structured_client = StructuredLLMClient(llm_client, model=model)

    def review(self, context: ReviewContext) -> StructuredReviewDraft:
        evidence_bundle = EvidenceRetriever(context).retrieve(
            "architecture entry point core module dependency route class function",
            limit=10,
        )
        if not evidence_bundle:
            return StructuredReviewDraft()

        prompt = self._render_prompt(context, evidence_bundle)
        allowed_evidence_ids = {record.evidence_id for record in evidence_bundle}
        result = self.structured_client.generate_findings(prompt, allowed_evidence_ids=allowed_evidence_ids)
        validator = FindingValidator(context)
        findings = [
            finding
            for raw_finding in result.findings
            if (finding := validator.validate(raw_finding, section=ARCHITECTURE_SECTION)) is not None
        ]
        return StructuredReviewDraft(findings=findings)

    @staticmethod
    def _render_prompt(context: ReviewContext, evidence_bundle) -> str:
        evidence_lines = [
            (
                f"- evidence_id={record.evidence_id}; file={record.file_path}; "
                f"lines={record.start_line}-{record.end_line}; snippet={record.snippet[:900]}"
            )
            for record in evidence_bundle
        ]
        return (
            "You are CodePilot's ArchitectureAgent.\n"
            "Return only JSON: {\"findings\": [{\"title\": str, \"description\": str, "
            "\"category\": \"architecture\", \"severity\": str, \"confidence\": number, "
            "\"recommendation\": str, \"evidence_ids\": [str]}]}.\n"
            "Use evidence_ids only for grounding. Do not invent file paths, line ranges, or snippets.\n"
            f"Repository: {context.repo_url}\n"
            f"Summary: {context.repository_summary}\n"
            "Evidence:\n"
            + "\n".join(evidence_lines)
        )
