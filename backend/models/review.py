import os
from enum import StrEnum
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, HttpUrl, field_validator

from backend.models.context import (
    CodeFileSummary,
    DependencyStructure,
    FileAnalysisBundle,
    InsightReport,
    RepoMetadata,
    RepositoryContext,
    RepositoryInsight,
    RepositoryInsights,
    ReviewContext,
)


class ReviewStatus(StrEnum):
    pending = "pending"
    cloning = "cloning"
    parsing = "parsing"
    summarizing = "summarizing"
    reviewing = "reviewing"
    completed = "completed"
    failed = "failed"


class ReviewCreateRequest(BaseModel):
    repo_url: HttpUrl = Field(description="GitHub repository URL to review")
    llm_mode: str = Field(default="mock", pattern="^(mock|mimo)$", description="LLM mode: mock or mimo")
    llm_provider: Literal["mimo", "doubao", "deepseek"] | None = Field(
        default=None,
        description="Real LLM provider used when llm_mode is mimo",
    )

    @field_validator("repo_url")
    @classmethod
    def validate_github_repository_url(cls, value: HttpUrl) -> HttpUrl:
        parsed = urlparse(str(value))
        path_parts = [part for part in parsed.path.split("/") if part]
        if (
            os.getenv("CODEPILOT_ALLOW_LOCAL_SMOKE_REPO", "").lower() == "true"
            and parsed.scheme == "http"
            and parsed.username == "github.com"
            and (parsed.hostname or "").lower() in {"127.0.0.1", "localhost"}
            and len(path_parts) == 1
        ):
            return value
        if (
            parsed.scheme != "https"
            or (parsed.hostname or "").lower() != "github.com"
            or len(path_parts) != 2
            or not all(path_parts)
            or bool(parsed.query)
            or bool(parsed.fragment)
        ):
            raise ValueError("Use an HTTPS GitHub repository URL such as https://github.com/owner/repository")
        return value


class ReviewCreateResponse(BaseModel):
    task_id: str
    llm_mode: str = "mock"
    llm_provider: Literal["mimo", "doubao", "deepseek"] | None = None


class AgentProgressItem(BaseModel):
    order: int
    label: str
    agent_id: str
    status: Literal["pending", "running", "completed", "failed", "skipped"] = "pending"
    findings_count: int | None = None
    evidence_count: int | None = None
    error: str | None = None


class ReviewProgressSnapshot(BaseModel):
    current_phase: str
    current_agent_id: str | None = None
    total_agents: int
    completed_agents: int
    agents: list[AgentProgressItem]


class ReviewStatusResponse(BaseModel):
    task_id: str
    repo_url: str
    status: ReviewStatus
    error: str | None = None
    report_markdown: str | None = None
    export_path: str | None = None
    progress: ReviewProgressSnapshot | None = None


class ReviewEvidenceRefResponse(BaseModel):
    evidence_id: str
    file_path: str | None = None
    symbol_name: str | None = None
    start_line: int
    end_line: int


class ReviewFindingDisplayText(BaseModel):
    title: str | None = None
    description: str | None = None
    recommendation: str | None = None
    impact: str | None = None
    first_step: str | None = None
    validation_tests: list[str] = Field(default_factory=list)
    confidence_rationale: str | None = None
    caveat: str | None = None


class ReviewFindingDisplay(BaseModel):
    en: ReviewFindingDisplayText = Field(default_factory=ReviewFindingDisplayText)
    zh: ReviewFindingDisplayText = Field(default_factory=ReviewFindingDisplayText)


class ReviewFindingResponse(BaseModel):
    finding_id: str
    finding_index: int
    section: str
    title: str
    description: str
    severity: str
    category: str | None = None
    confidence: float
    recommendation: str | None = None
    files: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_refs: list[ReviewEvidenceRefResponse] = Field(default_factory=list)
    validation_status: str | None = None
    impact: str | None = None
    first_step: str | None = None
    validation_tests: list[str] = Field(default_factory=list)
    confidence_rationale: str | None = None
    caveat: str | None = None
    display: ReviewFindingDisplay | None = None


class ReviewFindingsResponse(BaseModel):
    task_id: str
    findings: list[ReviewFindingResponse] = Field(default_factory=list)
    evidence_display_map: dict[str, str] = Field(default_factory=dict)


class ReviewAgentStateResponse(BaseModel):
    order: int
    agent_id: str
    label: str
    status: str
    findings_count: int
    evidence_count: int
    severity_mix: dict[str, int]
    average_confidence: float | None = None
    error: str | None = None


class ReviewAgentStatesResponse(BaseModel):
    task_id: str
    agents: list[ReviewAgentStateResponse] = Field(default_factory=list)


__all__ = [
    "CodeFileSummary",
    "DependencyStructure",
    "FileAnalysisBundle",
    "InsightReport",
    "RepoMetadata",
    "RepositoryContext",
    "RepositoryInsight",
    "RepositoryInsights",
    "ReviewContext",
    "AgentProgressItem",
    "ReviewAgentStateResponse",
    "ReviewAgentStatesResponse",
    "ReviewCreateRequest",
    "ReviewCreateResponse",
    "ReviewEvidenceRefResponse",
    "ReviewFindingDisplay",
    "ReviewFindingDisplayText",
    "ReviewFindingResponse",
    "ReviewFindingsResponse",
    "ReviewProgressSnapshot",
    "ReviewStatus",
    "ReviewStatusResponse",
]
