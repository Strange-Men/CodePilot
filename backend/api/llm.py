from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.core.config import Settings
from backend.llm.client import LLMProvider, get_llm_provider_statuses


class LLMProviderResponse(BaseModel):
    value: LLMProvider
    label: str
    available: bool


def build_llm_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/llm", tags=["llm"])

    @router.get("/providers", response_model=list[LLMProviderResponse])
    def list_llm_providers() -> list[LLMProviderResponse]:
        return [
            LLMProviderResponse(
                value=status.value,
                label=status.label,
                available=status.available,
            )
            for status in get_llm_provider_statuses(settings)
        ]

    return router
