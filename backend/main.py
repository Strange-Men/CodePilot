from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.errors import install_error_handlers
from backend.api.reviews import build_reviews_router
from backend.core.config import Settings, get_settings
from backend.core.logging import get_logger
from backend.services.localization_service import (
    LLMTranslator,
    LocalizationService,
    MockTranslator,
)
from backend.storage.sqlite import ReviewStore
from backend.tasks.runner import ReviewTaskRunner

STALE_REVIEW_THRESHOLD = timedelta(minutes=30)
STALE_REVIEW_ERROR = "Review was interrupted before completion."
logger = get_logger(__name__)


def create_app(
    settings: Settings,
    store: ReviewStore,
    runner: ReviewTaskRunner,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
            store.fail_stale_reviews(
                older_than=datetime.now(UTC) - STALE_REVIEW_THRESHOLD,
                error_message=STALE_REVIEW_ERROR,
            )
            yield
        finally:
            runner.shutdown()

    application = FastAPI(title="CodePilot API", version="0.1.0", lifespan=lifespan)
    install_error_handlers(application)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=settings.cors_allow_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    if settings.enable_llm_translation:
        translator = LLMTranslator(settings)
    else:
        translator = MockTranslator()
    localization_service = LocalizationService(store, translator)
    application.include_router(build_reviews_router(store, runner, localization_service))

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


settings = get_settings()
logger.info(
    "startup_config provider=%s model=%s review_engine=%s "
    "agent_mode=%s use_mock_llm=%s enable_real_llm=%s "
    "agent_concurrency=%s speed_mode=%s",
    "mimo" if settings.mimo_api_key else "openai",
    settings.mimo_model_name if settings.mimo_api_key else settings.openai_model,
    settings.review_engine,
    settings.review_agent_mode,
    settings.use_mock_llm,
    settings.enable_real_llm,
    settings.review_agent_concurrency,
    settings.review_speed_mode,
)
store = ReviewStore(settings.database_path)
runner = ReviewTaskRunner(settings, store)
app = create_app(settings, store, runner)
