from __future__ import annotations

from backend.agents.finding_validator import FindingValidator
from backend.llm.client import LLMClient
from backend.llm.structured import StructuredLLMClient
from backend.models.context import EvidenceRecord, ReviewContext
from backend.models.structured_review import StructuredReviewDraft
from backend.services.evidence import EvidenceRetriever, RetrievalPolicy, RetrievalStats


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
            return StructuredReviewDraft()

        prompt = self._render_prompt(context, evidence_bundle, retrieval_policy)
        allowed_evidence_ids = {record.evidence_id for record in evidence_bundle}
        result = self.structured_client.generate_findings(prompt, allowed_evidence_ids=allowed_evidence_ids)
        validator = FindingValidator(context)
        findings = [
            finding
            for raw_finding in result.findings
            if (finding := validator.validate(raw_finding, section=self.section)) is not None
        ]
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
            "Return only JSON: {\"findings\": [{\"title\": str, \"description\": str, "
            "\"category\": str, \"severity\": str, \"confidence\": number, "
            "\"recommendation\": str, \"evidence_ids\": [str], "
            "\"impact\": str|null, \"first_step\": str|null, "
            "\"validation_tests\": [str], \"confidence_rationale\": str|null, "
            "\"caveat\": str|null, "
            "\"display\": {\"en\": {\"title\": str, \"description\": str, "
            "\"recommendation\": str|null, \"impact\": str|null, \"first_step\": str|null, "
            "\"validation_tests\": [str], \"confidence_rationale\": str|null, \"caveat\": str|null}, "
            "\"zh\": {\"title\": str, \"description\": str, "
            "\"recommendation\": str|null, \"impact\": str|null, \"first_step\": str|null, "
            "\"validation_tests\": [str], \"confidence_rationale\": str|null, \"caveat\": str|null"
            "}}}]}.\n"
            "Use evidence_ids only for grounding. Do not invent file paths, line ranges, or snippets.\n"
            "\n"
            "Bilingual display rules:\n"
            "- The top-level fields (title, description, etc.) are the English canonical values.\n"
            "- The display.en object should mirror the top-level English fields exactly.\n"
            "- The display.zh object must contain natural Chinese translations for software engineers.\n"
            "- Use concise professional Chinese. Avoid machine-translation wording.\n"
            "- NEVER use '代码坏味道'. Use '代码质量问题' instead.\n"
            "- Use: 架构分析, 可维护性问题, 重构建议, 第一步建议, 验证方式, 注意事项.\n"
            "- Code symbols, file paths, commands, evidence IDs must NOT be translated.\n"
            "- severity, confidence, evidence_ids, files, category must remain identical across languages.\n"
            "\n"
            "Quality guidance:\n"
            "- Avoid vague findings like 'this code is complex', 'improve maintainability', "
            "'refactor this'. Prefer concrete descriptions of code responsibility, change risk, "
            "and specific actionable steps.\n"
            "- impact: describe the practical consequence if this issue is left unaddressed.\n"
            "- first_step: the safest initial change a developer should make before attempting a fix.\n"
            "- validation_tests: specific test files or test commands to run before and after the change.\n"
            "- confidence_rationale: briefly explain why this confidence level (e.g., 'multiple evidence "
            "records confirm the pattern' or 'limited to one evidence record').\n"
            "- caveat: note any risk, compatibility concern, or reason the recommendation might not apply "
            "(e.g., mature public API compatibility, intentional duplication for extension points).\n"
            "\n"
            "For mature libraries (Flask, Django, Express, etc.):\n"
            "- Avoid overly aggressive refactor advice.\n"
            "- Mention public API compatibility when relevant.\n"
            "- Do not assume duplication is always bad if it preserves API boundaries.\n"
            "- Architecture findings should prefer production-code evidence when possible.\n"
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
