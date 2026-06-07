from enum import StrEnum
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

    @field_validator("repo_url")
    @classmethod
    def validate_github_repository_url(cls, value: HttpUrl) -> HttpUrl:
        parsed = urlparse(str(value))
        path_parts = [part for part in parsed.path.split("/") if part]
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


class ReviewStatusResponse(BaseModel):
    task_id: str
    repo_url: str
    status: ReviewStatus
    error: str | None = None
    report_markdown: str | None = None
    export_path: str | None = None

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
    "ReviewCreateRequest",
    "ReviewCreateResponse",
    "ReviewStatus",
    "ReviewStatusResponse",
]

