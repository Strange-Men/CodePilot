from __future__ import annotations

import os
import re
import time
from collections.abc import Callable
from typing import Protocol

import httpx

from backend.core.config import Settings
from backend.core.report_contract import REPORT_SECTIONS, report_section_heading_list
from backend.models.structured_review import RawLLMFinding

MAX_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 1.0
RETRYABLE_STATUS_CODES = {408, 409, 429}


class LLMClient(Protocol):
    def generate_review(self, prompt: str) -> str:
        ...


class MockLLMClient:
    def generate_review(self, prompt: str) -> str:
        file_count_hint = self._extract_after(prompt, "Analyzed files:")
        language_hint = self._extract_after(prompt, "Repository language:") or "source"
        entry_points = self._extract_after(prompt, "- Entry Points:") or "none detected"
        core_modules = self._extract_after(prompt, "- Core Modules:") or "none detected"
        supporting_modules = self._extract_after(prompt, "- Supporting Modules:") or "none detected"
        dependency_structure = self._extract_after(prompt, "- Dependency Structure:") or "no resolved graph"
        hubs = self._extract_after(prompt, "- Hub Files:") or "none detected"
        cycles = self._extract_after(prompt, "- Circular Dependencies:") or "none detected"
        repository_type = self._extract_after(prompt, "- Repository Type:")
        risk_hotspots = self._extract_items(
            prompt,
            "Risk Hotspots:",
            {"Recommended Reading Order:"},
        )
        refactoring_candidates = self._extract_items(
            prompt,
            "Refactoring Candidates:",
            {"Architecture Summary Context:"},
        )
        if not repository_type or repository_type == "Software repository":
            repository_type = f"{language_hint} application"
        architecture, code_smells, maintainability, refactoring = REPORT_SECTIONS
        smell_lines = risk_hotspots[:3] or [
            "No concentrated structural hotspot was detected in the summarized repository context."
        ]
        refactoring_lines = refactoring_candidates[:3] or [
            "Preserve current module boundaries until a specific change exposes a clearer extraction point."
        ]
        return (
            f"# {architecture}\n"
            f"The repository appears to be a {repository_type} ({language_hint}) composed of "
            f"{file_count_hint or 'multiple'} analyzed modules. Entry points are {entry_points}. "
            f"Core modules are {core_modules}, while supporting modules are {supporting_modules}. "
            f"The dependency structure has {dependency_structure}. "
            f"High fan-in hubs are {hubs}; circular dependencies are {cycles}.\n\n"
            f"# {code_smells}\n"
            + "\n".join(f"- {finding}" for finding in smell_lines)
            + "\n\n"
            f"# {maintainability}\n"
            f"- Dependency structure: {dependency_structure}.\n"
            f"- Hub evidence: {hubs}; cycle evidence: {cycles}.\n"
            "- Keep tests focused on the boundaries identified by these repository signals.\n\n"
            f"# {refactoring}\n"
            + "\n".join(f"- {candidate}" for candidate in refactoring_lines)
            + "\n"
        )

    def generate_structured_findings(self, prompt: str) -> list[RawLLMFinding]:
        evidence_ids = list(dict.fromkeys(re.findall(r"\bev_[a-f0-9]{20}\b", prompt)))
        if not evidence_ids:
            return []
        category = self._extract_after(prompt, "Review category:") or "architecture"
        category = category.split(".", 1)[0].strip()
        title_by_category = {
            "architecture": "Evidence-grounded architecture boundary",
            "code_smell": "Evidence-grounded code smell",
            "maintainability": "Evidence-grounded maintainability risk",
            "refactor": "Evidence-grounded refactoring candidate",
        }
        recommendation_by_category = {
            "architecture": "Add contract tests around the boundary before refactoring.",
            "code_smell": "Inspect the cited code path and reduce the highest-complexity responsibility first.",
            "maintainability": "Stabilize the cited dependency boundary and cover it with focused tests.",
            "refactor": "Extract the cited responsibility behind a smaller interface.",
        }
        return [
            RawLLMFinding(
                title=title_by_category.get(category, "Evidence-grounded repository finding"),
                description=(
                    "The selected evidence highlights a repository concern that should be reviewed "
                    "before changing entry points, core modules, shared dependencies, or refactoring boundaries."
                ),
                category=category,
                severity="medium",
                confidence=0.72,
                recommendation=recommendation_by_category.get(
                    category,
                    "Review the cited evidence before changing code.",
                ),
                evidence_ids=evidence_ids[:3],
            )
        ]

    @staticmethod
    def _extract_after(prompt: str, label: str) -> str | None:
        for line in prompt.splitlines():
            if line.startswith(label):
                return line.split(":", 1)[1].strip()
        return None

    @staticmethod
    def _extract_items(
        prompt: str,
        heading: str,
        stop_headings: set[str],
    ) -> list[str]:
        collecting = False
        items: list[str] = []
        for line in prompt.splitlines():
            if line == heading:
                collecting = True
                continue
            if collecting and line in stop_headings:
                break
            if collecting and line.startswith("- "):
                items.append(line.removeprefix("- ").strip())
        return items


class OpenAICompatibleClient:
    def __init__(
        self,
        settings: Settings,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self.sleep = sleep

    def generate_review(self, prompt: str) -> str:
        api_key = self.settings.openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is missing. Set USE_MOCK_LLM=true to run without an API.")

        url = self.settings.openai_base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.settings.openai_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are CodePilot, an AI code review agent. Return markdown with exactly these "
                        f"top-level headings: {report_section_heading_list()}. Do not add extra sections."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        with httpx.Client(timeout=60) as client:
            for retry_index in range(MAX_RETRIES + 1):
                try:
                    response = client.post(
                        url,
                        headers={"Authorization": f"Bearer {api_key}"},
                        json=payload,
                    )
                    if not self._is_retryable_status(response.status_code):
                        response.raise_for_status()
                        data = response.json()
                        return data["choices"][0]["message"]["content"]
                    if retry_index == MAX_RETRIES:
                        response.raise_for_status()
                except httpx.RequestError:
                    if retry_index == MAX_RETRIES:
                        raise
                self.sleep(RETRY_BASE_DELAY_SECONDS * (2**retry_index))
        raise RuntimeError("LLM request failed without a response.")

    @staticmethod
    def _is_retryable_status(status_code: int) -> bool:
        return status_code in RETRYABLE_STATUS_CODES or status_code >= 500


def build_llm_client(settings: Settings) -> LLMClient:
    if settings.use_mock_llm:
        return MockLLMClient()
    if not settings.enable_real_llm:
        raise RuntimeError("ENABLE_REAL_LLM must be true before a real LLM client can be used.")
    return OpenAICompatibleClient(settings)
