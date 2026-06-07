from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


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


class ReviewCreateResponse(BaseModel):
    task_id: str


class ReviewStatusResponse(BaseModel):
    task_id: str
    repo_url: str
    status: ReviewStatus
    error: str | None = None
    report_markdown: str | None = None
    export_path: str | None = None


class CodeFileSummary(BaseModel):
    path: str
    classes: list[str] = Field(default_factory=list)
    functions: list[str] = Field(default_factory=list)
    purpose: str
    summary: str
    line_count: int = 0
    function_count: int = 0
    complexity_estimate: int = 0
    importance_score: float = 0.0
    importance_label: str = "Peripheral"
    file_role: str = "Supporting Module"
    is_entry_point: bool = False
    dependencies: list[str] = Field(default_factory=list)
    fan_in: int = 0
    fan_out: int = 0
    in_dependency_cycle: bool = False
    is_hub: bool = False
    is_orphan: bool = False


class RepositoryInsight(BaseModel):
    title: str
    explanation: str
    files: list[str] = Field(default_factory=list)


class RepositoryInsights(BaseModel):
    repository_type: str = "Software repository"
    major_components: list[str] = Field(default_factory=list)
    architecture_overview: list[RepositoryInsight] = Field(default_factory=list)
    risk_hotspots: list[RepositoryInsight] = Field(default_factory=list)
    onboarding_guide: list[RepositoryInsight] = Field(default_factory=list)
    refactoring_candidates: list[RepositoryInsight] = Field(default_factory=list)


class RepositoryContext(BaseModel):
    repo_url: str
    total_python_files: int
    analyzed_files: int
    skipped_files: int
    file_summaries: list[CodeFileSummary]
    repository_summary: str
    language: str = "Python"
    total_lines: int = 0
    avg_complexity: float = 0.0
    entry_points: list[str] = Field(default_factory=list)
    core_modules: list[str] = Field(default_factory=list)
    supporting_modules: list[str] = Field(default_factory=list)
    dependency_edges: dict[str, list[str]] = Field(default_factory=dict)
    circular_dependencies: list[list[str]] = Field(default_factory=list)
    hub_files: list[str] = Field(default_factory=list)
    orphan_files: list[str] = Field(default_factory=list)
    insights: RepositoryInsights = Field(default_factory=RepositoryInsights)

