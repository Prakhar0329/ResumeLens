"""Deterministic suggestion rules (no LLM).

Each rule inspects the analysis context and may emit one suggestion. Messages never
quote resume text; they refer only to skills, counts and generic phrases from the verb
lists, so stored suggestions contain no personal content.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.services.chunker import Bullet

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

MIN_WORDS = 250
MAX_WORDS = 1100
MAX_PAGES = 2
METRICS_LOW_PCT = 30.0
STRONG_VERB_LOW_PCT = 40.0
LONG_BULLET_WORDS = 40
LOW_SEMANTIC = 40.0
LOW_KEYWORD = 25.0
MAX_INDIVIDUAL_MISSING = 5

_YEAR_RE = re.compile(r"^(?:19[5-9]\d|20[0-4]\d)$")
_NUMBER_TOKEN_RE = re.compile(r"[$€£₹]?\d[\d,.]*\+?%?[kKmMbBxX]?")


@dataclass(frozen=True)
class VerbLists:
    weak: list[str]
    strong: list[str]

    @classmethod
    def from_files(cls, weak_path: Path, strong_path: Path) -> VerbLists:
        weak = json.loads(weak_path.read_text(encoding="utf-8"))["verbs"]
        strong = json.loads(strong_path.read_text(encoding="utf-8"))["verbs"]
        # Longest phrases first so "was responsible for" wins over "responsible for".
        return cls(weak=sorted({w.lower() for w in weak}, key=len, reverse=True), strong=strong)


@dataclass
class SuggestionContext:
    missing_required: list[str]
    missing_preferred: list[str]
    jd_has_skills: bool
    sections_present: set[str]
    bullets: list[Bullet]
    word_count: int
    pages: int
    semantic_score: float
    keyword_score: float
    weakest_requirement: str | None
    verbs: VerbLists
    out: list[dict] = field(default_factory=list)


def has_metric(text: str) -> bool:
    """True if the text contains a number that is not just a year (e.g. 30%, $2M, 5x, 1,200)."""
    for token in _NUMBER_TOKEN_RE.findall(text):
        if not _YEAR_RE.match(token.rstrip(".,")):
            return True
    return False


def starts_with_phrase(text: str, phrases: list[str]) -> str | None:
    lowered = text.lower().lstrip("-–—•*· ")
    for phrase in phrases:
        if lowered.startswith(phrase) and (len(lowered) == len(phrase) or not lowered[len(phrase)].isalnum()):
            return phrase
    return None


def metrics_pct(bullets: list[Bullet]) -> float:
    if not bullets:
        return 0.0
    return round(100.0 * sum(has_metric(b.text) for b in bullets) / len(bullets), 1)


_PREFERRED_EXAMPLES = ("Built", "Designed", "Automated", "Optimized", "Led")


def _example_strong_verbs(verbs: VerbLists) -> list[str]:
    available = {v.lower() for v in verbs.strong}
    picks = [v for v in _PREFERRED_EXAMPLES if v.lower() in available]
    return picks or verbs.strong[:5]


def _add(ctx: SuggestionContext, type_: str, priority: str, message: str) -> None:
    ctx.out.append({"type": type_, "priority": priority, "message": message})


def _rule_missing_required(ctx: SuggestionContext) -> None:
    for skill in ctx.missing_required[:MAX_INDIVIDUAL_MISSING]:
        _add(
            ctx,
            "missing_required_skill",
            "high",
            f"The job lists {skill} as required, but it was not found on your resume. If you have it, "
            f"add it to your Skills section and show it in an experience or project bullet.",
        )
    remaining = ctx.missing_required[MAX_INDIVIDUAL_MISSING:]
    if remaining:
        _add(
            ctx,
            "missing_required_skills_summary",
            "high",
            f"{len(remaining)} more required skills are missing: {', '.join(remaining)}.",
        )


def _rule_missing_preferred(ctx: SuggestionContext) -> None:
    if ctx.missing_preferred:
        shown = ", ".join(ctx.missing_preferred[:8])
        more = f" and {len(ctx.missing_preferred) - 8} more" if len(ctx.missing_preferred) > 8 else ""
        _add(
            ctx,
            "missing_preferred_skills",
            "medium",
            f"Nice-to-have skills not found: {shown}{more}. Mention any you genuinely have.",
        )


def _rule_no_jd_skills(ctx: SuggestionContext) -> None:
    if not ctx.jd_has_skills:
        _add(
            ctx,
            "no_skills_in_jd",
            "low",
            "No known skills were detected in the job description, so skill coverage was excluded and its "
            "weight was redistributed to semantic similarity and keyword overlap.",
        )


def _rule_sections(ctx: SuggestionContext) -> None:
    present = ctx.sections_present
    if present <= {"summary", "other"}:
        _add(
            ctx,
            "no_sections_detected",
            "medium",
            "No standard section headings were detected. Use clear headings such as Experience, Projects, "
            "Skills and Education so recruiters and ATS parsers can navigate your resume.",
        )
    if "skills" not in present:
        _add(
            ctx,
            "skills_section_missing",
            "medium",
            "Add a dedicated Skills section listing your languages, frameworks and tools.",
        )
    if not ({"experience", "projects"} & present):
        _add(
            ctx,
            "experience_section_missing",
            "high",
            "No Experience or Projects section was found. Add one with bullets describing what you built "
            "and the results.",
        )


def _rule_length(ctx: SuggestionContext) -> None:
    if ctx.word_count < MIN_WORDS:
        _add(
            ctx,
            "resume_too_short",
            "medium",
            f"Your resume has about {ctx.word_count} words. Aim for at least {MIN_WORDS} with concrete detail "
            "about projects, responsibilities and outcomes.",
        )
    elif ctx.pages > MAX_PAGES or ctx.word_count > MAX_WORDS:
        _add(
            ctx,
            "resume_too_long",
            "medium",
            f"Your resume is {ctx.pages} page(s) and about {ctx.word_count} words. Keep it to 1 page for "
            "early-career roles (2 at most) by cutting older or less relevant bullets.",
        )


def _rule_bullets(ctx: SuggestionContext) -> None:
    work_bullets = [b for b in ctx.bullets if b.section in ("experience", "projects")]
    if not ctx.bullets:
        _add(
            ctx,
            "no_bullets",
            "medium",
            "No bullet points were detected. Describe experience and projects as short bullets, one "
            "achievement each.",
        )
        return
    if work_bullets:
        pct = metrics_pct(work_bullets)
        if pct == 0 and len(work_bullets) >= 3:
            _add(
                ctx,
                "no_quantified_metrics",
                "high",
                "None of your experience or project bullets contain numbers. Quantify impact (users, latency, "
                "accuracy, time saved), e.g. 'reduced API latency by [X%]'.",
            )
        elif pct < METRICS_LOW_PCT:
            _add(
                ctx,
                "few_quantified_metrics",
                "medium",
                f"Only {pct:g}% of your experience and project bullets contain a number. Aim for at least half.",
            )

    weak_hits: dict[str, int] = {}
    strong_count = 0
    strong_lower = [s.lower() for s in ctx.verbs.strong]
    long_count = 0
    for bullet in ctx.bullets:
        phrase = starts_with_phrase(bullet.text, ctx.verbs.weak)
        if phrase:
            weak_hits[phrase] = weak_hits.get(phrase, 0) + 1
        elif starts_with_phrase(bullet.text, strong_lower):
            strong_count += 1
        if len(bullet.text.split()) > LONG_BULLET_WORDS:
            long_count += 1

    if weak_hits:
        total = sum(weak_hits.values())
        examples = ", ".join(f"'{p}'" for p, _ in sorted(weak_hits.items(), key=lambda kv: -kv[1])[:3])
        _add(
            ctx,
            "weak_action_verbs",
            "medium",
            f"{total} bullet(s) start with weak phrasing such as {examples}. Lead with a specific action "
            f"verb such as {', '.join(_example_strong_verbs(ctx.verbs))}.",
        )
    if len(ctx.bullets) >= 4 and 100.0 * strong_count / len(ctx.bullets) < STRONG_VERB_LOW_PCT and not weak_hits:
        _add(
            ctx,
            "few_strong_verbs",
            "low",
            "Fewer than 40% of your bullets open with a strong action verb. Start each bullet with what you "
            "did: Built, Designed, Reduced, Automated, Led.",
        )
    if long_count >= 2:
        _add(
            ctx,
            "long_bullets",
            "low",
            f"{long_count} bullets are longer than {LONG_BULLET_WORDS} words. Split them or trim to one idea "
            "and one result each.",
        )


def _rule_alignment(ctx: SuggestionContext) -> None:
    if ctx.semantic_score < LOW_SEMANTIC:
        target = ""
        if ctx.weakest_requirement:
            req = ctx.weakest_requirement
            target = f" The least-covered requirement is: \"{req[:140]}{'…' if len(req) > 140 else ''}\"."
        _add(
            ctx,
            "low_semantic_alignment",
            "medium",
            "Your bullets do not closely match what the job description asks for. Where truthful, describe "
            "your work in terms of the role's responsibilities." + target,
        )
    if ctx.keyword_score < LOW_KEYWORD:
        _add(
            ctx,
            "low_keyword_overlap",
            "low",
            "Few of the job description's exact terms appear on your resume. Mirror its wording for skills "
            "and tools you actually have (ATS systems often match literally).",
        )


RULES: list[Callable[[SuggestionContext], None]] = [
    _rule_missing_required,
    _rule_missing_preferred,
    _rule_no_jd_skills,
    _rule_sections,
    _rule_length,
    _rule_bullets,
    _rule_alignment,
]


def generate_suggestions(ctx: SuggestionContext) -> list[dict]:
    ctx.out = []
    for rule in RULES:
        rule(ctx)
    return sorted(ctx.out, key=lambda s: PRIORITY_ORDER[s["priority"]])
