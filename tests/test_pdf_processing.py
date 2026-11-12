"""PDF validation, detection, text extraction, and OCR behavior."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from src.models import PDFKind
from src.pdf_processing.errors import (
    PDFCorruptedError,
    PDFEmptyError,
    PDFPasswordError,
    PDFValidationError,
    OCRUnavailableError,
)
from src.pdf_processing.ocr_processor import OCRProcessor
from src.pdf_processing.pdf_detector import (
    detect_pdf_type,
    open_pdf,
    validate_pdf_file,
)
from src.pdf_processing.text_extractor import extract_text_pages


def test_validate_pdf_accepts_valid_file(text_statement_path: Path) -> None:
    assert validate_pdf_file(text_statement_path) == text_statement_path


def test_validate_pdf_rejects_non_pdf(non_pdf_path: Path) -> None:
    with pytest.raises(PDFValidationError):
        validate_pdf_file(non_pdf_path)


def test_validate_pdf_rejects_blank_file(blank_file_path: Path) -> None:
    with pytest.raises(PDFValidationError):
        validate_pdf_file(blank_file_path)


def test_validate_pdf_rejects_oversized_file(
    text_statement_path: Path, tmp_path: Path
) -> None:
    with pytest.raises(PDFValidationError):
        validate_pdf_file(text_statement_path, max_bytes=text_statement_path.stat().st_size - 1)


def test_validate_pdf_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(PDFValidationError):
        validate_pdf_file(tmp_path / "missing.pdf")


def test_detect_text_pdf(text_statement_path: Path) -> None:
    info = detect_pdf_type(text_statement_path)

    assert info.kind == PDFKind.TEXT
    assert info.page_count == 1
    assert info.text_page_numbers == [1]
    assert info.image_page_numbers == []
    assert not info.encrypted


def test_detect_scanned_pdf(scanned_pdf_path: Path) -> None:
    info = detect_pdf_type(scanned_pdf_path)

    assert info.kind == PDFKind.SCANNED
    assert info.page_count == 1
    assert info.image_page_numbers == [1]
    assert info.warnings


def test_detect_mixed_pdf(mixed_pdf_path: Path) -> None:
    info = detect_pdf_type(mixed_pdf_path)

    assert info.kind == PDFKind.MIXED
    assert info.page_count == 2
    assert info.text_page_numbers == [1]
    assert info.image_page_numbers == [2]


def test_detect_empty_pdf(empty_pdf_path: Path) -> None:
    info = detect_pdf_type(empty_pdf_path)

    assert info.kind == PDFKind.EMPTY
    assert info.warnings


def test_corrupt_pdf_is_rejected(corrupt_pdf_path: Path) -> None:
    with pytest.raises((PDFCorruptedError, PDFEmptyError)):
        detect_pdf_type(corrupt_pdf_path)


def test_password_protected_pdf_requires_password(password_statement_path: Path) -> None:
    with pytest.raises(PDFPasswordError):
        detect_pdf_type(password_statement_path)

    with pytest.raises(PDFPasswordError):
        detect_pdf_type(password_statement_path, password="wrong")

    info = detect_pdf_type(password_statement_path, password="secret")
    assert info.kind == PDFKind.TEXT
    assert info.encrypted


def test_open_pdf_returns_document(text_statement_path: Path) -> None:
    document = open_pdf(text_statement_path)
    try:
        assert document.page_count == 1
    finally:
        document.close()


def test_extract_text_pages_keeps_statement_rows(text_statement_path: Path) -> None:
    pages = extract_text_pages(text_statement_path)

    assert len(pages) == 1
    assert "HDFC BANK LIMITED" in pages[0]
    assert "SALARY CREDIT APRIL ACME CORP" in pages[0]
    assert "INTEREST CREDIT SAVINGS" in pages[0]


def test_extract_text_pages_supports_password(password_statement_path: Path) -> None:
    pages = extract_text_pages(password_statement_path, password="secret")

    assert "HDFC BANK LIMITED" in pages[0]


def test_ocr_unavailable_error_is_actionable(tmp_path: Path) -> None:
    processor = OCRProcessor(tesseract_cmd=str(tmp_path / "missing-tesseract.exe"))

    assert not processor.available
    with pytest.raises(OCRUnavailableError):
        processor.ocr_page(tmp_path / "missing.pdf", 0)


def test_ocr_text_cleanup() -> None:
    cleaned = OCRProcessor._clean_ocr_text("  first   line  \n\n second\tline \n")

    assert cleaned == "first line\nsecond line"


def test_ocr_image_preprocessing_returns_grayscale_image() -> None:
    source = Image.new("RGB", (80, 40), "white")

    processed = OCRProcessor._preprocess_image(source)

    assert processed.size == source.size
    assert processed.mode in {"L", "1"}
