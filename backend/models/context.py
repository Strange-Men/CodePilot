from __future__ import annotations

from pydantic import BaseModel, Field


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


class InsightReport(BaseModel):
    repository_type: str = "Software repository"
    major_components: list[str] = Field(default_factory=list)
    architecture_overview: list[RepositoryInsight] = Field(default_factory=list)
    risk_hotspots: list[RepositoryInsight] = Field(default_factory=list)
    onboarding_guide: list[RepositoryInsight] = Field(default_factory=list)
    refactoring_candidates: list[RepositoryInsight] = Field(default_factory=list)


class RepositoryInsights(InsightReport):
    """Compatibility name retained for V2.5 imports."""


class RepoMetadata(BaseModel):
    repo_url: str
    total_source_files: int = 0
    analyzed_files: int = 0
    skipped_files: int = 0
    repository_summary: str = ""
    language: str = "Python"
    total_lines: int = 0
    avg_complexity: float = 0.0


class FileAnalysisBundle(BaseModel):
    summaries: list[CodeFileSummary] = Field(default_factory=list)
    entry_points: list[str] = Field(default_factory=list)
    core_modules: list[str] = Field(default_factory=list)
    supporting_modules: list[str] = Field(default_factory=list)


class DependencyStructure(BaseModel):
    edges: dict[str, list[str]] = Field(default_factory=dict)
    circular_dependencies: list[list[str]] = Field(default_factory=list)
    hub_files: list[str] = Field(default_factory=list)
    orphan_files: list[str] = Field(default_factory=list)


class ReviewContext(BaseModel):
    metadata: RepoMetadata
    files: FileAnalysisBundle = Field(default_factory=FileAnalysisBundle)
    dependencies: DependencyStructure = Field(default_factory=DependencyStructure)
    insights: InsightReport = Field(default_factory=InsightReport)

    @property
    def repo_url(self) -> str:
        return self.metadata.repo_url

    @property
    def total_python_files(self) -> int:
        return self.metadata.total_source_files

    @property
    def analyzed_files(self) -> int:
        return self.metadata.analyzed_files

    @property
    def skipped_files(self) -> int:
        return self.metadata.skipped_files

    @property
    def repository_summary(self) -> str:
        return self.metadata.repository_summary

    @property
    def language(self) -> str:
        return self.metadata.language

    @property
    def total_lines(self) -> int:
        return self.metadata.total_lines

    @property
    def avg_complexity(self) -> float:
        return self.metadata.avg_complexity

    @property
    def file_summaries(self) -> list[CodeFileSummary]:
        return self.files.summaries

    @property
    def entry_points(self) -> list[str]:
        return self.files.entry_points

    @property
    def core_modules(self) -> list[str]:
        return self.files.core_modules

    @property
    def supporting_modules(self) -> list[str]:
        return self.files.supporting_modules

    @property
    def dependency_edges(self) -> dict[str, list[str]]:
        return self.dependencies.edges

    @property
    def circular_dependencies(self) -> list[list[str]]:
        return self.dependencies.circular_dependencies

    @property
    def hub_files(self) -> list[str]:
        return self.dependencies.hub_files

    @property
    def orphan_files(self) -> list[str]:
        return self.dependencies.orphan_files


class RepositoryContext(BaseModel):
    """Flat V2.5 context retained at external and extension boundaries."""

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

    def to_review_context(self) -> ReviewContext:
        return ReviewContext(
            metadata=RepoMetadata(
                repo_url=self.repo_url,
                total_source_files=self.total_python_files,
                analyzed_files=self.analyzed_files,
                skipped_files=self.skipped_files,
                repository_summary=self.repository_summary,
                language=self.language,
                total_lines=self.total_lines,
                avg_complexity=self.avg_complexity,
            ),
            files=FileAnalysisBundle(
                summaries=self.file_summaries,
                entry_points=self.entry_points,
                core_modules=self.core_modules,
                supporting_modules=self.supporting_modules,
            ),
            dependencies=DependencyStructure(
                edges=self.dependency_edges,
                circular_dependencies=self.circular_dependencies,
                hub_files=self.hub_files,
                orphan_files=self.orphan_files,
            ),
            insights=InsightReport.model_validate(self.insights.model_dump()),
        )

    @classmethod
    def from_review_context(cls, context: ReviewContext) -> RepositoryContext:
        return cls(
            repo_url=context.repo_url,
            total_python_files=context.total_python_files,
            analyzed_files=context.analyzed_files,
            skipped_files=context.skipped_files,
            file_summaries=context.file_summaries,
            repository_summary=context.repository_summary,
            language=context.language,
            total_lines=context.total_lines,
            avg_complexity=context.avg_complexity,
            entry_points=context.entry_points,
            core_modules=context.core_modules,
            supporting_modules=context.supporting_modules,
            dependency_edges=context.dependency_edges,
            circular_dependencies=context.circular_dependencies,
            hub_files=context.hub_files,
            orphan_files=context.orphan_files,
            insights=RepositoryInsights.model_validate(context.insights.model_dump()),
        )


def as_review_context(context: ReviewContext | RepositoryContext) -> ReviewContext:
    if isinstance(context, ReviewContext):
        return context
    return context.to_review_context()
