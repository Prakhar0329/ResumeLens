"""FastAPI application factory.

Run locally from the ``backend/`` directory::

    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import APP_DIR, Settings, get_settings
from app.db import Database
from app.errors import register_exception_handlers
from app.middleware import (
    REQUEST_ID_HEADER,
    InMemoryRateLimiter,
    RequestContextMiddleware,
    configure_logging,
)
from app.services.analyzer import ResumeAnalyzer
from app.services.embedder import Embedder, EmbedderProtocol
from app.services.skill_extractor import SkillExtractor
from app.services.suggestions import VerbLists

logger = logging.getLogger("resumelens.main")

DATA_DIR = APP_DIR / "data"


def build_analyzer(settings: Settings, embedder: EmbedderProtocol | None = None) -> ResumeAnalyzer:
    extractor, spacy_name = SkillExtractor.from_files(DATA_DIR / "skills.json", settings.spacy_model)
    verbs = VerbLists.from_files(DATA_DIR / "weak_verbs.json", DATA_DIR / "strong_verbs.json")
    embedder = embedder or Embedder(
        settings.embedding_model,
        batch_size=settings.embedding_batch_size,
        cache_dir=settings.model_cache_dir,
    )
    return ResumeAnalyzer(settings, extractor, embedder, verbs, spacy_name)


def create_app(settings: Settings | None = None, embedder: EmbedderProtocol | None = None) -> FastAPI:
    """Build the app. ``settings`` and ``embedder`` can be injected (used by tests)."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        db = Database(settings.database_url)
        db.create_all()
        analyzer = build_analyzer(settings, embedder)
        if settings.preload_models:
            analyzer.embedder.load()  # first request is fast; failures surface at startup
        app.state.settings = settings
        app.state.db = db
        app.state.analyzer = analyzer
        app.state.rate_limiter = InMemoryRateLimiter(settings.rate_limit_per_minute)
        logger.info(
            "startup_complete",
            extra={
                "fields": {
                    "version": settings.app_version,
                    "spacy_model": analyzer.spacy_model_name,
                    "embedding_model": settings.embedding_model,
                    "embedder_loaded": analyzer.embedder.loaded,
                    "skills": analyzer.skills.size,
                    "llm_enabled": settings.llm_enabled,
                }
            },
        )
        try:
            yield
        finally:
            db.dispose()

    app = FastAPI(
        title="ResumeLens API",
        version=settings.app_version,
        description=(
            "Match a resume PDF against a job description. Returns a 0-100 score, skill gaps, "
            "per-section similarity, requirement-level explanations and improvement suggestions."
        ),
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER, "Retry-After"],
    )
    app.add_middleware(RequestContextMiddleware)
    app.include_router(router)

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"name": settings.app_name, "docs": "/docs", "health": "/api/v1/health"}

    return app


app = create_app()
