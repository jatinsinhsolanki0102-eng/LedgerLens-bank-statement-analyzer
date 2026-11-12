"""End-to-end statement processing orchestration."""

from __future__ import annotations

from pathlib import Path

from config.settings import MIN_TEXT_CHARS_PER_PAGE
from src.classification.classification_engine import ClassificationEngine
from src.classification.ml_classifier import MLClassifier
from src.classification.rule_classifier import RuleClassifier
from src.extraction.account_extractor import AccountExtractor
from src.extraction.bank_parser import get_bank_parser
from src.models import PDFKind, StatementAnalysis, ValidationReport
from src.pdf_processing.errors import (
    OCRExtractionError,
    OCRUnavailableError,
    PDFEmptyError,
)
from src.pdf_processing.ocr_processor import OCRProcessor
from src.pdf_processing.pdf_detector import detect_pdf_type
from src.pdf_processing.text_extractor import (
    extract_table_rows,
    extract_text_pages,
    extract_text_with_pdfplumber,
)
from src.utils.logging_config import get_logger
from src.validation.balance_validator import BalanceValidator
from src.validation.transaction_validator import TransactionValidator

logger = get_logger("pipeline")


class StatementProcessingPipeline:
    """Coordinates detection, extraction, classification, and validation."""

    def __init__(
        self,
        classification_engine: ClassificationEngine | None = None,
        ocr_processor: OCRProcessor | None = None,
        account_extractor: AccountExtractor | None = None,
    ) -> None:
        self.ocr_processor = ocr_processor or OCRProcessor()
        self.account_extractor = account_extractor or AccountExtractor()
        self.classification_engine = classification_engine or self._default_engine()
        self.transaction_validator = TransactionValidator()
        self.balance_validator = BalanceValidator()

    def analyze(
        self, pdf_path: str | Path, password: str | None = None
    ) -> StatementAnalysis:
        """Process one statement PDF and return a complete analysis object."""

        pdf_path = Path(pdf_path)
        pdf_info = detect_pdf_type(pdf_path, password=password)
        if pdf_info.kind == PDFKind.EMPTY:
            raise PDFEmptyError("No readable text or images were found in this PDF.")

        warnings = list(pdf_info.warnings)
        page_texts, used_ocr = self._extract_document_text(
            pdf_path, pdf_info.kind, pdf_info.image_page_numbers, password, warnings
        )
        combined_text = "\n".join(page_texts).strip()
        if not combined_text:
            raise PDFEmptyError(
                "No readable text could be extracted. For scanned PDFs, verify that "
                "Tesseract OCR is installed and the scan quality is sufficient."
            )

        account = self.account_extractor.extract(combined_text)
        parser = get_bank_parser(combined_text, bank_name=account.bank_name)
        tables = extract_table_rows(pdf_path, password=password)
        extraction_result = parser.parse(
            pages=page_texts, account=account, tables=tables
        )
        warnings.extend(extraction_result.warnings)

        if not self.classification_engine.ml_available:
            warnings.append(
                "The machine-learning model is unavailable, so only deterministic "
                "rule-based classification was applied."
            )

        transactions = self.classification_engine.classify_all(
            extraction_result.transactions
        )

        validation = ValidationReport()
        validation.extend(self.transaction_validator.validate(transactions))
        validation.extend(self.balance_validator.validate(transactions, account))

        logger.info(
            "Analysis complete: %s pages, %s transactions, %s validation issues",
            pdf_info.page_count,
            len(transactions),
            len(validation.issues),
        )
        return StatementAnalysis(
            source_name=pdf_path.name,
            pdf_info=pdf_info,
            account=account,
            transactions=transactions,
            validation=validation,
            parser_name=parser.name,
            warnings=warnings,
            used_ocr=used_ocr,
        )

    def _extract_document_text(
        self,
        pdf_path: Path,
        kind: PDFKind,
        image_page_numbers: list[int],
        password: str | None,
        warnings: list[str],
    ) -> tuple[list[str], bool]:
        if kind == PDFKind.TEXT:
            pages = extract_text_pages(pdf_path, password=password)
            if not any(page.strip() for page in pages):
                pages = extract_text_with_pdfplumber(pdf_path, password=password)
            return pages, False

        pages = extract_text_pages(pdf_path, password=password)
        if len(pages) < max(image_page_numbers, default=0):
            pages.extend([""] * (max(image_page_numbers, default=len(pages)) - len(pages)))

        used_ocr = False
        for page_number in image_page_numbers:
            page_index = page_number - 1
            existing_text = pages[page_index] if page_index < len(pages) else ""
            if len(existing_text.strip()) >= MIN_TEXT_CHARS_PER_PAGE:
                continue
            try:
                ocr_text = self.ocr_processor.ocr_page(
                    pdf_path, page_index, password=password
                )
            except OCRUnavailableError:
                if kind == PDFKind.MIXED and any(page.strip() for page in pages):
                    warnings.append(
                        f"OCR was unavailable for page {page_number}; its text layer "
                        "was used where present."
                    )
                    continue
                raise
            except OCRExtractionError as exc:
                warnings.append(f"OCR failed for page {page_number}: {exc}")
                continue

            if not ocr_text:
                warnings.append(f"OCR returned no text for page {page_number}.")
                continue
            while len(pages) <= page_index:
                pages.append("")
            pages[page_index] = ocr_text
            used_ocr = True

        return pages, used_ocr

    @staticmethod
    def _default_engine() -> ClassificationEngine:
        ml_classifier = MLClassifier()
        ml_classifier.ensure_trained()
        return ClassificationEngine(
            rule_classifier=RuleClassifier(),
            ml_classifier=ml_classifier,
        )
