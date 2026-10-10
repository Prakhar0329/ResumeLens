"""Pipeline orchestrator: PDF bytes + JD text -> AnalysisResponse.

Steps: parse PDF -> clean -> split sections -> chunk resume / split JD requirements ->
extract skills -> embed (one batched call per request) -> TF-IDF baseline -> score ->
suggestions. All signal-level functions are also exposed via ``compute_signals`` so the
evaluation harness can score labelled pairs with exactly the production code.
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np

from app.config import Settings
from app.errors import InvalidJobDescriptionError
from app.schemas import (
    AnalysisResponse,
    ExtraSkill,
    ModelInfo,
    RequirementMatch,
    ResumeStats,
    ScoreBreakdown,
    ScoreWeights,
    SectionScore,
    SkillItem,
    Suggestion,
)
from app.services.baseline import tfidf_cosine
from app.services.chunker import (
    Bullet,
    Chunk,
    Requirement,
    chunk_resume,
    clean_jd,
    extract_bullets,
    split_jd_requirements,
    top_requirements,
)
from app.services.embedder import EmbedderProtocol, EmbeddingCache, cosine_matrix
from app.services.pdf_parser import parse_pdf
from app.services.scorer import (
    CombinedScore,
    SkillPriorityWeights,
    Weights,
    best_match_mean,
    combine,
    rescale,
    skill_coverage,
    verdict_for,
)
from app.services.section_splitter import SECTION_NAMES, Section, split_sections
from app.services.skill_extractor import SkillExtractor
from app.services.suggestions import SuggestionContext, VerbLists, generate_suggestions, metrics_pct
from app.services.text_cleaner import clean_text, word_count

logger = logging.getLogger("resumelens.analyzer")

TAG_RANK = {"required": 0, "unspecified": 1, "preferred": 2}
CATEGORY_ORDER = [
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


@dataclass
class ResumeDoc:
    """Everything derived from the resume that later steps need."""

    pages: int
    structured_text: str
    embed_text: str
    sections: list[Section]
    chunks: list[Chunk]
    bullets: list[Bullet]
    skills: list[str]


@dataclass
class JDDoc:
    text: str
    requirements: list[Requirement]
    skills: dict[str, str]  # canonical name -> strongest tag


@dataclass
class Signals:
    """Raw and rescaled signals for one resume/JD pair."""

    coverage: float | None
    semantic_raw: float
    semantic: float
    keyword_raw: float
    keyword: float
    similarity: np.ndarray  # requirements x chunks


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


class ResumeAnalyzer:
    def __init__(
        self,
        settings: Settings,
        skill_extractor: SkillExtractor,
        embedder: EmbedderProtocol,
        verbs: VerbLists,
        spacy_model_name: str,
    ) -> None:
        self.settings = settings
        self.skills = skill_extractor
        self.embedder = embedder
        self.verbs = verbs
        self.spacy_model_name = spacy_model_name

    # ------------------------------------------------------------------ helpers
    @property
    def weights(self) -> Weights:
        s = self.settings
        return Weights(s.weight_skill, s.weight_semantic, s.weight_keyword)

    @property
    def priority_weights(self) -> SkillPriorityWeights:
        s = self.settings
        return SkillPriorityWeights(s.skill_weight_required, s.skill_weight_unspecified, s.skill_weight_preferred)

    def validate_jd(self, jd_text: str) -> str:
        text = (jd_text or "").strip()
        n = len(text)
        if n < self.settings.min_jd_chars:
            raise InvalidJobDescriptionError(
                f"Job description is too short ({n} characters); at least {self.settings.min_jd_chars} are required."
            )
        if n > self.settings.max_jd_chars:
            raise InvalidJobDescriptionError(
                f"Job description is too long ({n} characters); the maximum is {self.settings.max_jd_chars}."
            )
        return text

    # ------------------------------------------------------------- preparation
    def prepare_resume_text(self, text: str, pages: int) -> ResumeDoc:
        cleaned = clean_text(text)
        sections = split_sections(cleaned.for_embedding)
        if not sections:
            sections = [Section(section="other", text=cleaned.for_embedding, heading=None)]
        chunks = chunk_resume(sections, self.settings.chunk_min_words, self.settings.chunk_max_words)
        if not chunks:
            chunks = [Chunk(text=cleaned.for_embedding[:2000], section="other")]
        return ResumeDoc(
            pages=pages,
            structured_text=cleaned.structured,
            embed_text=cleaned.for_embedding,
            sections=sections,
            chunks=chunks,
            bullets=extract_bullets(sections),
            skills=self.skills.extract_names(cleaned.for_embedding),
        )

    def prepare_resume_pdf(self, pdf_bytes: bytes) -> ResumeDoc:
        parsed = parse_pdf(pdf_bytes, max_bytes=self.settings.max_upload_bytes, max_pages=self.settings.max_pdf_pages)
        return self.prepare_resume_text(parsed.text, parsed.pages)

    def prepare_jd(self, jd_text: str) -> JDDoc:
        text = clean_jd(jd_text)
        requirements = split_jd_requirements(text, self.settings.max_jd_requirements)
        skills: dict[str, str] = {}
        for req in requirements:
            for name in self.skills.extract_names(req.text):
                current = skills.get(name)
                if current is None or TAG_RANK[req.tag] < TAG_RANK[current]:
                    skills[name] = req.tag
        return JDDoc(text=text, requirements=requirements, skills=skills)

    # ------------------------------------------------------------------ signals
    def compute_signals(self, resume: ResumeDoc, jd: JDDoc, cache: EmbeddingCache | None = None) -> Signals:
        cache = cache or EmbeddingCache(self.embedder)
        s = self.settings
        req_texts = [r.text for r in jd.requirements]
        chunk_texts = [c.text for c in resume.chunks]
        cache.encode(req_texts + chunk_texts)  # one batched model call
        similarity = cosine_matrix(cache.encode(req_texts), cache.encode(chunk_texts))
        semantic_raw = best_match_mean(similarity)
        keyword_raw = tfidf_cosine(resume.embed_text, jd.text)
        coverage = skill_coverage(jd.skills, set(resume.skills), self.priority_weights)
        return Signals(
            coverage=coverage,
            semantic_raw=semantic_raw,
            semantic=rescale(semantic_raw, s.semantic_floor, s.semantic_ceiling),
            keyword_raw=keyword_raw,
            keyword=rescale(keyword_raw, s.keyword_floor, s.keyword_ceiling),
            similarity=similarity,
        )

    def combine_signals(self, signals: Signals, weights: Weights | None = None) -> CombinedScore:
        return combine(signals.coverage, signals.semantic, signals.keyword, weights or self.weights)

    # ---------------------------------------------------------------- outputs
    def _skill_lists(self, resume: ResumeDoc, jd: JDDoc) -> tuple[list[SkillItem], list[SkillItem], list[ExtraSkill]]:
        resume_set = set(resume.skills)

        def sort_key(item: SkillItem) -> tuple[int, int, str]:
            return (TAG_RANK[item.in_jd_as], CATEGORY_ORDER.index(item.category), item.name.lower())

        matched, missing = [], []
        for name, tag in jd.skills.items():
            item = SkillItem(name=name, category=self.skills.category_of(name), in_jd_as=tag)
            (matched if name in resume_set else missing).append(item)
        extra = [ExtraSkill(name=n, category=self.skills.category_of(n)) for n in resume.skills if n not in jd.skills][
            : self.settings.max_extra_skills
        ]
        return sorted(matched, key=sort_key), sorted(missing, key=sort_key), extra

    def _section_scores(self, resume: ResumeDoc, similarity: np.ndarray) -> list[SectionScore]:
        s = self.settings
        words: dict[str, int] = {}
        for sec in resume.sections:
            words[sec.section] = words.get(sec.section, 0) + word_count(sec.text)
        out: list[SectionScore] = []
        for name in SECTION_NAMES:
            cols = [i for i, c in enumerate(resume.chunks) if c.section == name]
            if not cols or similarity.size == 0:
                continue
            raw = best_match_mean(similarity[:, cols])
            out.append(
                SectionScore(
                    section=name,
                    similarity=round(raw, 3),
                    score=round(rescale(raw, s.semantic_floor, s.semantic_ceiling), 1),
                    word_count=words.get(name, 0),
                )
            )
        return out

    def _requirement_matches(self, resume: ResumeDoc, jd: JDDoc, similarity: np.ndarray) -> list[RequirementMatch]:
        position = {id(r): i for i, r in enumerate(jd.requirements)}
        matches: list[RequirementMatch] = []
        for req in top_requirements(jd.requirements, self.settings.top_requirement_matches):
            row = similarity[position[id(req)]] if similarity.size else np.zeros(0)
            if row.size == 0:
                matches.append(
                    RequirementMatch(
                        requirement=req.text,
                        requirement_type=req.tag,
                        best_chunk=None,
                        best_chunk_section=None,
                        similarity=0.0,
                    )
                )
                continue
            j = int(np.argmax(row))
            matches.append(
                RequirementMatch(
                    requirement=req.text,
                    requirement_type=req.tag,
                    best_chunk=resume.chunks[j].text,
                    best_chunk_section=resume.chunks[j].section,
                    similarity=round(float(row[j]), 3),
                )
            )
        return matches

    def _weakest_requirement(self, jd: JDDoc, similarity: np.ndarray) -> str | None:
        if similarity.size == 0:
            return None
        best = similarity.max(axis=1)
        return jd.requirements[int(np.argmin(best))].text

    # -------------------------------------------------------------------- main
    def analyze(self, pdf_bytes: bytes, jd_text: str) -> AnalysisResponse:
        start = time.perf_counter()
        jd_clean = self.validate_jd(jd_text)
        resume = self.prepare_resume_pdf(pdf_bytes)
        t_resume = time.perf_counter()
        jd = self.prepare_jd(jd_clean)
        t_jd = time.perf_counter()
        signals = self.compute_signals(resume, jd)
        combined = self.combine_signals(signals)
        t_score = time.perf_counter()

        matched, missing, extra = self._skill_lists(resume, jd)
        stats = ResumeStats(
            pages=resume.pages,
            word_count=word_count(resume.structured_text),
            bullet_count=len(resume.bullets),
            bullets_with_numbers_pct=metrics_pct(resume.bullets),
        )
        suggestions = generate_suggestions(
            SuggestionContext(
                missing_required=[m.name for m in missing if m.in_jd_as == "required"],
                missing_preferred=[m.name for m in missing if m.in_jd_as == "preferred"],
                jd_has_skills=bool(jd.skills),
                sections_present={s.section for s in resume.sections},
                bullets=resume.bullets,
                word_count=stats.word_count,
                pages=stats.pages,
                semantic_score=signals.semantic,
                keyword_score=signals.keyword,
                weakest_requirement=self._weakest_requirement(jd, signals.similarity),
                verbs=self.verbs,
            )
        )

        response = AnalysisResponse(
            analysis_id=uuid.uuid4().hex,
            created_at=datetime.now(UTC),
            overall_score=combined.overall,
            verdict=verdict_for(combined.overall),
            score_breakdown=ScoreBreakdown(
                skill_coverage=combined.skill_coverage,
                semantic_similarity=combined.semantic_similarity,
                keyword_overlap=combined.keyword_overlap,
                weights=ScoreWeights(
                    skill_coverage=combined.weights.skill,
                    semantic_similarity=combined.weights.semantic,
                    keyword_overlap=combined.weights.keyword,
                ),
                raw_semantic_cosine=round(signals.semantic_raw, 4),
                raw_keyword_cosine=round(signals.keyword_raw, 4),
                skill_weight_redistributed=combined.skill_weight_redistributed,
            ),
            matched_skills=matched,
            missing_skills=missing,
            extra_skills=extra,
            section_scores=self._section_scores(resume, signals.similarity),
            requirement_matches=self._requirement_matches(resume, jd, signals.similarity),
            suggestions=[Suggestion(**s) for s in suggestions],
            resume_stats=stats,
            model_info=ModelInfo(
                embedding_model=self.settings.embedding_model,
                spacy_model=self.spacy_model_name,
                version=self.settings.app_version,
            ),
            stored=False,
            redacted=False,
        )
        logger.info(
            "analysis_complete",
            extra={
                "fields": {
                    "score": combined.overall,
                    "chunks": len(resume.chunks),
                    "requirements": len(jd.requirements),
                    "jd_skills": len(jd.skills),
                    "resume_ms": round((t_resume - start) * 1000, 1),
                    "jd_ms": round((t_jd - t_resume) * 1000, 1),
                    "score_ms": round((t_score - t_jd) * 1000, 1),
                    "total_ms": round((time.perf_counter() - start) * 1000, 1),
                }
            },
        )
        return response


def redact_for_storage(response: AnalysisResponse) -> AnalysisResponse:
    """Copy of the response that is safe to persist: no resume excerpts."""
    redacted = response.model_copy(deep=True)
    for match in redacted.requirement_matches:
        match.best_chunk = None
    redacted.stored = True
    redacted.redacted = True
    return redacted
