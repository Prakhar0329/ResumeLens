"""Application configuration.

Every tunable lives here and can be overridden with an environment variable of the
same name in upper case (for example ``WEIGHT_SKILL=0.6``) or via a ``.env`` file in
the ``backend/`` directory. See ``.env.example`` for the full list.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BACKEND_DIR / "app"
DEFAULT_DB_PATH = BACKEND_DIR / "data" / "resumelens.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- General -------------------------------------------------------------
    app_name: str = "ResumeLens"
    app_version: str = "1.0.0"
    environment: str = "development"
    log_level: str = "INFO"

    # --- Storage ---------------------------------------------------------------
    database_url: str = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"

    # --- HTTP ------------------------------------------------------------------
    cors_origins: str = "http://localhost:3000"
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = Field(default=20, ge=1)

    # --- Models ----------------------------------------------------------------
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_batch_size: int = Field(default=32, ge=1)
    model_cache_dir: str | None = None
    spacy_model: str = "en_core_web_sm"
    preload_models: bool = True

    # --- Input limits ------------------------------------------------------------
    max_upload_mb: float = Field(default=5.0, gt=0)
    max_pdf_pages: int = Field(default=10, ge=1)
    min_jd_chars: int = Field(default=100, ge=1)
    max_jd_chars: int = Field(default=15000, ge=1)

    # --- Chunking ----------------------------------------------------------------
    chunk_min_words: int = Field(default=15, ge=1)
    chunk_max_words: int = Field(default=80, ge=5)
    max_jd_requirements: int = Field(default=60, ge=1)
    top_requirement_matches: int = Field(default=10, ge=1)
    max_extra_skills: int = Field(default=15, ge=0)

    # --- Scoring weights (normalised to sum to 1 at scoring time) ----------------
    weight_skill: float = Field(default=0.50, ge=0)
    weight_semantic: float = Field(default=0.35, ge=0)
    weight_keyword: float = Field(default=0.15, ge=0)

    # Per-requirement-type weights for skill coverage.
    skill_weight_required: float = Field(default=2.0, ge=0)
    skill_weight_unspecified: float = Field(default=1.0, ge=0)
    skill_weight_preferred: float = Field(default=0.5, ge=0)

    # Raw cosine values are rescaled linearly from [floor, ceiling] to [0, 100].
    semantic_floor: float = 0.20
    semantic_ceiling: float = 0.75
    keyword_floor: float = 0.02
    keyword_ceiling: float = 0.40

    # --- Optional LLM bullet rewriter --------------------------------------------
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-4-5-20251001"
    llm_max_tokens: int = Field(default=300, ge=50)
    llm_timeout_seconds: float = Field(default=30.0, gt=0)

    @model_validator(mode="after")
    def _check_ranges(self) -> Settings:
        if self.semantic_floor >= self.semantic_ceiling:
            raise ValueError("SEMANTIC_FLOOR must be lower than SEMANTIC_CEILING")
        if self.keyword_floor >= self.keyword_ceiling:
            raise ValueError("KEYWORD_FLOOR must be lower than KEYWORD_CEILING")
        if self.weight_skill + self.weight_semantic + self.weight_keyword <= 0:
            raise ValueError("At least one of WEIGHT_SKILL/WEIGHT_SEMANTIC/WEIGHT_KEYWORD must be > 0")
        if self.min_jd_chars >= self.max_jd_chars:
            raise ValueError("MIN_JD_CHARS must be lower than MAX_JD_CHARS")
        if self.chunk_min_words >= self.chunk_max_words:
            raise ValueError("CHUNK_MIN_WORDS must be lower than CHUNK_MAX_WORDS")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key and self.anthropic_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
