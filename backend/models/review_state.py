from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend.models.context import EvidenceRecord, ReviewContext
from backend.models.structured_review import ReviewFinding

AgentStatus = Literal["completed", "failed"]
ValidationStatus = Literal["validated", "failed", "not_applicable"]


class AgentExecutionState(BaseModel):
    agent_id: str
    status: AgentStatus
    findings: list[ReviewFinding] = Field(default_factory=list)
    error: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    llm_calls: int | None = None
    validation_status: ValidationStatus = "validated"
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class EvidenceReference(BaseModel):
    evidence_id: str
    file_path: str
    start_line: int
    end_line: int
    kind: str
    symbols: list[str] = Field(default_factory=list)

    @classmethod
    def from_record(cls, record: EvidenceRecord) -> EvidenceReference:
        return cls(
            evidence_id=record.evidence_id,
            file_path=record.file_path,
            start_line=record.start_line,
            end_line=record.end_line,
            kind=record.kind,
            symbols=record.symbols,
        )


class ReviewContextSummary(BaseModel):
    repo_url: str
    language: str
    total_source_files: int
    analyzed_files: int
    skipped_files: int
    repository_summary: str

    @classmethod
    def from_context(cls, context: ReviewContext) -> ReviewContextSummary:
        return cls(
            repo_url=context.repo_url,
            language=context.language,
            total_source_files=context.total_source_files,
            analyzed_files=context.analyzed_files,
            skipped_files=context.skipped_files,
            repository_summary=context.repository_summary,
        )


class PersistedReviewState(BaseModel):
    task_id: str | None = None
    context: ReviewContextSummary
    evidence_index: list[EvidenceReference] = Field(default_factory=list)
    evidence_bundles: dict[str, list[str]] = Field(default_factory=dict)
    agent_results: list[AgentExecutionState] = Field(default_factory=list)
    validated_findings: list[ReviewFinding] = Field(default_factory=list)
    errors: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class ReviewState(BaseModel):
    task_id: str | None = None
    context: ReviewContext
    evidence_bundles: dict[str, list[EvidenceRecord]] = Field(default_factory=dict)
    agent_results: list[AgentExecutionState] = Field(default_factory=list)
    validated_findings: list[ReviewFinding] = Field(default_factory=list)
    errors: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    def safe_snapshot(self) -> PersistedReviewState:
        return PersistedReviewState(
            task_id=self.task_id,
            context=ReviewContextSummary.from_context(self.context),
            evidence_index=[
                EvidenceReference.from_record(record)
                for record in self.context.evidence
            ],
            evidence_bundles={
                agent_id: [record.evidence_id for record in records]
                for agent_id, records in self.evidence_bundles.items()
            },
            agent_results=self.agent_results,
            validated_findings=self.validated_findings,
            errors=self.errors,
            metadata=self.metadata,
        )
