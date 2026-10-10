"""Pydantic v2 request/response models.

These names and fields are the API contract. The frontend mirrors them exactly in
``frontend/src/types/api.ts``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Verdict = Literal["Weak match", "Partial match", "Strong match", "Excellent match"]
RequirementType = Literal["required", "preferred", "unspecified"]
SectionName = Literal["summary", "experience", "projects", "skills", "education", "other"]
Priority = Literal["high", "medium", "low"]
SkillCategory = Literal[
    "language",
    "frontend",
    "backend",
    "database",
    "cloud",
    "devops",
    "data_ml",
    "testing",
    "tools",
    "concepts",
    "soft_skill",
]
SuggestionType = Literal[
    "missing_required_skill",
    "missing_required_skills_summary",
    "missing_preferred_skills",
    "no_skills_in_jd",
    "no_quantified_metrics",
    "few_quantified_metrics",
    "resume_too_short",
    "resume_too_long",
    "skills_section_missing",
    "experience_section_missing",
    "no_sections_detected",
    "no_bullets",
    "weak_action_verbs",
    "few_strong_verbs",
    "long_bullets",
    "low_semantic_alignment",
    "low_keyword_overlap",
]


class _Model(BaseModel):
    # protected_namespaces=() allows the public field name ``model_info``.
    model_config = ConfigDict(protected_namespaces=())


class SkillItem(_Model):
    name: str
    category: SkillCategory
    in_jd_as: RequirementType


class ExtraSkill(_Model):
    name: str
    category: SkillCategory


class ScoreWeights(_Model):
    skill_coverage: float = Field(ge=0, le=1)
    semantic_similarity: float = Field(ge=0, le=1)
    keyword_overlap: float = Field(ge=0, le=1)


class ScoreBreakdown(_Model):
    skill_coverage: float = Field(ge=0, le=100)
    semantic_similarity: float = Field(ge=0, le=100)
    keyword_overlap: float = Field(ge=0, le=100)
    weights: ScoreWeights
    raw_semantic_cosine: float = Field(description="Mean best-match cosine before rescaling.")
    raw_keyword_cosine: float = Field(description="TF-IDF cosine before rescaling.")
    skill_weight_redistributed: bool = Field(
        description="True when the JD had no detectable skills and the skill weight was redistributed."
    )


class SectionScore(_Model):
    section: SectionName
    similarity: float = Field(description="Mean best-match cosine of JD requirements against this section.")
    score: float = Field(ge=0, le=100, description="Similarity rescaled with the semantic band.")
    word_count: int = Field(ge=0)


class RequirementMatch(_Model):
    requirement: str
    requirement_type: RequirementType
    best_chunk: str | None = Field(description="Best-matching resume excerpt; null once stored (redacted).")
    best_chunk_section: SectionName | None
    similarity: float


class Suggestion(_Model):
    type: SuggestionType
    priority: Priority
    message: str


class ResumeStats(_Model):
    pages: int = Field(ge=0)
    word_count: int = Field(ge=0)
    bullet_count: int = Field(ge=0)
    bullets_with_numbers_pct: float = Field(ge=0, le=100)


class ModelInfo(_Model):
    embedding_model: str
    spacy_model: str
    version: str


class AnalysisResponse(_Model):
    analysis_id: str
    created_at: datetime
    overall_score: float = Field(ge=0, le=100)
    verdict: Verdict
    score_breakdown: ScoreBreakdown
    matched_skills: list[SkillItem]
    missing_skills: list[SkillItem]
    extra_skills: list[ExtraSkill]
    section_scores: list[SectionScore]
    requirement_matches: list[RequirementMatch]
    suggestions: list[Suggestion]
    resume_stats: ResumeStats
    model_info: ModelInfo
    stored: bool = Field(description="Whether this analysis was saved to history.")
    redacted: bool = Field(description="True when resume excerpts were removed (stored copies).")


class AnalysisSummary(_Model):
    analysis_id: str
    created_at: datetime
    overall_score: float
    verdict: Verdict
    top_missing_skills: list[str]


class AnalysisList(_Model):
    items: list[AnalysisSummary]
    total: int
    limit: int
    offset: int


class DeleteResponse(_Model):
    deleted: int


class ModelStatus(_Model):
    spacy_loaded: bool
    spacy_model: str
    embedder_loaded: bool
    embedding_model: str
    skills_count: int


class BandConfig(_Model):
    floor: float
    ceiling: float


class SkillPriorityWeights(_Model):
    required: float
    unspecified: float
    preferred: float


class VerdictThresholds(_Model):
    partial: float
    strong: float
    excellent: float


class InputLimits(_Model):
    max_upload_mb: float
    max_pdf_pages: int
    min_jd_chars: int
    max_jd_chars: int


class ScoringConfig(_Model):
    weights: ScoreWeights
    semantic_band: BandConfig
    keyword_band: BandConfig
    skill_priority_weights: SkillPriorityWeights
    verdict_thresholds: VerdictThresholds
    limits: InputLimits


class HealthResponse(_Model):
    status: Literal["ok", "degraded"]
    version: str
    models: ModelStatus
    llm_enabled: bool
    config: ScoringConfig


class RewriteRequest(_Model):
    bullet: str = Field(min_length=5, max_length=600)
    target_skills: list[str] = Field(default_factory=list, max_length=10)
    jd_context: str | None = Field(default=None, max_length=2000)


class RewriteResponse(_Model):
    original: str
    rewritten: str
    placeholders: list[str] = Field(description="Placeholders such as [X%] the user must fill in.")
    model: str


class ErrorDetail(_Model):
    code: str
    message: str


class ErrorResponse(_Model):
    error: ErrorDetail
