from __future__ import annotations

import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import httpx

from backend.core.config import Settings
from backend.core.logging import get_logger
from backend.core.report_contract import REPORT_SECTIONS, report_section_heading_list
from backend.models.structured_review import BilingualTextField, DisplayFields, RawLLMFinding

logger = get_logger(__name__)


@dataclass(frozen=True)
class ResolvedLLMConfig:
    """Resolved LLM provider configuration used by OpenAICompatibleClient."""

    provider: str
    model: str
    base_url: str
    api_key: str
    api_key_env_name: str


def resolve_llm_config(settings: Settings) -> ResolvedLLMConfig:
    """Resolve the active LLM provider from application settings.

    Priority: MiMo (when MIMO_API_KEY is set) > OpenAI.
    Returns a config with empty api_key if neither key is available.
    """
    if settings.mimo_api_key:
        return ResolvedLLMConfig(
            provider="mimo",
            model=settings.mimo_model_name,
            base_url=settings.mimo_base_url,
            api_key=settings.mimo_api_key,
            api_key_env_name="MIMO_API_KEY",
        )
    openai_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY", "")
    return ResolvedLLMConfig(
        provider="openai",
        model=settings.openai_model,
        base_url=settings.openai_base_url,
        api_key=openai_key,
        api_key_env_name="OPENAI_API_KEY",
    )


MAX_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 1.0
RETRYABLE_STATUS_CODES = {408, 409, 429}
RETRYABLE_TIMEOUT_CLASSES = (
    httpx.ReadTimeout,
    httpx.ConnectTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
)


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
        impact_by_category = {
            "architecture": (
                "Changes to this boundary may affect multiple consumers "
                "if the interface contract is not preserved."
            ),
            "code_smell": (
                "The cited responsibility may accumulate unrelated "
                "changes, increasing merge conflict risk."
            ),
            "maintainability": (
                "Without focused test coverage, future changes to "
                "this area may introduce silent regressions."
            ),
            "refactor": (
                "Leaving the current structure unaddressed makes "
                "future feature work slower and riskier."
            ),
        }
        first_step_by_category = {
            "architecture": (
                "Add characterization tests covering the current "
                "public interface before restructuring."
            ),
            "code_smell": (
                "Identify the single highest-complexity responsibility "
                "and extract it behind a focused interface."
            ),
            "maintainability": (
                "Add targeted tests for the cited boundary, "
                "then review dependency directions."
            ),
            "refactor": (
                "Write tests that pin current behavior, "
                "then extract the smallest reusable unit."
            ),
        }
        validation_by_category = {
            "architecture": [
                "Run the full test suite before and after any boundary change.",
            ],
            "code_smell": [
                "Run targeted unit tests for the cited module after each extraction step.",
            ],
            "maintainability": [
                "Run the test suite and verify no new warnings or failures appear.",
            ],
            "refactor": [
                "Run the test suite after each incremental extraction.",
            ],
        }
        caveat_by_category = {
            "architecture": (
                "If this boundary is part of a public API, "
                "changing it may break downstream consumers."
            ),
            "code_smell": (
                "Some duplication may be intentional to "
                "preserve independent extension points."
            ),
            "maintainability": (
                "This finding is based on structural signals; "
                "confirm with production behavior before acting."
            ),
            "refactor": (
                "Refactoring should be incremental; avoid large-scope "
                "changes without intermediate verification."
            ),
        }
        title_en = title_by_category.get(category, "Evidence-grounded repository finding")
        description_en = (
            "The selected evidence highlights a repository concern that should be reviewed "
            "before changing entry points, core modules, shared dependencies, or refactoring boundaries."
        )
        recommendation_en = recommendation_by_category.get(
            category,
            "Review the cited evidence before changing code.",
        )
        impact_en = impact_by_category.get(category)
        first_step_en = first_step_by_category.get(category)
        validation_tests_en = validation_by_category.get(category, [])
        confidence_rationale_en = "Based on evidence records provided in the prompt context."
        caveat_en = caveat_by_category.get(category)

        zh_title_map = {
            "architecture": "架构边界需要审查",
            "code_smell": "代码质量问题需要关注",
            "maintainability": "可维护性风险需要改善",
            "refactor": "重构候选需要评估",
        }
        zh_recommendation_map = {
            "architecture": "在重构前为该边界添加契约测试，确保接口行为不变。",
            "code_smell": "检查引用的代码路径，优先降低复杂度最高的职责。",
            "maintainability": "稳定引用的依赖边界，并用针对性测试覆盖。",
            "refactor": "将引用的职责提取到更小的接口中，降低耦合度。",
        }
        zh_impact_map = {
            "architecture": "如果接口契约未被保留，该边界的变更可能影响多个依赖方。",
            "code_smell": "该职责可能积累不相关的变更，增加合并冲突的风险。",
            "maintainability": "缺少针对性测试覆盖时，后续变更可能引入隐蔽的回归问题。",
            "refactor": "不改善当前结构会导致后续功能开发更慢、风险更高。",
        }
        zh_first_step_map = {
            "architecture": "在重构前为当前公共接口添加表征测试，锁定现有行为。",
            "code_smell": "识别复杂度最高的职责，将其提取到独立接口中。",
            "maintainability": "为引用的边界添加针对性测试，然后审查依赖方向是否合理。",
            "refactor": "编写测试锁定当前行为，然后提取最小的可复用单元。",
        }
        zh_validation_map = {
            "architecture": ["在边界变更前后运行完整测试套件，确认无回归。"],
            "code_smell": ["在每个提取步骤后运行引用模块的单元测试。"],
            "maintainability": ["运行测试套件，确认没有新增警告或失败。"],
            "refactor": ["每次增量提取后运行测试套件。"],
        }
        zh_caveat_map = {
            "architecture": "如果该边界属于公共 API，变更可能破坏下游使用者。",
            "code_smell": "部分重复可能是有意为之，以保留独立的扩展点。",
            "maintainability": "该发现基于结构化信号；行动前请结合生产行为确认。",
            "refactor": "重构应渐进式进行，避免未经中间验证的大范围变更。",
        }

        display = DisplayFields(
            en=BilingualTextField(
                title=title_en,
                description=description_en,
                recommendation=recommendation_en,
                impact=impact_en,
                first_step=first_step_en,
                validation_tests=validation_tests_en,
                confidence_rationale=confidence_rationale_en,
                caveat=caveat_en,
            ),
            zh=BilingualTextField(
                title=zh_title_map.get(category, "仓库问题需要关注"),
                description="引用的证据表明该区域存在结构性问题，在修改入口点、核心模块、共享依赖或重构边界前应优先审查。",
                recommendation=zh_recommendation_map.get(category, "修改代码前先审查引用的证据，确认影响范围。"),
                impact=zh_impact_map.get(category),
                first_step=zh_first_step_map.get(category),
                validation_tests=zh_validation_map.get(category, ["运行测试套件，确认没有新增警告或失败。"]),
                confidence_rationale="基于提示上下文中提供的证据记录。",
                caveat=zh_caveat_map.get(category),
            ),
        )

        return [
            RawLLMFinding(
                title=title_en,
                description=description_en,
                category=category,
                severity="medium",
                confidence=0.72,
                recommendation=recommendation_en,
                evidence_ids=evidence_ids[:3],
                impact=impact_en,
                first_step=first_step_en,
                validation_tests=validation_tests_en,
                confidence_rationale=confidence_rationale_en,
                caveat=caveat_en,
                display=display,
            )
        ]

    def generate_grouped_structured_findings(self, prompt: str) -> dict[str, dict[str, object]]:
        """Mock grouped findings for two logical agents in one call.

        Returns a dict keyed by agent role, each containing
        {'findings': [...], 'no_findings_reason': None}.
        """
        # Detect agent roles from prompt sections
        agent_roles = re.findall(r"### Agent: (\w+)", prompt)
        if not agent_roles:
            return {}

        result: dict[str, dict[str, object]] = {}
        for role in agent_roles:
            # Extract category for this agent from the prompt
            category_match = re.search(
                rf"### Agent: {re.escape(role)}\nReview category: (\w+)",
                prompt,
            )
            category = category_match.group(1) if category_match else "general"

            # Find evidence IDs scoped to this agent's section
            section_pattern = rf"### Agent: {re.escape(role)}\n.*?(?=### Agent:|$)"
            section_match = re.search(section_pattern, prompt, re.DOTALL)
            section_text = section_match.group(0) if section_match else prompt
            evidence_ids = list(dict.fromkeys(re.findall(r"\bev_[a-f0-9]{20}\b", section_text)))

            if not evidence_ids:
                result[role] = {"findings": [], "no_findings_reason": "No evidence available."}
                continue

            display = self._build_grouped_display(category)
            result[role] = {
                "findings": [
                    {
                        "title": f"Evidence-grounded {category} finding",
                        "description": (
                            "The selected evidence highlights a repository concern."
                        ),
                        "category": category,
                        "severity": "medium",
                        "confidence": 0.72,
                        "recommendation": "Review the cited evidence before changing code.",
                        "evidence_ids": evidence_ids[:3],
                        "impact": "Structural concern that should be reviewed.",
                        "first_step": "Inspect the cited code path.",
                        "validation_tests": ["Run the test suite after changes."],
                        "confidence_rationale": "Based on evidence records provided.",
                        "caveat": "Confirm with production behavior before acting.",
                        "display": display,
                    }
                ],
                "no_findings_reason": None,
            }
        return result

    def _build_grouped_display(self, category: str) -> dict[str, dict[str, object]]:
        """Build bilingual display fields for a grouped mock finding."""
        en_map = {
            "architecture": ("Architecture boundary review", "The evidence suggests a structural boundary concern."),
            "code_smell": ("Code quality issue detected", "The evidence highlights a code quality pattern."),
            "maintainability": ("Maintainability risk identified", "The evidence shows a maintainability concern."),
            "refactor": ("Refactoring candidate found", "The evidence suggests an extraction opportunity."),
        }
        zh_map = {
            "architecture": ("架构边界需要审查", "证据表明存在结构性边界问题。"),
            "code_smell": ("代码质量问题需要关注", "证据显示存在代码质量模式。"),
            "maintainability": ("可维护性风险需要改善", "证据表明存在可维护性问题。"),
            "refactor": ("重构候选需要评估", "证据表明存在提取机会。"),
        }
        en_title, en_desc = en_map.get(category, ("Repository finding", "Evidence-based concern."))
        zh_title, zh_desc = zh_map.get(category, ("仓库问题需要关注", "基于证据的问题。"))
        return {
            "en": {"title": en_title, "description": en_desc},
            "zh": {"title": zh_title, "description": zh_desc},
        }

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
        *,
        resolved: ResolvedLLMConfig | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self.resolved = resolved or resolve_llm_config(settings)
        self.sleep = sleep
        self._timeout = httpx.Timeout(
            connect=settings.llm_connect_timeout,
            read=settings.llm_read_timeout,
            write=settings.llm_write_timeout,
            pool=settings.llm_pool_timeout,
        )
        self._max_retries = settings.llm_max_retries

    def generate_review(self, prompt: str) -> str:
        api_key = self.resolved.api_key
        if not api_key:
            raise RuntimeError(
                f"{self.resolved.api_key_env_name} is missing. "
                "Set USE_MOCK_LLM=true to run without a real API."
            )

        url = self.resolved.base_url.rstrip("/") + "/chat/completions"
        structured_output = "Return only JSON" in prompt
        system_content = (
            "You are CodePilot, an evidence-grounded code review agent. "
            "Return only valid JSON matching the schema in the user prompt."
            if structured_output
            else (
                "You are CodePilot, an AI code review agent. Return markdown with exactly these "
                f"top-level headings: {report_section_heading_list()}. Do not add extra sections."
            )
        )
        payload = {
            "model": self.resolved.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_content,
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        provider = self.resolved.provider
        llm_started = time.perf_counter()
        with httpx.Client(timeout=self._timeout) as client:
            for retry_index in range(self._max_retries + 1):
                try:
                    response = client.post(
                        url,
                        headers={"Authorization": f"Bearer {api_key}"},
                        json=payload,
                    )
                    if not self._is_retryable_status(response.status_code):
                        response.raise_for_status()
                        data = response.json()
                        duration_ms = round((time.perf_counter() - llm_started) * 1000, 1)
                        logger.info(
                            "performance_event stage=llm_request duration_ms=%s "
                            "success=true retries=%d provider=%s model=%s",
                            duration_ms, retry_index, provider,
                            self.resolved.model,
                        )
                        return data["choices"][0]["message"]["content"]
                    if retry_index == self._max_retries:
                        response.raise_for_status()
                except httpx.TimeoutException as exc:
                    timeout_type = type(exc).__name__
                    logger.warning(
                        "performance_event stage=llm_request success=false "
                        "provider=%s model=%s timeout_type=%s "
                        "attempt=%d max_retries=%d",
                        provider,
                        self.resolved.model,
                        timeout_type,
                        retry_index + 1,
                        self._max_retries,
                    )
                    if retry_index == self._max_retries:
                        duration_ms = round(
                            (time.perf_counter() - llm_started) * 1000, 1
                        )
                        logger.info(
                            "performance_event stage=llm_request "
                            "duration_ms=%s success=false retries=%d "
                            "provider=%s model=%s",
                            duration_ms, retry_index, provider,
                            self.resolved.model,
                        )
                        raise
                except httpx.RequestError as exc:
                    logger.warning(
                        "performance_event stage=llm_request success=false "
                        "provider=%s model=%s error_type=%s attempt=%d",
                        provider,
                        self.resolved.model,
                        type(exc).__name__,
                        retry_index + 1,
                    )
                    if retry_index == self._max_retries:
                        duration_ms = round(
                            (time.perf_counter() - llm_started) * 1000, 1
                        )
                        logger.info(
                            "performance_event stage=llm_request "
                            "duration_ms=%s success=false retries=%d "
                            "provider=%s model=%s",
                            duration_ms, retry_index, provider,
                            self.resolved.model,
                        )
                        raise
                self.sleep(RETRY_BASE_DELAY_SECONDS * (2**retry_index))
        raise RuntimeError("LLM request failed without a response.")

    def _provider_label(self) -> str:
        return self.resolved.provider

    @staticmethod
    def _is_retryable_status(status_code: int) -> bool:
        return status_code in RETRYABLE_STATUS_CODES or status_code >= 500


def build_llm_client(settings: Settings) -> LLMClient:
    if settings.use_mock_llm:
        return MockLLMClient()
    if not settings.enable_real_llm:
        raise RuntimeError("ENABLE_REAL_LLM must be true before a real LLM client can be used.")
    resolved = resolve_llm_config(settings)
    if not resolved.api_key:
        raise RuntimeError(
            f"{resolved.api_key_env_name} is missing. "
            "Set USE_MOCK_LLM=true to run without a real API."
        )
    return OpenAICompatibleClient(settings, resolved=resolved)


def build_llm_client_for_mode(settings: Settings, llm_mode: str) -> LLMClient:
    if llm_mode == "mock":
        return MockLLMClient()
    if llm_mode == "mimo":
        if not settings.mimo_api_key:
            raise RuntimeError(
                "MIMO_API_KEY is missing. Set USE_MOCK_LLM=true to run without a real API."
            )
        resolved = ResolvedLLMConfig(
            provider="mimo",
            model=settings.mimo_model_name,
            base_url=settings.mimo_base_url,
            api_key=settings.mimo_api_key,
            api_key_env_name="MIMO_API_KEY",
        )
        return OpenAICompatibleClient(settings, resolved=resolved)
    raise ValueError(f"Unknown llm_mode: {llm_mode}")
