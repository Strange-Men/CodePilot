from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

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
