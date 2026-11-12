"""Domain-specific PDF and OCR exceptions."""

from __future__ import annotations


class StatementProcessingError(Exception):
    """Base class for errors that can be shown to the application user."""


class PDFValidationError(StatementProcessingError):
    """The uploaded file is not an acceptable PDF."""


class PDFCorruptedError(StatementProcessingError):
    """The PDF cannot be opened or parsed."""


class PDFPasswordError(StatementProcessingError):
    """The PDF requires a valid password."""


class PDFEmptyError(StatementProcessingError):
    """The PDF has no pages or no extractable content."""


class OCRUnavailableError(StatementProcessingError):
    """Tesseract OCR is not installed or could not be found."""


class OCRExtractionError(StatementProcessingError):
    """A scanned page could not be processed by OCR."""
