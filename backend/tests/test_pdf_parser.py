import pytest

from app.errors import (
    BadRequestError,
    FileTooLargeError,
    InvalidFileTypeError,
    TooManyPagesError,
    UnreadablePDFError,
)
from app.services import pdf_parser
from app.services.pdf_parser import parse_pdf, validate_pdf_bytes
from tests.conftest import SAMPLE_RESUME_LINES, make_encrypted_pdf, make_image_only_pdf, make_pdf

MB = 1024 * 1024


def test_parses_text_pdf(sample_pdf):
    parsed = parse_pdf(sample_pdf, max_bytes=5 * MB, max_pages=10)
    assert parsed.pages == 1
    assert parsed.extractor == "pdfplumber"
    assert "FastAPI" in parsed.text
    assert "EXPERIENCE" in parsed.text


def test_multi_page_count():
    parsed = parse_pdf(make_pdf(SAMPLE_RESUME_LINES, pages=3), max_bytes=5 * MB, max_pages=10)
    assert parsed.pages == 3


def test_rejects_non_pdf():
    with pytest.raises(InvalidFileTypeError) as exc:
        validate_pdf_bytes(b"This is just a text file pretending to be a resume.", 5 * MB)
    assert exc.value.status_code == 415


def test_rejects_png_bytes():
    with pytest.raises(InvalidFileTypeError):
        parse_pdf(b"\x89PNG\r\n\x1a\n" + b"0" * 200, max_bytes=5 * MB, max_pages=10)


def test_rejects_empty_file():
    with pytest.raises(BadRequestError) as exc:
        validate_pdf_bytes(b"", 5 * MB)
    assert exc.value.code == "empty_file"


def test_rejects_oversized_file():
    with pytest.raises(FileTooLargeError) as exc:
        validate_pdf_bytes(b"%PDF-1.4\n" + b"0" * (MB + 1), MB)
    assert exc.value.status_code == 413


def test_rejects_too_many_pages():
    with pytest.raises(TooManyPagesError) as exc:
        parse_pdf(make_pdf(SAMPLE_RESUME_LINES, pages=3), max_bytes=5 * MB, max_pages=2)
    assert "3 pages" in exc.value.message


def test_scanned_pdf_is_rejected_with_clear_message():
    with pytest.raises(UnreadablePDFError) as exc:
        parse_pdf(make_image_only_pdf(), max_bytes=5 * MB, max_pages=10)
    assert "OCR is not supported" in exc.value.message
    assert "scanned" in exc.value.message
    assert exc.value.status_code == 422


def test_blank_pdf_without_images_is_rejected():
    with pytest.raises(UnreadablePDFError) as exc:
        parse_pdf(make_pdf([]), max_bytes=5 * MB, max_pages=10)
    assert "scanned" not in exc.value.message


def test_corrupted_pdf_is_rejected():
    with pytest.raises(UnreadablePDFError):
        parse_pdf(b"%PDF-1.4\nthis is not really a pdf body\n%%EOF", max_bytes=5 * MB, max_pages=10)


def test_encrypted_pdf_is_rejected():
    with pytest.raises(UnreadablePDFError) as exc:
        parse_pdf(make_encrypted_pdf(SAMPLE_RESUME_LINES), max_bytes=5 * MB, max_pages=10)
    assert exc.value.code == "encrypted_pdf"


def test_falls_back_to_pymupdf(monkeypatch, sample_pdf):
    monkeypatch.setattr(pdf_parser, "_extract_pdfplumber", lambda data: "")
    parsed = parse_pdf(sample_pdf, max_bytes=5 * MB, max_pages=10)
    assert parsed.extractor == "pymupdf"
    assert "PostgreSQL" in parsed.text


def test_extractors_survive_garbage():
    assert pdf_parser._extract_pdfplumber(b"not a pdf") == ""
    assert pdf_parser._extract_pymupdf(b"not a pdf") == ""
    assert pdf_parser._has_images(b"not a pdf") is False
