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
    "ReviewCreateRequest",
    "ReviewCreateResponse",
    "ReviewProgressSnapshot",
    "ReviewStatus",
    "ReviewStatusResponse",
]

