"""ORM models.

Privacy: only derived results are stored (scores, skills, section scores, suggestions,
requirement-match similarities) plus SHA-256 hashes of the inputs. The resume text is
never persisted; the resume excerpts inside ``requirement_matches`` are redacted before
the result is saved.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    resume_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    jd_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    top_missing_skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # Full (redacted) AnalysisResponse as JSON.
    result: Mapped[dict] = mapped_column(JSON, nullable=False)

    __table_args__ = (Index("ix_analyses_created_at", "created_at"),)
