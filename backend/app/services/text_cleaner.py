"""Text normalisation for resumes and job descriptions.

Produces three views of the same document:

* ``raw``: the extractor output, untouched.
* ``structured``: unicode-normalised, de-hyphenated, whitespace-collapsed, bullets
  unified to ``BULLET``, with line structure preserved (needed for section detection).
* ``for_embedding``: ``structured`` with emails, phone numbers and URLs removed, so
  personal contact details never reach the embedding model or the stored results.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

BULLET = "\u2022"  # the single canonical bullet marker ("•")

# Glyphs used as bullets by common resume templates, including private-use glyphs that
# Word/Symbol fonts emit (U+F0B7 etc.). "-" and "*" count only at the start of a line.
_BULLET_GLYPHS = (
    "\u2022\u25aa\u25cf\u25e6\u2023\u2219\u25cb\u25a0\u25a1\u27a2\u27a4\u25ba\u25b6"
    "\u2713\u2714\u00b7\u2043\u2013\u2014\uf0b7\uf0a7\uf076\uf0d8\uf0fc\u2756\u29bf"
)
_BULLET_LINE_RE = re.compile(r"^\s*(?:[" + re.escape(_BULLET_GLYPHS) + r"]|[-*](?=\s))\s*")
_CID_RE = re.compile(r"\(cid:\d+\)")
_HYPHEN_BREAK_RE = re.compile(r"([a-z])-\n\s*([a-z])")
_INLINE_WS_RE = re.compile(r"[ \t\u00a0\u2000-\u200b\u202f\u205f\u3000]+")
_MANY_NEWLINES_RE = re.compile(r"\n{3,}")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_PROFILE_URL_RE = re.compile(
    r"\b(?:linkedin|github|gitlab|behance|dribbble|medium|leetcode|kaggle|stackoverflow|twitter|x)\.com/\S*",
    re.IGNORECASE,
)
# Runs of digit groups joined by short separators: "+91 98765 43210", "(415) 555-0134".
_PHONE_CANDIDATE_RE = re.compile(r"(?<![\w+])\+?\(?\d[\d()]*(?:[ .\-]{1,3}\(?\d[\d()]*)+")
_DIGIT_GROUP_RE = re.compile(r"\d+")
_YEARISH_RE = re.compile(r"(?:19|20)\d{2}")


@dataclass(frozen=True)
class CleanedText:
    raw: str
    structured: str
    for_embedding: str


def _replace_phone(match: re.Match[str]) -> str:
    """Strip the leading 10-15 digits of a candidate run if they form a phone number.

    Digit groups are consumed left to right; once 10 digits are collected, a following
    year-like group (e.g. the "2019" in "...43210 2019 - 2021") ends the number. Runs that
    start with a year and have no "+" (date ranges) are left alone.
    """
    text = match.group(0)
    groups = list(_DIGIT_GROUP_RE.finditer(text))
    if not text.startswith("+") and _YEARISH_RE.fullmatch(groups[0].group()):
        return text
    total, end = 0, 0
    for group in groups:
        digits = len(group.group())
        if total >= 10 and (total + digits > 15 or _YEARISH_RE.fullmatch(group.group())):
            break
        total += digits
        end = group.end()
        if total > 15:
            return text
    if 10 <= total <= 15:
        return " " + text[end:].lstrip(" .-)")
    return text


def strip_pii(text: str) -> str:
    """Remove emails, URLs/profile links and phone numbers."""
    text = _EMAIL_RE.sub(" ", text)
    text = _URL_RE.sub(" ", text)
    text = _PROFILE_URL_RE.sub(" ", text)
    text = _PHONE_CANDIDATE_RE.sub(_replace_phone, text)
    return text


def normalize_bullets(text: str) -> str:
    """Replace any leading bullet glyph on each line with ``BULLET + ' '``.

    A glyph sitting alone on its own line (common in PDF extraction) is attached to the
    following line.
    """
    out: list[str] = []
    pending_bullet = False
    for line in text.split("\n"):
        if _BULLET_LINE_RE.match(line):
            rest = _BULLET_LINE_RE.sub("", line, count=1).strip()
            if rest:
                out.append(f"{BULLET} {rest}")
                pending_bullet = False
            else:
                pending_bullet = True
            continue
        if pending_bullet and line.strip():
            out.append(f"{BULLET} {line.strip()}")
            pending_bullet = False
            continue
        out.append(line)
    return "\n".join(out)


def _collapse_whitespace(text: str) -> str:
    lines = [_INLINE_WS_RE.sub(" ", line).strip() for line in text.split("\n")]
    return _MANY_NEWLINES_RE.sub("\n\n", "\n".join(lines)).strip()


def _tidy_lines(text: str) -> str:
    text = _collapse_whitespace(text)
    # Drop lines that are only separators such as "-----" or "|||" (bullets are already
    # normalised by the time this runs, so "•" lines never reach here empty).
    lines = [line for line in text.split("\n") if line == "" or not re.fullmatch(r"[\W_]+", line)]
    return _MANY_NEWLINES_RE.sub("\n\n", "\n".join(lines)).strip()


def normalize_text(text: str) -> str:
    """Normalise unicode, fix hyphenated line breaks, unify bullets, collapse whitespace."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n\n")
    text = _CONTROL_RE.sub(" ", text)
    text = _CID_RE.sub(" ", text)
    text = _HYPHEN_BREAK_RE.sub(r"\1\2", text)
    text = _collapse_whitespace(text)
    text = normalize_bullets(text)
    return _tidy_lines(text)


def clean_text(text: str) -> CleanedText:
    structured = normalize_text(text)
    for_embedding = _tidy_lines(strip_pii(structured))
    return CleanedText(raw=text, structured=structured, for_embedding=for_embedding)


# ---------------------------------------------------------------------------
# Tech-term normalisation shared by the skill matcher and the TF-IDF baseline.
# Symbols in names like C++, C#, .NET, Node.js and CI/CD tokenize unpredictably, so
# both the text and the skill aliases are rewritten to stable placeholder words.
# ---------------------------------------------------------------------------
_TECH_REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?<![\w+])c\+\+(?![\w+])", re.IGNORECASE), " cplusplus "),
    (re.compile(r"(?<![\w#])c#(?![\w#])", re.IGNORECASE), " csharp "),
    (re.compile(r"(?<![\w#])f#(?![\w#])", re.IGNORECASE), " fsharp "),
    (re.compile(r"\bci\s*/\s*cd\b", re.IGNORECASE), " cicd "),
    (re.compile(r"\.net\b", re.IGNORECASE), " dotnet "),
    (re.compile(r"(?<=[A-Za-z0-9])\.js\b", re.IGNORECASE), "js"),
    (re.compile(r"\bpython\s?3(?:\.\d+)?\b", re.IGNORECASE), "python"),
    (re.compile(r"\s*/\s*"), " / "),
]


def normalize_tech_terms(text: str) -> str:
    """Rewrite symbol-heavy technology names into tokenizer-friendly placeholders.

    Case is preserved for ordinary words so case-sensitive matching (e.g. "Go") still works.
    """
    for pattern, replacement in _TECH_REPLACEMENTS:
        text = pattern.sub(replacement, text)
    return text


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w[\w'+#.-]*\b", text))
