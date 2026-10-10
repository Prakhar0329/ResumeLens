"""HTTP routes under ``/api/v1``."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import FileTooLargeError, NotFoundError
from app.middleware import client_ip
from app.models import Analysis
from app.schemas import (
    AnalysisList,
    AnalysisResponse,
    AnalysisSummary,
    BandConfig,
    DeleteResponse,
    ErrorResponse,
    HealthResponse,
    InputLimits,
    ModelStatus,
    RewriteRequest,
    RewriteResponse,
    ScoreWeights,
    ScoringConfig,
    SkillPriorityWeights,
    VerdictThresholds,
)
from app.services import llm_rewriter
from app.services.analyzer import ResumeAnalyzer, redact_for_storage, sha256_hex
from app.services.scorer import VERDICT_EXCELLENT, VERDICT_PARTIAL, VERDICT_STRONG, Weights

router = APIRouter(prefix="/api/v1")

ERRORS = {code: {"model": ErrorResponse} for code in (400, 404, 413, 415, 422, 429, 500, 501, 502)}


# ----------------------------------------------------------------- dependencies
def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_analyzer(request: Request) -> ResumeAnalyzer:
    return request.app.state.analyzer


def get_db(request: Request) -> Iterator[Session]:
    yield from request.app.state.db.session()


def rate_limit(request: Request) -> None:
    settings: Settings = request.app.state.settings
    if settings.rate_limit_enabled:
        # Separate budgets per endpoint so rewrite calls do not consume analyze quota.
        request.app.state.rate_limiter.check(f"{request.url.path}:{client_ip(request)}")


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


# ----------------------------------------------------------------------- health
@router.get("/health", response_model=HealthResponse, tags=["system"])
def health(request: Request) -> HealthResponse:
    settings: Settings = request.app.state.settings
    analyzer: ResumeAnalyzer = request.app.state.analyzer
    weights = Weights(settings.weight_skill, settings.weight_semantic, settings.weight_keyword).normalised()
    spacy_loaded = analyzer.spacy_model_name != "blank:en"
    embedder_loaded = analyzer.embedder.loaded
    return HealthResponse(
        status="ok" if (spacy_loaded and embedder_loaded) else "degraded",
        version=settings.app_version,
        models=ModelStatus(
            spacy_loaded=spacy_loaded,
            spacy_model=analyzer.spacy_model_name,
            embedder_loaded=embedder_loaded,
            embedding_model=settings.embedding_model,
            skills_count=analyzer.skills.size,
        ),
        llm_enabled=settings.llm_enabled,
        config=ScoringConfig(
            weights=ScoreWeights(
                skill_coverage=round(weights.skill, 4),
                semantic_similarity=round(weights.semantic, 4),
                keyword_overlap=round(weights.keyword, 4),
            ),
            semantic_band=BandConfig(floor=settings.semantic_floor, ceiling=settings.semantic_ceiling),
            keyword_band=BandConfig(floor=settings.keyword_floor, ceiling=settings.keyword_ceiling),
            skill_priority_weights=SkillPriorityWeights(
                required=settings.skill_weight_required,
                unspecified=settings.skill_weight_unspecified,
                preferred=settings.skill_weight_preferred,
            ),
            verdict_thresholds=VerdictThresholds(
                partial=VERDICT_PARTIAL, strong=VERDICT_STRONG, excellent=VERDICT_EXCELLENT
            ),
            limits=InputLimits(
                max_upload_mb=settings.max_upload_mb,
                max_pdf_pages=settings.max_pdf_pages,
                min_jd_chars=settings.min_jd_chars,
                max_jd_chars=settings.max_jd_chars,
            ),
        ),
    )


# ---------------------------------------------------------------------- analyze
def _persist(db: Session, response: AnalysisResponse, resume_hash: str, jd_hash: str) -> None:
    stored = redact_for_storage(response)
    db.add(
        Analysis(
            id=stored.analysis_id,
            created_at=stored.created_at,
            overall_score=stored.overall_score,
            verdict=stored.verdict,
            resume_sha256=resume_hash,
            jd_sha256=jd_hash,
            top_missing_skills=[s.name for s in stored.missing_skills[:3]],
            result=stored.model_dump(mode="json"),
        )
    )
    db.commit()


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    responses=ERRORS,
    dependencies=[Depends(rate_limit)],
    tags=["analysis"],
    summary="Analyse a resume PDF against a job description",
)
async def analyze(
    resume: UploadFile = File(..., description="Resume as a text-based PDF (max 5 MB, 10 pages)."),
    jd_text: str = Form(..., description="Job description as plain text (100-15,000 characters)."),
    save: bool = Form(True, description="Store the (redacted) result in history."),
    analyzer: ResumeAnalyzer = Depends(get_analyzer),
    settings: Settings = Depends(get_settings_dep),
    db: Session = Depends(get_db),
) -> AnalysisResponse:
    max_bytes = settings.max_upload_bytes
    data = await resume.read(max_bytes + 1)  # never read more than the limit + 1 byte
    await resume.close()
    if len(data) > max_bytes:
        raise FileTooLargeError(f"Resume must be at most {settings.max_upload_mb:g} MB.")
    # Validate the JD before the expensive PDF work so bad input fails fast.
    analyzer.validate_jd(jd_text)

    response = await run_in_threadpool(analyzer.analyze, data, jd_text)
    if save:
        await run_in_threadpool(_persist, db, response, sha256_hex(data), sha256_hex(jd_text.strip()))
        response.stored = True
    return response


# ---------------------------------------------------------------------- history
@router.get("/analyses", response_model=AnalysisList, tags=["history"])
def list_analyses(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> AnalysisList:
    total = db.scalar(select(func.count()).select_from(Analysis)) or 0
    rows = db.scalars(select(Analysis).order_by(Analysis.created_at.desc()).limit(limit).offset(offset)).all()
    items = [
        AnalysisSummary(
            analysis_id=row.id,
            created_at=_as_utc(row.created_at),
            overall_score=row.overall_score,
            verdict=row.verdict,  # type: ignore[arg-type]
            top_missing_skills=list(row.top_missing_skills or []),
        )
        for row in rows
    ]
    return AnalysisList(items=items, total=total, limit=limit, offset=offset)


@router.get("/analyses/{analysis_id}", response_model=AnalysisResponse, responses=ERRORS, tags=["history"])
def get_analysis(analysis_id: str, db: Session = Depends(get_db)) -> AnalysisResponse:
    row = db.get(Analysis, analysis_id)
    if row is None:
        raise NotFoundError(f"Analysis {analysis_id} was not found.")
    return AnalysisResponse.model_validate(row.result)


@router.delete("/analyses/{analysis_id}", response_model=DeleteResponse, responses=ERRORS, tags=["history"])
def delete_analysis(analysis_id: str, db: Session = Depends(get_db)) -> DeleteResponse:
    row = db.get(Analysis, analysis_id)
    if row is None:
        raise NotFoundError(f"Analysis {analysis_id} was not found.")
    db.delete(row)
    db.commit()
    return DeleteResponse(deleted=1)


@router.delete("/analyses", response_model=DeleteResponse, tags=["history"])
def delete_all_analyses(db: Session = Depends(get_db)) -> DeleteResponse:
    result = db.execute(delete(Analysis))
    db.commit()
    return DeleteResponse(deleted=result.rowcount or 0)


# ---------------------------------------------------------------------- rewrite
@router.post(
    "/rewrite-bullet",
    response_model=RewriteResponse,
    responses=ERRORS,
    dependencies=[Depends(rate_limit)],
    tags=["optional"],
    summary="Rewrite one resume bullet with an LLM (requires ANTHROPIC_API_KEY)",
)
def rewrite_bullet(body: RewriteRequest, settings: Settings = Depends(get_settings_dep)) -> RewriteResponse:
    result = llm_rewriter.rewrite(body.bullet, body.target_skills, body.jd_context, settings=settings)
    return RewriteResponse(
        original=result.original,
        rewritten=result.rewritten,
        placeholders=result.placeholders,
        model=result.model,
    )
