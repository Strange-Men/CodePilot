from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.errors import install_error_handlers
from backend.api.reviews import build_reviews_router
from backend.core.config import Settings, get_settings
from backend.storage.sqlite import ReviewStore
from backend.tasks.runner import ReviewTaskRunner


def create_app(
    settings: Settings,
    store: ReviewStore,
    runner: ReviewTaskRunner,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        try:
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
    application.include_router(build_reviews_router(store, runner))

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


settings = get_settings()
store = ReviewStore(settings.database_path)
runner = ReviewTaskRunner(settings, store)
app = create_app(settings, store, runner)
