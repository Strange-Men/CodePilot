from __future__ import annotations

from backend.agents.finding_validator import FindingValidator
from backend.llm.client import LLMClient
from backend.llm.structured import StructuredLLMClient
from backend.models.context import EvidenceRecord, ReviewContext
from backend.models.structured_review import StructuredReviewDraft
from backend.services.evidence import EvidenceRetriever


class EvidenceGroundedAgent:
    role = "EvidenceGroundedAgent"
    section = ""
    category = "general"
    evidence_query = "architecture maintainability code smell refactor"
    evidence_limit = 8

    def __init__(self, llm_client: LLMClient, *, model: str = "gpt-4o-mini", token_budget: int = 2000) -> None:
        self.structured_client = StructuredLLMClient(llm_client, model=model)
        self.token_budget = token_budget
        self.last_evidence_bundle: list[EvidenceRecord] = []

    def review(self, context: ReviewContext) -> StructuredReviewDraft:
        evidence_bundle = EvidenceRetriever(context).retrieve(self.evidence_query, limit=self.evidence_limit)
        self.last_evidence_bundle = evidence_bundle
        if not evidence_bundle:
            return StructuredReviewDraft()

        prompt = self._render_prompt(context, evidence_bundle)
        allowed_evidence_ids = {record.evidence_id for record in evidence_bundle}
        result = self.structured_client.generate_findings(prompt, allowed_evidence_ids=allowed_evidence_ids)
        validator = FindingValidator(context)
        findings = [
            finding
            for raw_finding in result.findings
            if (finding := validator.validate(raw_finding, section=self.section)) is not None
        ]
        return StructuredReviewDraft(findings=findings)

    def _render_prompt(self, context: ReviewContext, evidence_bundle: list[EvidenceRecord]) -> str:
        evidence_lines = [
            (
                f"- evidence_id={record.evidence_id}; file={record.file_path}; "
                f"lines={record.start_line}-{record.end_line}; snippet={record.snippet[:900]}"
            )
            for record in evidence_bundle
        ]
        return (
            f"You are CodePilot's {self.role}.\n"
            f"Review category: {self.category}. Target report section: {self.section}.\n"
            "Return only JSON: {\"findings\": [{\"title\": str, \"description\": str, "
            "\"category\": str, \"severity\": str, \"confidence\": number, "
            "\"recommendation\": str, \"evidence_ids\": [str]}]}.\n"
            "Use evidence_ids only for grounding. Do not invent file paths, line ranges, or snippets.\n"
            f"Per-agent prompt budget: {self.token_budget} tokens.\n"
            f"Repository: {context.repo_url}\n"
            f"Summary: {context.repository_summary}\n"
            "Evidence:\n"
            + "\n".join(evidence_lines)
        )
