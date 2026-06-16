from __future__ import annotations

from backend.agents.finding_validator import FindingValidator
from backend.core.logging import get_logger
from backend.llm.client import LLMClient
from backend.llm.structured import StructuredLLMClient
from backend.models.context import EvidenceRecord, ReviewContext
from backend.models.structured_review import StructuredReviewDraft
from backend.services.evidence import EvidenceRetriever, RetrievalPolicy, RetrievalStats

logger = get_logger(__name__)


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
        self.last_retrieval_stats: RetrievalStats | None = None
        self.candidate_paths: set[str] | None = None

    def set_candidate_paths(self, candidate_paths: set[str] | None) -> None:
        self.candidate_paths = None if candidate_paths is None else set(candidate_paths)

    def review(self, context: ReviewContext) -> StructuredReviewDraft:
        retrieval_policy = self._retrieval_policy()
        retrieval = EvidenceRetriever(context).retrieve_with_policy(
            retrieval_policy,
            candidate_paths=self.candidate_paths,
        )
        evidence_bundle = retrieval.records
        self.last_evidence_bundle = evidence_bundle
        self.last_retrieval_stats = retrieval.stats
        if not evidence_bundle:
            logger.info(
                "finding_quality agent=%s stage=evidence_empty evidence_count=0",
                self.role,
            )
            return StructuredReviewDraft()

        prompt = self._render_prompt(context, evidence_bundle, retrieval_policy)
        allowed_evidence_ids = {record.evidence_id for record in evidence_bundle}
        result = self.structured_client.generate_findings(prompt, allowed_evidence_ids=allowed_evidence_ids)
        validator = FindingValidator(context)
        raw_count = len(result.findings)
        findings = [
            finding
            for raw_finding in result.findings
            if (finding := validator.validate(raw_finding, section=self.section)) is not None
        ]
        validated_count = len(findings)
        dropped_count = raw_count - validated_count
        logger.info(
            "finding_quality agent=%s raw=%d validated=%d dropped=%d "
            "no_findings_reason=%s invalid_attempts=%d evidence_count=%d",
            self.role,
            raw_count,
            validated_count,
            dropped_count,
            result.no_findings_reason or "none",
            result.invalid_attempts,
            len(evidence_bundle),
        )
        self.last_no_findings_reason = result.no_findings_reason
        return StructuredReviewDraft(findings=findings)

    def _render_prompt(
        self,
        context: ReviewContext,
        evidence_bundle: list[EvidenceRecord],
        retrieval_policy: RetrievalPolicy | None = None,
    ) -> str:
        retrieval_policy = retrieval_policy or self._retrieval_policy()
        retriever = EvidenceRetriever(context)
        evidence_lines = []
        for record in evidence_bundle:
            compressed = retriever.compress_for_prompt(record, self.evidence_query, policy=retrieval_policy)
            evidence_lines.append(
                f"- evidence_id={record.evidence_id}; file={record.file_path}; "
                f"lines={record.start_line}-{record.end_line}; "
                f"excerpt_lines={compressed.excerpt_start_line}-{compressed.excerpt_end_line}; "
                f"truncated={str(compressed.truncated).lower()}; snippet={compressed.snippet}"
            )
        return (
            f"You are CodePilot's {self.role}.\n"
            f"Review category: {self.category}. Target report section: {self.section}.\n"
            "\n"
            "TASK: Analyze the evidence below and produce 1-3 actionable findings.\n"
            "Each finding must be grounded in the provided evidence_ids.\n"
            "Severity can be high, medium, or low — medium and low findings are welcome.\n"
            "If the evidence genuinely supports no findings, return an empty array with a reason.\n"
            "\n"
            "OUTPUT FORMAT: Return ONLY valid JSON. No markdown fences, no explanation text.\n"
            "Top-level structure: {\"findings\": [...], \"no_findings_reason\": null}\n"
            "Each finding MUST have these required fields:\n"
            "- title: string (short summary)\n"
            "- description: string (concrete explanation)\n"
            f"- category: string (must be exactly \"{self.category}\")\n"
            "- severity: one of \"high\", \"medium\", \"low\"\n"
            "- confidence: number 0.0-1.0\n"
            "- evidence_ids: array of strings from the provided evidence (at least one)\n"
            "- display: {en: {title, description, ...}, zh: {title, description, ...}}\n"
            "Optional fields: recommendation, impact, first_step, validation_tests, "
            "confidence_rationale, caveat (all nullable).\n"
            "\n"
            "EXAMPLE:\n"
            '{"findings": [{"title": "Broad exception handler", '
            '"description": "The except block catches all exceptions including KeyboardInterrupt.", '
            f'"category": "{self.category}", "severity": "medium", "confidence": 0.8, '
            '"recommendation": "Catch specific exceptions instead.", '
            '"evidence_ids": ["ev_abc123"], "impact": "Silences real errors.", '
            '"first_step": "Add specific exception types to the except clause.", '
            '"validation_tests": ["pytest tests/test_error_handling.py"], '
            '"confidence_rationale": "Single evidence record confirms the pattern.", '
            '"caveat": "May be intentional for top-level error boundary.", '
            '"display": {"en": {"title": "Broad exception handler", '
            '"description": "The except block catches all exceptions including KeyboardInterrupt."}, '
            '"zh": {"title": "宽泛异常处理", '
            '"description": "except 块捕获所有异常，包括 KeyboardInterrupt。"}}}], '
            '"no_findings_reason": null}\n'
            "\n"
            "Use evidence_ids only for grounding. Do not invent file paths, line ranges, or snippets.\n"
            "\n"
            "Bilingual display rules:\n"
            "- display.en: mirror the top-level English fields exactly.\n"
            "- display.zh: natural Chinese for software engineers. Concise professional wording.\n"
            "- NEVER use '代码坏味道'. Use '代码质量问题' instead.\n"
            "- Preferred terms: 架构分析, 可维护性问题, 重构建议, 第一步建议, 验证方式, 注意事项.\n"
            "- Keep code symbols, file paths, commands, evidence IDs untranslated.\n"
            "- severity, confidence, evidence_ids, category must be identical in en and zh.\n"
            "\n"
            "Quality guidance:\n"
            "- Prefer concrete descriptions of code responsibility, change risk, "
            "and specific actionable steps over vague statements.\n"
            "- impact: practical consequence if left unaddressed.\n"
            "- first_step: safest initial change before attempting a fix.\n"
            "- validation_tests: test files or commands to run before and after.\n"
            "- confidence_rationale: why this confidence level.\n"
            "- caveat: risks or reasons the recommendation might not apply.\n"
            "\n"
            "For mature libraries (Flask, Django, Express, etc.):\n"
            "- Avoid overly aggressive refactor advice.\n"
            "- Mention public API compatibility when relevant.\n"
            "- Do not assume duplication is always bad if it preserves API boundaries.\n"
            "\n"
            f"Per-agent prompt budget: {self.token_budget} tokens.\n"
            f"Repository: {context.repo_url}\n"
            f"Summary: {context.repository_summary}\n"
            "Evidence:\n"
            + "\n".join(evidence_lines)
        )

    def _retrieval_policy(self) -> RetrievalPolicy:
        return RetrievalPolicy(
            agent_role=self.role,
            query=self.evidence_query,
            limit=self.evidence_limit,
            token_budget=self.token_budget,
            manifest_limit=max(self.evidence_limit * 3, 12),
            symbol_limit=max(self.evidence_limit * 2, 8),
        )
