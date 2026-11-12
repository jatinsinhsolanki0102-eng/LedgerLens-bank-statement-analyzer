"""End-to-end pipeline behavior for text, mixed, and scanned PDFs."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.models import PDFKind
from src.pdf_processing.errors import OCRUnavailableError, PDFEmptyError, PDFPasswordError
from src.pdf_processing.ocr_processor import OCRProcessor
from src.pipeline import StatementProcessingPipeline


class _FakeOCRProcessor:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[tuple[int, int]] = []

    def ocr_page(
        self, path: str | Path, page_number: int, password: str | None = None
    ) -> str:
        self.calls.append((page_number, len(self.text)))
        return self.text


def test_bundled_sample_end_to_end(bundled_sample_path: Path) -> None:
    analysis = StatementProcessingPipeline().analyze(bundled_sample_path)

    assert analysis.pdf_info.kind == PDFKind.TEXT
    assert analysis.pdf_info.page_count == 2
    assert analysis.account.account_holder_name == "AARAV SHARMA"
    assert analysis.account.account_number == "50100123456789"
    assert analysis.account.bank_name == "HDFC Bank"
    assert analysis.account.opening_balance == 125000.0
    assert analysis.account.closing_balance == 117287.0
    assert analysis.parser_name == "HDFC Bank layout parser"
    assert len(analysis.transactions) == 18
    assert not analysis.used_ocr
    assert analysis.warnings == []

    categories = {transaction.description: transaction.category for transaction in analysis.transactions}
    assert categories["SALARY CREDIT APRIL ACME CORP NEFT123"] == "Income"
    assert categories["UPI/ZOMATO/ORDER 445566 UPI445566"] == "Food & Dining"
    assert categories["ATM WITHDRAWAL MG ROAD ATM7788"] == "Cash Withdrawal"
    assert categories["NETFLIX SUBSCRIPTION NACH9988"] == "Entertainment"
    assert categories["HOUSE RENT PAYMENT LANDLORD IMPS776"] == "Housing"
    assert categories["MUTUAL FUND SIP AUTO DEBIT MF0098"] == "Investment"
    assert categories["CREDIT CARD PAYMENT CC8899"] == "Credit Card Payment"

    interest = analysis.transactions[-1]
    assert interest.category == "Income"
    assert not interest.needs_review
    assert interest.classification_method == "Rule-based"
    assert analysis.validation.error_count == 0
    assert analysis.validation.warning_count == 0


def test_generated_text_statement_end_to_end(text_statement_path: Path) -> None:
    analysis = StatementProcessingPipeline().analyze(text_statement_path)

    assert len(analysis.transactions) == 18
    assert analysis.transactions[0].credit == 85000.0
    assert analysis.transactions[0].balance == 210000.0
    assert analysis.transactions[-1].balance == 117287.0


def test_scanned_statement_uses_injected_ocr(
    scanned_pdf_path: Path, statement_lines: list[str]
) -> None:
    fake_ocr = _FakeOCRProcessor("\n".join(statement_lines))
    pipeline = StatementProcessingPipeline(ocr_processor=fake_ocr)

    analysis = pipeline.analyze(scanned_pdf_path)

    assert analysis.pdf_info.kind == PDFKind.SCANNED
    assert analysis.used_ocr
    assert len(analysis.transactions) == 18
    assert fake_ocr.calls


def test_mixed_statement_uses_ocr_for_image_page(
    mixed_pdf_path: Path,
) -> None:
    fake_ocr = _FakeOCRProcessor("SCANNED PAGE APPENDIX")
    pipeline = StatementProcessingPipeline(ocr_processor=fake_ocr)

    analysis = pipeline.analyze(mixed_pdf_path)

    assert analysis.pdf_info.kind == PDFKind.MIXED
    assert analysis.used_ocr
    assert len(analysis.transactions) == 18
    assert fake_ocr.calls == [(1, len("SCANNED PAGE APPENDIX"))]


def test_mixed_statement_continues_when_ocr_is_unavailable(
    mixed_pdf_path: Path, tmp_path: Path
) -> None:
    missing_tesseract = OCRProcessor(
        tesseract_cmd=str(tmp_path / "missing-tesseract.exe")
    )
    pipeline = StatementProcessingPipeline(ocr_processor=missing_tesseract)

    analysis = pipeline.analyze(mixed_pdf_path)

    assert analysis.pdf_info.kind == PDFKind.MIXED
    assert not analysis.used_ocr
    assert len(analysis.transactions) == 18
    assert any("OCR was unavailable" in warning for warning in analysis.warnings)


def test_scanned_statement_without_ocr_raises(
    scanned_pdf_path: Path, tmp_path: Path
) -> None:
    pipeline = StatementProcessingPipeline(
        ocr_processor=OCRProcessor(
            tesseract_cmd=str(tmp_path / "missing-tesseract.exe")
        )
    )

    with pytest.raises(OCRUnavailableError):
        pipeline.analyze(scanned_pdf_path)


def test_password_protected_pipeline(password_statement_path: Path) -> None:
    pipeline = StatementProcessingPipeline()

    with pytest.raises(PDFPasswordError):
        pipeline.analyze(password_statement_path)

    analysis = pipeline.analyze(password_statement_path, password="secret")
    assert analysis.pdf_info.encrypted
    assert len(analysis.transactions) == 18


def test_empty_pdf_pipeline_raises(empty_pdf_path: Path) -> None:
    with pytest.raises(PDFEmptyError):
        StatementProcessingPipeline().analyze(empty_pdf_path)
