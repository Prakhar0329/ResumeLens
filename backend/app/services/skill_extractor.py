"""Rule-based skill extraction with spaCy's PhraseMatcher.

Two matchers run over the same tokenized text:

* ``aliases`` use ``attr="LOWER"`` (case-insensitive), e.g. "postgres" -> PostgreSQL.
* ``strict_aliases`` use ``attr="ORTH"`` (case-sensitive) for ambiguous words that are
  only skills when capitalised, e.g. "Go", "R", "Spring", "Excel".

Symbol-heavy names (C++, C#, .NET, Node.js, CI/CD) are rewritten to placeholder words by
``normalize_tech_terms`` on BOTH the text and the patterns, so they always tokenize
the same way. Overlapping matches keep the longest span ("Spring Boot" beats "Spring").
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import spacy
from spacy.language import Language
from spacy.matcher import PhraseMatcher
from spacy.tokens import Span
from spacy.util import filter_spans

from app.services.text_cleaner import normalize_tech_terms

logger = logging.getLogger("resumelens.skills")

VALID_CATEGORIES = {
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
}


@dataclass(frozen=True)
class SkillDef:
    canonical: str
    category: str


@dataclass(frozen=True)
class ExtractedSkill:
    name: str
    category: str
    count: int


def load_skills(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    skills = data["skills"] if isinstance(data, dict) else data
    seen: set[str] = set()
    for entry in skills:
        canonical = entry["canonical"]
        if entry["category"] not in VALID_CATEGORIES:
            raise ValueError(f"Unknown category {entry['category']!r} for skill {canonical!r}")
        if canonical.lower() in seen:
            raise ValueError(f"Duplicate canonical skill {canonical!r}")
        seen.add(canonical.lower())
    return skills


def load_spacy(model_name: str) -> tuple[Language, str]:
    """Load the configured spaCy pipeline; fall back to a blank English tokenizer.

    Only the tokenizer is used for matching, so the blank fallback produces identical
    matches. The returned name reports which one is active.
    """
    try:
        return spacy.load(model_name), model_name
    except OSError:
        logger.warning(
            "spacy_model_missing",
            extra={"fields": {"model": model_name, "hint": f"python -m spacy download {model_name}"}},
        )
        return spacy.blank("en"), "blank:en"


class SkillExtractor:
    def __init__(self, nlp: Language, skills: list[dict]) -> None:
        self.nlp = nlp
        self.defs: dict[str, SkillDef] = {}
        self._lower = PhraseMatcher(nlp.vocab, attr="LOWER")
        self._strict = PhraseMatcher(nlp.vocab, attr="ORTH")
        for entry in skills:
            canonical = entry["canonical"]
            key = canonical  # match_id string
            self.defs[key] = SkillDef(canonical=canonical, category=entry["category"])
            lower_patterns = self._patterns(entry.get("aliases", []), lowercase=True)
            strict_patterns = self._patterns(entry.get("strict_aliases", []), lowercase=False)
            if lower_patterns:
                self._lower.add(key, lower_patterns)
            if strict_patterns:
                self._strict.add(key, strict_patterns)

    @classmethod
    def from_files(cls, skills_path: Path, spacy_model: str) -> tuple[SkillExtractor, str]:
        nlp, loaded_name = load_spacy(spacy_model)
        return cls(nlp, load_skills(skills_path)), loaded_name

    def _patterns(self, aliases: list[str], *, lowercase: bool) -> list:
        seen: set[str] = set()
        docs = []
        for alias in aliases:
            normalised = " ".join(normalize_tech_terms(alias.lower() if lowercase else alias).split())
            if normalised and normalised not in seen:
                seen.add(normalised)
                docs.append(self.nlp.make_doc(normalised))
        return docs

    @property
    def size(self) -> int:
        return len(self.defs)

    def category_of(self, name: str) -> str:
        return self.defs[name].category

    def extract(self, text: str) -> list[ExtractedSkill]:
        """Return de-duplicated canonical skills in order of first appearance."""
        if not text.strip():
            return []
        doc = self.nlp.make_doc(normalize_tech_terms(text))
        spans = []
        for matcher in (self._lower, self._strict):
            for match_id, start, end in matcher(doc):
                spans.append(Span(doc, start, end, label=match_id))
        spans = filter_spans(spans)  # longest non-overlapping spans win
        counts: dict[str, int] = {}
        order: list[str] = []
        for span in sorted(spans, key=lambda s: s.start):
            name = span.label_
            if name not in counts:
                order.append(name)
                counts[name] = 0
            counts[name] += 1
        return [ExtractedSkill(name=n, category=self.defs[n].category, count=counts[n]) for n in order]

    def extract_names(self, text: str) -> list[str]:
        return [s.name for s in self.extract(text)]
