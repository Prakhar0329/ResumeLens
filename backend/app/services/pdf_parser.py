"""PDF validation and text extraction.

Strategy: pdfplumber first (good reading order for single-column resumes); if it yields
fewer than ``FALLBACK_THRESHOLD_CHARS`` characters, retry with PyMuPDF and keep the
longer result. If neither produces usable text the PDF is treated as scanned/image-only
and rejected, because OCR is out of scope.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

import fitz  # PyMuPDF
import pdfplumber

from app.errors import (
    BadRequestError,
    FileTooLargeError,
    InvalidFileTypeError,
    TooManyPagesError,
    UnreadablePDFError,
)

logger = logging.getLogger("resumelens.pdf")

PDF_MAGIC = b"%PDF"
MAGIC_SEARCH_BYTES = 1024  # the PDF spec tolerates a little junk before the header
FALLBACK_THRESHOLD_CHARS = 100
MIN_TEXT_CHARS = 100


@dataclass(frozen=True)
class ParsedPDF:
    text: str
    pages: int
    extractor: str  # "pdfplumber" or "pymupdf"


def validate_pdf_bytes(data: bytes, max_bytes: int) -> None:
    """Cheap checks that do not require parsing: emptiness, size and magic bytes."""
    if not data:
        raise BadRequestError("The uploaded file is empty.", code="empty_file")
    if len(data) > max_bytes:
        mb = max_bytes / (1024 * 1024)
        raise FileTooLargeError(f"Resume must be at most {mb:g} MB.")
    if PDF_MAGIC not in data[:MAGIC_SEARCH_BYTES]:
        raise InvalidFileTypeError("Only PDF files are supported (missing %PDF header).")


def _count_pages(data: bytes) -> int:
    try:
        with fitz.open(stream=data, filetype="pdf") as doc:
            if doc.needs_pass:
                raise UnreadablePDFError("Password-protected PDFs are not supported.", code="encrypted_pdf")
            return doc.page_count
    except UnreadablePDFError:
        raise
    except Exception as exc:  # corrupted or not really a PDF
        raise UnreadablePDFError("The file could not be opened as a PDF; it may be corrupted.") from exc


def _extract_pdfplumber(data: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = [page.extract_text(x_tolerance=1.5, y_tolerance=3) or "" for page in pdf.pages]
        return "\n\n".join(pages)
    except Exception:
        logger.warning("pdfplumber_failed", exc_info=False)
        return ""


def _extract_pymupdf(data: bytes) -> str:
    try:
        with fitz.open(stream=data, filetype="pdf") as doc:
            return "\n\n".join(page.get_text("text", sort=True) for page in doc)
    except Exception:
        logger.warning("pymupdf_failed", exc_info=False)
        return ""


def _has_images(data: bytes) -> bool:
    try:
        with fitz.open(stream=data, filetype="pdf") as doc:
            return any(page.get_images(full=False) for page in doc)
    except Exception:
        return False


def parse_pdf(data: bytes, *, max_bytes: int, max_pages: int) -> ParsedPDF:
    """Validate a PDF upload and return its text.

    Raises:
        BadRequestError: empty upload.
        FileTooLargeError: larger than ``max_bytes``.
        InvalidFileTypeError: missing the ``%PDF`` magic bytes.
        TooManyPagesError: more than ``max_pages`` pages.
        UnreadablePDFError: corrupted, encrypted or image-only PDF.
    """
    validate_pdf_bytes(data, max_bytes)
    pages = _count_pages(data)
    if pages == 0:
        raise UnreadablePDFError("The PDF has no pages.")
    if pages > max_pages:
        raise TooManyPagesError(f"Resume has {pages} pages; the maximum is {max_pages}.")

    text = _extract_pdfplumber(data)
    extractor = "pdfplumber"
    if len(text.strip()) < FALLBACK_THRESHOLD_CHARS:
        alt = _extract_pymupdf(data)
        if len(alt.strip()) > len(text.strip()):
            text, extractor = alt, "pymupdf"

    if len(text.strip()) < MIN_TEXT_CHARS:
        detail = " The PDF appears to be scanned or image-only." if _has_images(data) else ""
        raise UnreadablePDFError(
            "No extractable text; OCR is not supported."
            + detail
            + " Export your resume as a text-based PDF from Word, Google Docs or LaTeX."
        )

    logger.info("pdf_parsed", extra={"fields": {"pages": pages, "chars": len(text), "extractor": extractor}})
    return ParsedPDF(text=text, pages=pages, extractor=extractor)
