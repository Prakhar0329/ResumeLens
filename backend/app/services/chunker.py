"""Chunking for resumes and requirement extraction for job descriptions.

Resume: each bullet (with its wrapped continuation lines) or paragraph sentence group
becomes a unit; units shorter than ``min_words`` are merged with their neighbours in the
same section and units longer than ``max_words`` are split on sentence boundaries.

JD: each bullet or sentence becomes a candidate requirement, tagged ``required``,
``preferred`` or ``unspecified`` from cue phrases in the sentence itself, falling back
to the JD sub-heading it sits under (e.g. "Nice to have"). Boilerplate blocks such as
"About us" or "Benefits" are skipped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.section_splitter import Section
from app.services.text_cleaner import BULLET, normalize_text, strip_pii, word_count

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+(?=[A-Z0-9(\"'])")
_TERMINAL_PUNCT = (".", "!", "?", ";", ":")
_CONTINUATION_START_RE = re.compile(r"^[a-z0-9(&,/+%$]")
_CONTINUATION_END_RE = re.compile(r"(?:,|&|\band|\bor|\bwith|\bto|\bof|\bfor|\bin|-|/)$", re.IGNORECASE)


@dataclass(frozen=True)
class Chunk:
    text: str
    section: str


@dataclass(frozen=True)
class Bullet:
    text: str
    section: str


@dataclass(frozen=True)
class Requirement:
    text: str
    tag: str  # "required" | "preferred" | "unspecified"
    index: int  # position in the JD, for stable ordering


def split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_SPLIT_RE.split(text.strip())
    return [p.strip() for p in parts if p and p.strip()]


def _is_bullet(line: str) -> bool:
    return line.startswith(BULLET + " ")


def _strip_bullet(line: str) -> str:
    return line[len(BULLET) + 1 :].strip() if _is_bullet(line) else line.strip()


def _is_continuation(prev: str, line: str) -> bool:
    """A wrapped line continues the previous one if it starts lowercase/with a joiner, or
    the previous line clearly ends mid-phrase ("..., and", "with", "-")."""
    if _CONTINUATION_START_RE.match(line):
        return True
    return not prev.endswith(_TERMINAL_PUNCT) and bool(_CONTINUATION_END_RE.search(prev))


def _section_units(section_text: str) -> list[tuple[str, bool]]:
    """Return (text, is_bullet) units for a section.

    Resumes are line-oriented, so each line starts a new unit unless it is a wrapped
    continuation of the previous line. Non-bullet units are then split into sentences.
    """
    raw_units: list[list] = []  # [text, is_bullet, can_continue]
    for raw_line in section_text.split("\n"):
        line = raw_line.strip()
        if not line:
            if raw_units:
                raw_units[-1][2] = False  # a blank line ends any wrapping
            continue
        if _is_bullet(line):
            raw_units.append([_strip_bullet(line), True, True])
            continue
        if raw_units and raw_units[-1][2] and _is_continuation(raw_units[-1][0], line):
            raw_units[-1][0] = f"{raw_units[-1][0]} {line}"
            continue
        raw_units.append([line, False, True])

    units: list[tuple[str, bool]] = []
    for text, is_bullet, _ in raw_units:
        if is_bullet:
            units.append((text, True))
        else:
            units.extend((sentence, False) for sentence in split_sentences(text))
    return [(t, b) for t, b in units if t]


_DATE_RANGE_RE = re.compile(
    r"(?:\b(?:19|20)\d{2}|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s*(?:19|20)?\d{0,2})"
    r"\s*(?:-|–|—|to)\s*(?:(?:19|20)\d{2}|present|current|now|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec))",
    re.IGNORECASE,
)


def looks_like_role_header(text: str) -> bool:
    """Job/project header lines such as "Engineer, Acme  Jun 2023 - Aug 2023"."""
    return bool(_DATE_RANGE_RE.search(text)) and word_count(text) <= 16


def extract_bullets(sections: list[Section]) -> list[Bullet]:
    """Bullets across the resume.

    If an experience/projects section contains no bullet glyphs (some PDFs lose them),
    its sentence-like lines of 6+ words that are not role/date headers count instead.
    """
    bullets: list[Bullet] = []
    for sec in sections:
        units = _section_units(sec.text)
        marked = [Bullet(t, sec.section) for t, is_b in units if is_b]
        if not marked and sec.section in ("experience", "projects"):
            marked = [
                Bullet(t, sec.section)
                for t, _ in units
                if word_count(t) >= 6 and t[:1].isupper() and not looks_like_role_header(t)
            ]
        bullets.extend(marked)
    return bullets


def _split_long(text: str, max_words: int) -> list[str]:
    if word_count(text) <= max_words:
        return [text]
    pieces: list[str] = []
    current: list[str] = []
    for sentence in split_sentences(text):
        words = sentence.split()
        # A single overlong sentence is cut into word windows.
        while len(words) > max_words:
            if current:
                pieces.append(" ".join(current))
                current = []
            pieces.append(" ".join(words[:max_words]))
            words = words[max_words:]
        if current and len(current) + len(words) > max_words:
            pieces.append(" ".join(current))
            current = []
        current.extend(words)
    if current:
        pieces.append(" ".join(current))
    return pieces


STANDALONE_UNIT_WORDS = 8
MIN_CHUNK_WORDS = 3


def chunk_resume(sections: list[Section], min_words: int = 15, max_words: int = 80) -> list[Chunk]:
    """Chunk each section into bullet/sentence-group chunks of roughly min..max words.

    A unit (bullet or sentence) of at least ``STANDALONE_UNIT_WORDS`` words is its own chunk,
    so the explainability view shows a real bullet. Shorter units are grouped until the
    group reaches ``min_words``; a group still too small when a standalone unit arrives is
    prefixed onto it, and a small tail at the end of a section joins the previous chunk.
    """
    chunks: list[Chunk] = []
    for sec in sections:
        merged: list[str] = []
        buffer = ""
        for text, _ in _section_units(sec.text):
            if word_count(text) >= STANDALONE_UNIT_WORDS:
                if buffer and word_count(buffer) >= MIN_CHUNK_WORDS + 1:
                    merged.append(buffer)
                    merged.append(text)
                elif buffer:
                    merged.append(f"{buffer} {text}")
                else:
                    merged.append(text)
                buffer = ""
                continue
            buffer = f"{buffer} {text}".strip() if buffer else text
            if word_count(buffer) >= min_words:
                merged.append(buffer)
                buffer = ""
        if buffer:
            tail_words = word_count(buffer)
            if merged and tail_words < MIN_CHUNK_WORDS and word_count(merged[-1]) + tail_words <= max_words:
                merged[-1] = f"{merged[-1]} {buffer}"
            else:
                merged.append(buffer)
        for text in merged:
            for piece in _split_long(text, max_words):
                if word_count(piece) >= 2:
                    chunks.append(Chunk(text=piece, section=sec.section))
    return chunks


# ---------------------------------------------------------------------------
# Job description requirements
# ---------------------------------------------------------------------------
_PREFERRED_CUES = re.compile(
    r"\b(?:nice[\s-]to[\s-]haves?|good[\s-]to[\s-]haves?|preferred|preferably|preference|bonus|"
    r"(?:is\s+|are\s+|would\s+be\s+|a\s+|big\s+|huge\s+)plus|pluses|desirable|desired|ideally|"
    r"advantageous|an\s+advantage|nice\s+if|not\s+required|optional|extra\s+credit)\b",
    re.IGNORECASE,
)
_REQUIRED_CUES = re.compile(
    r"\b(?:must(?:\s+have)?|required|requirements?|require[sd]?|mandatory|essential|minimum|"
    r"at\s+least|need\s+to\s+have|you\s+(?:will\s+)?need|necessary|non[\s-]negotiable|"
    r"\d+\+?\s*(?:years|yrs))\b",
    re.IGNORECASE,
)

_HEADING_CONTEXTS: list[tuple[str, re.Pattern[str]]] = [
    (
        "skip",
        re.compile(
            r"^(?:about\s+(?:us|the\s+company|the\s+team|company)|who\s+we\s+are|our\s+(?:story|mission|values|culture)|"
            r"benefits|perks(?:\s+(?:and|&)\s+benefits)?|what\s+we\s+offer|we\s+offer|compensation|salary|"
            r"equal\s+(?:opportunity|employment).*|eeo.*|how\s+to\s+apply|application\s+process|location|"
            r"why\s+(?:join\s+us|work\s+(?:with|for)\s+us).*)$",
            re.IGNORECASE,
        ),
    ),
    (
        "preferred",
        re.compile(
            r"^(?:preferred(?:\s+(?:qualifications|skills|experience|requirements))?|nice[\s-]to[\s-]haves?|"
            r"good[\s-]to[\s-]haves?|bonus(?:\s+points)?|pluses|desired(?:\s+(?:skills|qualifications))?|"
            r"additional\s+(?:qualifications|skills)|extra\s+credit|it'?s?\s+a\s+plus\s+if.*|ideally.*)$",
            re.IGNORECASE,
        ),
    ),
    (
        "required",
        re.compile(
            r"^(?:(?:minimum|basic|required|key|essential)\s+(?:qualifications|requirements|skills)|requirements|"
            r"qualifications|must[\s-]haves?|what\s+you(?:'ll|\s+will)?\s+(?:need|bring)|what\s+we(?:'re|\s+are)\s+looking\s+for|"
            r"who\s+you\s+are|you\s+(?:have|bring|are)|skills(?:\s+(?:and|&)\s+(?:experience|qualifications))?|"
            r"experience|skills\s+required|required\s+experience|your\s+(?:profile|skills|background)|ideal\s+candidate)$",
            re.IGNORECASE,
        ),
    ),
    (
        "unspecified",
        re.compile(
            r"^(?:responsibilities|key\s+responsibilities|duties|what\s+you(?:'ll|\s+will)\s+do|the\s+role|"
            r"about\s+the\s+(?:role|job|position)|role\s+overview|job\s+description|overview|your\s+(?:role|impact|mission)|"
            r"in\s+this\s+role.*|day[\s-]to[\s-]day)$",
            re.IGNORECASE,
        ),
    ),
]

MIN_REQUIREMENT_WORDS = 3
MAX_JD_HEADING_WORDS = 8


def _jd_heading_context(line: str) -> str | None:
    if _is_bullet(line):
        return None
    candidate = re.sub(r"^[\W\d_]+|[\W_]+$", "", line).strip()
    candidate = re.sub(r"\s+", " ", candidate)
    if not candidate or len(candidate.split()) > MAX_JD_HEADING_WORDS:
        return None
    for context, pattern in _HEADING_CONTEXTS:
        if pattern.match(candidate):
            return context
    return None


def tag_requirement(text: str, context: str = "unspecified") -> str:
    """Sentence cues win over the heading context; preferred cues are checked first
    because phrases like "X is a plus" are more specific than generic "required" words."""
    if _PREFERRED_CUES.search(text):
        return "preferred"
    if _REQUIRED_CUES.search(text):
        return "required"
    return context if context in ("required", "preferred") else "unspecified"


def clean_jd(text: str) -> str:
    return normalize_text(strip_pii(text))


def split_jd_requirements(jd_text: str, max_requirements: int = 60) -> list[Requirement]:
    """Split a JD into tagged requirement sentences (already PII-stripped, normalised text)."""
    requirements: list[Requirement] = []
    context = "unspecified"
    index = 0
    for raw_line in jd_text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        heading_ctx = _jd_heading_context(line)
        if heading_ctx is not None:
            context = heading_ctx
            continue
        if line.endswith(":") and len(line.split()) <= MAX_JD_HEADING_WORDS and not _is_bullet(line):
            # Unknown heading: reset to neutral, but let it influence via cue words.
            context = tag_requirement(line, "unspecified")
            continue
        if context == "skip":
            continue
        for sentence in split_sentences(_strip_bullet(line)):
            if word_count(sentence) < MIN_REQUIREMENT_WORDS:
                continue
            requirements.append(Requirement(text=sentence, tag=tag_requirement(sentence, context), index=index))
            index += 1

    if not requirements:
        # Unstructured JD: fall back to its sentences, or the whole text as one requirement.
        flat = " ".join(jd_text.split())
        sentences = [s for s in split_sentences(flat) if word_count(s) >= MIN_REQUIREMENT_WORDS] or [flat]
        requirements = [Requirement(text=s, tag=tag_requirement(s), index=i) for i, s in enumerate(sentences)]

    return requirements[:max_requirements]


_TAG_ORDER = {"required": 0, "unspecified": 1, "preferred": 2}


def top_requirements(requirements: list[Requirement], n: int) -> list[Requirement]:
    """Most important requirements first: required, then unspecified, then preferred."""
    return sorted(requirements, key=lambda r: (_TAG_ORDER[r.tag], r.index))[:n]
