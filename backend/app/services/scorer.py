"""Scoring: combine skill coverage, semantic similarity and keyword overlap.

    skill_coverage      = sum(w(tag) for JD skills found) / sum(w(tag) for all JD skills) * 100
                          with w(required)=2.0, w(unspecified)=1.0, w(preferred)=0.5
    semantic_similarity = rescale(mean_i max_j cos(req_i, chunk_j), floor=0.20, ceiling=0.75)
    keyword_overlap     = rescale(tfidf_cosine(resume, jd), floor=0.02, ceiling=0.40)
    overall_score       = 0.50*skill + 0.35*semantic + 0.15*keyword

``rescale`` maps [floor, ceiling] linearly onto [0, 100] and clips. Weights are
normalised to sum to 1. If the JD has no detectable skills, the skill weight is
redistributed to the other two signals in proportion to their weights.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

VERDICT_PARTIAL = 40.0
VERDICT_STRONG = 65.0
VERDICT_EXCELLENT = 85.0


@dataclass(frozen=True)
class Weights:
    skill: float
    semantic: float
    keyword: float

    def normalised(self) -> Weights:
        total = self.skill + self.semantic + self.keyword
        if total <= 0:
            raise ValueError("Weights must sum to a positive number")
        return Weights(self.skill / total, self.semantic / total, self.keyword / total)


@dataclass(frozen=True)
class SkillPriorityWeights:
    required: float = 2.0
    unspecified: float = 1.0
    preferred: float = 0.5

    def for_tag(self, tag: str) -> float:
        return {"required": self.required, "unspecified": self.unspecified, "preferred": self.preferred}[tag]


@dataclass(frozen=True)
class CombinedScore:
    overall: float
    skill_coverage: float
    semantic_similarity: float
    keyword_overlap: float
    weights: Weights  # effective weights actually applied
    skill_weight_redistributed: bool


def rescale(value: float, floor: float, ceiling: float) -> float:
    """Linearly map ``value`` from [floor, ceiling] to [0, 100], clipped."""
    if ceiling <= floor:
        raise ValueError("ceiling must be greater than floor")
    scaled = (value - floor) / (ceiling - floor) * 100.0
    return float(min(100.0, max(0.0, scaled)))


def verdict_for(score: float) -> str:
    if score >= VERDICT_EXCELLENT:
        return "Excellent match"
    if score >= VERDICT_STRONG:
        return "Strong match"
    if score >= VERDICT_PARTIAL:
        return "Partial match"
    return "Weak match"


def skill_coverage(
    jd_skills: dict[str, str],
    resume_skills: set[str],
    priority: SkillPriorityWeights = SkillPriorityWeights(),
) -> float | None:
    """Weighted share (0-100) of JD skills present on the resume; ``None`` if the JD has no skills.

    ``jd_skills`` maps canonical skill name to its tag ("required"/"preferred"/"unspecified").
    """
    if not jd_skills:
        return None
    total = sum(priority.for_tag(tag) for tag in jd_skills.values())
    if total <= 0:
        return None
    found = sum(priority.for_tag(tag) for name, tag in jd_skills.items() if name in resume_skills)
    return 100.0 * found / total


def best_match_mean(similarity: np.ndarray) -> float:
    """Mean over rows (JD requirements) of the max over columns (resume chunks)."""
    if similarity.size == 0:
        return 0.0
    return float(np.mean(np.max(similarity, axis=1)))


def combine(
    coverage: float | None,
    semantic: float,
    keyword: float,
    weights: Weights,
) -> CombinedScore:
    """Combine signals (each 0-100) into the overall score (0-100, one decimal)."""
    w = weights.normalised()
    redistributed = False
    if coverage is None:
        redistributed = True
        rest = w.semantic + w.keyword
        if rest > 0:
            w = Weights(0.0, w.semantic / rest, w.keyword / rest)
        else:  # all weight was on skills: fall back to an even split
            w = Weights(0.0, 0.5, 0.5)
        coverage_value = 0.0
    else:
        coverage_value = coverage
    overall = w.skill * coverage_value + w.semantic * semantic + w.keyword * keyword
    overall = round(float(min(100.0, max(0.0, overall))), 1)
    return CombinedScore(
        overall=overall,
        skill_coverage=round(coverage_value, 1),
        semantic_similarity=round(semantic, 1),
        keyword_overlap=round(keyword, 1),
        weights=Weights(round(w.skill, 4), round(w.semantic, 4), round(w.keyword, 4)),
        skill_weight_redistributed=redistributed,
    )
