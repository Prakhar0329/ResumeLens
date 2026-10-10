"""Resume section detection using a regex heading dictionary.

A line is treated as a heading when, after stripping decoration (colons, pipes,
numbering, trailing punctuation), the whole line matches one of the patterns below and
is short. Headings such as "Certifications" or "Achievements" are recognised but map to
the ``other`` bucket, since only six section names are scored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.text_cleaner import BULLET, word_count

SECTION_NAMES = ("summary", "experience", "projects", "skills", "education", "other")

_HEADING_PATTERNS: dict[str, list[str]] = {
    "summary": [
        r"(?:professional\s+|career\s+|executive\s+)?summary",
        r"(?:career\s+|professional\s+)?objective",
        r"(?:professional\s+|personal\s+)?profile",
        r"about(?:\s+me)?",
        r"overview",
        r"introduction",
    ],
    "experience": [
        r"(?:professional\s+|work\s+|relevant\s+|industry\s+|employment\s+|job\s+)?experience",
        r"work\s+history",
        r"employment(?:\s+history)?",
        r"career\s+history",
        r"internships?(?:\s+experience)?",
        r"experience\s+(?:and|&)\s+internships?",
        r"internships?\s+(?:and|&)\s+experience",
        r"professional\s+background",
    ],
    "projects": [
        r"(?:academic\s+|personal\s+|key\s+|selected\s+|side\s+|technical\s+|relevant\s+|major\s+)?projects?",
        r"project\s+(?:experience|work|highlights)",
        r"portfolio",
    ],
    "skills": [
        r"(?:technical\s+|core\s+|key\s+|professional\s+|relevant\s+|it\s+|computer\s+)?skills(?:\s+summary)?",
        r"skills?\s+(?:and|&)\s+(?:tools|technologies|expertise|abilities|interests)",
        r"(?:tools\s+(?:and|&)\s+)?technologies",
        r"tech(?:nical)?\s+stack",
        r"technical\s+(?:proficiencies|expertise|competencies)",
        r"(?:core\s+)?competencies",
        r"areas\s+of\s+expertise",
        r"expertise",
    ],
    "education": [
        r"education(?:al)?(?:\s+(?:background|qualifications?|details))?",
        r"academic(?:s|\s+(?:background|qualifications?|details|history))",
        r"(?:academic\s+)?qualifications?",
        r"(?:relevant\s+)?coursework",
    ],
    "other": [
        r"(?:licenses?\s+(?:and|&)\s+)?certifications?(?:\s+(?:and|&)\s+(?:licenses?|courses|trainings?))?",
        r"courses?",
        r"trainings?",
        r"achievements?(?:\s+(?:and|&)\s+awards?)?",
        r"awards?(?:\s+(?:and|&)\s+(?:honou?rs|achievements?))?",
        r"honou?rs(?:\s+(?:and|&)\s+awards?)?",
        r"accomplishments",
        r"publications?",
        r"research(?:\s+experience)?",
        r"extra[\s-]?curricular(?:\s+activities)?",
        r"activities",
        r"leadership(?:\s+(?:experience|roles?))?",
        r"positions?\s+of\s+responsibility",
        r"volunteer(?:ing)?(?:\s+(?:experience|work))?",
        r"languages",
        r"interests",
        r"hobbies(?:\s+(?:and|&)\s+interests)?",
        r"references",
        r"additional\s+information",
        r"personal\s+(?:details|information)",
    ],
}

_COMPILED: list[tuple[str, re.Pattern[str]]] = [
    (section, re.compile(rf"^(?:{pattern})$", re.IGNORECASE))
    for section, patterns in _HEADING_PATTERNS.items()
    for pattern in patterns
]

_DECORATION_RE = re.compile(r"^[\W\d_]*(?:[ivx]+[.)]\s*)?|[\W_]*$", re.IGNORECASE)
_SPACED_LETTERS_RE = re.compile(r"^(?:[A-Za-z] ){3,}[A-Za-z]$")
MAX_HEADING_WORDS = 6
MAX_HEADING_CHARS = 45
SHORT_PREAMBLE_WORDS = 80


@dataclass(frozen=True)
class Section:
    section: str
    text: str
    heading: str | None


def _normalise_heading(line: str) -> str:
    candidate = line.strip()
    if _SPACED_LETTERS_RE.match(candidate):  # "E X P E R I E N C E"
        candidate = candidate.replace(" ", "")
    candidate = _DECORATION_RE.sub("", candidate)
    candidate = candidate.replace("&", " & ")
    return re.sub(r"\s+", " ", candidate).strip()


def detect_heading(line: str) -> str | None:
    """Return the canonical section name if ``line`` is a section heading, else ``None``."""
    stripped = line.strip()
    if not stripped or stripped.startswith(BULLET):
        return None
    if len(stripped) > MAX_HEADING_CHARS + 10:
        return None
    candidate = _normalise_heading(stripped)
    if not candidate or len(candidate) > MAX_HEADING_CHARS or len(candidate.split()) > MAX_HEADING_WORDS:
        return None
    for section, pattern in _COMPILED:
        if pattern.match(candidate):
            return section
    return None


def split_sections(text: str) -> list[Section]:
    """Split resume text into ordered sections.

    Text before the first heading becomes ``summary`` when short (at most
    ``SHORT_PREAMBLE_WORDS`` words), otherwise ``other``. Empty sections are dropped.
    """
    sections: list[Section] = []
    current_name: str | None = None
    current_heading: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if not body:
            return
        if current_name is None:
            name = "summary" if word_count(body) <= SHORT_PREAMBLE_WORDS else "other"
        else:
            name = current_name
        sections.append(Section(section=name, text=body, heading=current_heading))

    for line in text.split("\n"):
        heading = detect_heading(line)
        if heading is not None:
            flush()
            buffer = []
            current_name, current_heading = heading, line.strip()
        else:
            buffer.append(line)
    flush()
    return sections


def section_names(sections: list[Section]) -> set[str]:
    return {s.section for s in sections}
