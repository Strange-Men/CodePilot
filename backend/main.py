from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.reviews import build_reviews_router
from backend.core.config import get_settings
from backend.storage.sqlite import ReviewStore
from backend.tasks.runner import ReviewTaskRunner


settings = get_settings()
store = ReviewStore(settings.database_path)
runner = ReviewTaskRunner(settings, store)

app = FastAPI(title="CodePilot API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(build_reviews_router(store, runner))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
