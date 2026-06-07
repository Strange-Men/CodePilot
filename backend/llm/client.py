from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Protocol

import httpx

from backend.core.config import Settings
from backend.core.report_contract import REPORT_SECTIONS, report_section_heading_list

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
        architecture, code_smells, maintainability, refactoring = REPORT_SECTIONS
        return (
            f"# {architecture}\n"
            f"The repository appears to be a {language_hint} application composed of "
            f"{file_count_hint or 'multiple'} analyzed modules. "
            "The code is organized around module-level responsibilities, with classes and functions forming the main "
            "reviewable units. "
            "The current structure is suitable for a portfolio review because entry points, services, and data "
            "definitions can be inspected separately.\n\n"
            f"# {code_smells}\n"
            "- Some modules may be carrying mixed responsibilities when API, parsing, and persistence logic appear "
            "close together.\n"
            "- Files with many functions should be checked for low cohesion and hidden orchestration logic.\n"
            "- Missing or thin docstrings make it harder for a reviewer to understand intent from the code index "
            "alone.\n\n"
            f"# {maintainability}\n"
            "- Error handling should stay explicit at repository boundaries such as cloning, file parsing, and LLM "
            "calls.\n"
            "- Larger files should be split only when there is a clear domain boundary, not just to reduce line "
            "count.\n"
            "- Tests should cover parsing edge cases, failed clone flows, and deterministic mock review generation.\n\n"
            f"# {refactoring}\n"
            "- Keep I/O operations in service modules and pure code analysis in parser or reviewer modules.\n"
            "- Add small integration tests around the complete review workflow before expanding features.\n"
            "- Prefer concise file summaries and repository-level context over sending raw source to the LLM.\n"
        )

    @staticmethod
    def _extract_after(prompt: str, label: str) -> str | None:
        for line in prompt.splitlines():
            if line.startswith(label):
                return line.split(":", 1)[1].strip()
        return None


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
    return OpenAICompatibleClient(settings)
