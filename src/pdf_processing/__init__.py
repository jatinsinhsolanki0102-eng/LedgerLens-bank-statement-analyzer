"""PDF detection, text extraction, and OCR."""

from src.pdf_processing.errors import (
    OCRExtractionError,
    OCRUnavailableError,
    PDFCorruptedError,
    PDFEmptyError,
    PDFPasswordError,
    PDFValidationError,
    StatementProcessingError,
)
from src.pdf_processing.ocr_processor import OCRProcessor
from src.pdf_processing.pdf_detector import detect_pdf_type, open_pdf, validate_pdf_file
from src.pdf_processing.text_extractor import (
    extract_table_rows,
    extract_text_pages,
    extract_text_with_pdfplumber,
)

__all__ = [
    "OCRProcessor",
    "OCRExtractionError",
    "OCRUnavailableError",
    "PDFCorruptedError",
    "PDFEmptyError",
    "PDFPasswordError",
    "PDFValidationError",
    "StatementProcessingError",
    "detect_pdf_type",
    "extract_table_rows",
    "extract_text_pages",
    "extract_text_with_pdfplumber",
    "open_pdf",
    "validate_pdf_file",
]
