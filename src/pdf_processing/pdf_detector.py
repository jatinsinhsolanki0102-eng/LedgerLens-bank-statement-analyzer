"""Detect whether a PDF has a text layer, scanned pages, or both."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import fitz
from pypdf import PdfReader, PdfWriter

from config.settings import MIN_TEXT_CHARS_PER_PAGE, SUPPORTED_FILE_EXTENSIONS
from src.models import PDFInfo, PDFKind
from src.pdf_processing.errors import (
    PDFCorruptedError,
    PDFEmptyError,
    PDFPasswordError,
    PDFValidationError,
)
from src.utils.logging_config import get_logger

logger = get_logger("pdf_detector")


def validate_pdf_file(path: str | Path, max_bytes: int | None = None) -> Path:
    """Validate the basic file properties before opening it with a PDF library."""

    pdf_path = Path(path)
    if not pdf_path.exists() or not pdf_path.is_file():
        raise PDFValidationError("The selected file could not be found.")
    if pdf_path.suffix.lower() not in SUPPORTED_FILE_EXTENSIONS:
        raise PDFValidationError("Only PDF files are supported.")
    if pdf_path.stat().st_size == 0:
        raise PDFValidationError("The uploaded file is empty.")
    if max_bytes is not None and pdf_path.stat().st_size > max_bytes:
        size_mb = max_bytes / (1024 * 1024)
        raise PDFValidationError(f"The file exceeds the {size_mb:.0f} MB upload limit.")

    with pdf_path.open("rb") as file_handle:
        signature = file_handle.read(5)
    if signature != b"%PDF-":
        raise PDFValidationError("The file does not appear to be a valid PDF.")
    return pdf_path


def _decrypt_pdf_bytes(data: bytes, password: str) -> bytes:
    """Decrypt an encrypted PDF into a fresh in-memory PDF."""

    reader = PdfReader(BytesIO(data))
    if not reader.is_encrypted:
        return data
    if not reader.decrypt(password):
        raise PDFPasswordError("The PDF password is incorrect.")

    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def open_pdf(path: str | Path, password: str | None = None) -> fitz.Document:
    """Open and authenticate a PDF, raising a user-facing error on failure."""

    try:
        data = Path(path).read_bytes()
        document = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        logger.warning("PDF open failed: %s", type(exc).__name__)
        raise PDFCorruptedError(
            "The PDF is corrupted or uses an unsupported format."
        ) from exc

    was_encrypted = bool(document.needs_pass or document.is_encrypted)
    if document.needs_pass:
        if not password:
            document.close()
            raise PDFPasswordError("This PDF is password-protected. Enter its password.")
        document.close()
        try:
            data = _decrypt_pdf_bytes(data, password)
        except PDFPasswordError:
            raise
        except Exception as exc:
            logger.warning("PDF decryption fallback used: %s", type(exc).__name__)
            try:
                document = fitz.open(stream=data, filetype="pdf")
                if not document.authenticate(password):
                    raise PDFPasswordError("The PDF password is incorrect.")
            except PDFPasswordError:
                raise
            except Exception as fallback_exc:
                logger.warning("PDF open failed: %s", type(fallback_exc).__name__)
                raise PDFCorruptedError(
                    "The PDF is corrupted or uses an unsupported format."
                ) from fallback_exc
        else:
            try:
                document = fitz.open(stream=data, filetype="pdf")
            except Exception as exc:
                logger.warning("Decrypted PDF open failed: %s", type(exc).__name__)
                raise PDFCorruptedError(
                    "The PDF is corrupted or uses an unsupported format."
                ) from exc
        was_encrypted = True

    if document.page_count == 0:
        document.close()
        raise PDFEmptyError("The PDF contains no pages.")

    document._ledgerlens_encrypted = was_encrypted
    return document


def detect_pdf_type(path: str | Path, password: str | None = None) -> PDFInfo:
    """Inspect page text and images to classify the document layout."""

    pdf_path = validate_pdf_file(path)
    document = open_pdf(pdf_path, password=password)
    was_encrypted = bool(
        getattr(document, "_ledgerlens_encrypted", False)
        or document.needs_pass
        or document.is_encrypted
    )
    total_pages = document.page_count

    text_pages: list[int] = []
    image_pages: list[int] = []
    sparse_text_pages: list[int] = []
    try:
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            text = page.get_text("text").strip()
            has_images = bool(page.get_images(full=True))
            if len(text) >= MIN_TEXT_CHARS_PER_PAGE:
                text_pages.append(page_index + 1)
            elif text:
                sparse_text_pages.append(page_index + 1)
            elif has_images or page.get_drawings():
                image_pages.append(page_index + 1)
    finally:
        document.close()

    has_text = bool(text_pages or sparse_text_pages)
    if has_text and image_pages:
        kind = PDFKind.MIXED
    elif has_text:
        kind = PDFKind.TEXT
    elif image_pages:
        kind = PDFKind.SCANNED
    else:
        kind = PDFKind.EMPTY

    warnings: list[str] = []
    if kind == PDFKind.SCANNED:
        warnings.append("No text layer was found. OCR is required to read this PDF.")
    elif kind == PDFKind.MIXED:
        warnings.append("Some pages require OCR because they do not contain a text layer.")
    elif kind == PDFKind.EMPTY:
        warnings.append("No readable text or page images were found in the PDF.")

    logger.info("PDF detected as %s across %s pages", kind.value, total_pages)
    return PDFInfo(
        page_count=total_pages,
        kind=kind,
        encrypted=was_encrypted,
        text_page_numbers=sorted(text_pages + sparse_text_pages),
        image_page_numbers=sorted(image_pages),
        file_size_bytes=pdf_path.stat().st_size,
        warnings=warnings,
    )
