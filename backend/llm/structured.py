from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from pydantic import ValidationError

from backend.core.logging import get_logger
from backend.llm.client import LLMClient
from backend.models.structured_review import RawLLMFinding
from backend.services.token_counting import PromptTokenCounter

logger = get_logger(__name__)


@dataclass
class CostTracker:
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0

    def record(self, prompt: str, completion: str) -> None:
        counter = PromptTokenCounter(self.model)
        self.calls += 1
        self.prompt_tokens += counter.count(prompt)
        self.completion_tokens += counter.count(completion)


@dataclass
class StructuredLLMResult:
    findings: list[RawLLMFinding]
    invalid_attempts: int = 0
    errors: list[str] = field(default_factory=list)
    no_findings_reason: str | None = None


class StructuredLLMClient:
    def __init__(
        self,
        llm_client: LLMClient,
        *,
        model: str = "gpt-4o-mini",
        max_retries: int = 1,
        max_findings: int | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.max_retries = max_retries
        self.max_findings = max_findings
        self.cost_tracker = CostTracker(model=model)

    def generate_findings(self, prompt: str, *, allowed_evidence_ids: set[str]) -> StructuredLLMResult:
        structured_mock = getattr(self.llm_client, "generate_structured_findings", None)
        if callable(structured_mock):
            findings = self._filter_allowed(structured_mock(prompt), allowed_evidence_ids)
            if self.max_findings is not None:
                findings = findings[: self.max_findings]
            return StructuredLLMResult(findings=findings)

        errors: list[str] = []
        current_prompt = prompt
        for attempt in range(self.max_retries + 1):
            completion = self.llm_client.generate_review(current_prompt)
            self.cost_tracker.record(current_prompt, completion)
            try:
                findings, no_reason = self._parse_findings(completion)
                if self.max_findings is not None:
                    findings = findings[: self.max_findings]
                return StructuredLLMResult(
                    findings=self._filter_allowed(findings, allowed_evidence_ids),
                    invalid_attempts=attempt,
                    errors=errors,
                    no_findings_reason=no_reason,
                )
            except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
                errors.append(str(exc))
                logger.info(
                    "structured_parse_failure attempt=%d error_type=%s "
                    "completion_length=%d sanitized_error=%s",
                    attempt + 1,
                    type(exc).__name__,
                    len(completion),
                    str(exc)[:200],
                )
                current_prompt = (
                    f"{prompt}\n\nPrevious output was invalid: {exc}. "
                    "Return only JSON with a top-level findings array and valid evidence_ids."
                )
        return StructuredLLMResult(findings=[], invalid_attempts=len(errors), errors=errors)

    @staticmethod
    def _strip_code_fences(completion: str) -> str:
        """Strip markdown code fences (```json ... ```) from LLM output."""
        stripped = completion.strip()
        # Match ```json ... ``` or ``` ... ```
        match = re.match(r"^```(?:json)?\s*\n?(.*?)\n?\s*```$", stripped, re.DOTALL)
        if match:
            return match.group(1).strip()
        return stripped

    @staticmethod
    def _parse_findings(completion: str) -> tuple[list[RawLLMFinding], str | None]:
        cleaned = StructuredLLMClient._strip_code_fences(completion)
        data = json.loads(cleaned)
        no_reason: str | None = None
        if isinstance(data, dict):
            raw_findings = data.get("findings", [])
            no_reason = data.get("no_findings_reason")
        else:
            raw_findings = data
        findings = [RawLLMFinding.model_validate(item) for item in raw_findings]
        for finding in findings:
            if not finding.evidence_ids:
                raise ValueError("Structured finding lacks evidence_ids.")
        return findings, no_reason

    @staticmethod
    def _filter_allowed(findings: list[RawLLMFinding], allowed_evidence_ids: set[str]) -> list[RawLLMFinding]:
        filtered: list[RawLLMFinding] = []
        for finding in findings:
            evidence_ids = [evidence_id for evidence_id in finding.evidence_ids if evidence_id in allowed_evidence_ids]
            if evidence_ids:
                filtered.append(finding.model_copy(update={"evidence_ids": evidence_ids}))
        return filtered
