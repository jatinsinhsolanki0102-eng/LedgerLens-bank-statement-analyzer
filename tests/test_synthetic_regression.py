"""Regression coverage for the bundled 60-transaction synthetic dataset."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from config.category_rules import OTHER_CATEGORY
from src.export import build_csv_bytes, build_excel_workbook_bytes
from src.extraction.account_extractor import AccountExtractor
from src.pipeline import StatementProcessingPipeline

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "ledgerlens_synthetic"


def _evaluate_synthetic_statements() -> pd.DataFrame:
    ground_truth = pd.read_csv(FIXTURE_DIR / "ground_truth_transactions.csv")
    pipeline = StatementProcessingPipeline()
    records: list[dict[str, object]] = []

    for statement_file, expected_rows in ground_truth.groupby(
        "statement_file", sort=False
    ):
        analysis = pipeline.analyze(FIXTURE_DIR / statement_file)
        assert len(analysis.transactions) == len(expected_rows)
        assert analysis.validation.error_count == 0

        for transaction, expected in zip(
            analysis.transactions, expected_rows.itertuples(), strict=True
        ):
            expected_date = pd.to_datetime(expected.date).date()
            assert transaction.transaction_date == expected_date
            assert expected.description in transaction.description
            assert expected.reference in transaction.description
            assert abs((transaction.debit or 0.0) - float(expected.debit)) < 0.01
            assert abs((transaction.credit or 0.0) - float(expected.credit)) < 0.01
            assert abs((transaction.balance or 0.0) - expected.expected_balance) < 0.01
            records.append(
                {
                    "statement_file": statement_file,
                    "description": transaction.description,
                    "expected_category": expected.expected_category,
                    "actual_category": transaction.category,
                    "classification_method": transaction.classification_method,
                    "confidence": transaction.confidence_score,
                    "needs_review": transaction.needs_review,
                }
            )

    frame = pd.DataFrame(records)
    frame["correct"] = frame["actual_category"] == frame["expected_category"]
    frame["incorrect_high_confidence"] = (~frame["correct"]) & (
        frame["confidence"].fillna(0.0) >= 0.80
    )
    return frame


def _workbook_text(workbook: object) -> str:
    values: list[str] = []
    for worksheet in workbook.worksheets:
        for row in worksheet.iter_rows():
            for cell in row:
                if cell.value is not None:
                    values.append(str(cell.value))
    return "\n".join(values)


def test_synthetic_60_transaction_regression() -> None:
    results = _evaluate_synthetic_statements()

    assert len(results) == 60
    assert set(results["statement_file"]) == {
        "01_standard_statement.pdf",
        "02_mixed_transactions.pdf",
        "03_extended_statement.pdf",
    }
    assert results["correct"].all()
    assert not results["incorrect_high_confidence"].any()

    review_counts = (
        results.groupby("statement_file")["needs_review"].sum().to_dict()
    )
    assert review_counts == {
        "01_standard_statement.pdf": 0,
        "02_mixed_transactions.pdf": 0,
        "03_extended_statement.pdf": 2,
    }

    ambiguous = results[
        results["description"].str.contains("UNKNOWN MERCHANT|UPI PAYMENT REF")
    ]
    assert len(ambiguous) == 2
    assert ambiguous["needs_review"].all()
    assert set(ambiguous["actual_category"]) == {OTHER_CATEGORY}
    assert set(ambiguous["classification_method"]) == {"Ambiguous - Needs Review"}


def test_all_three_statements_export_masked_by_default() -> None:
    pipeline = StatementProcessingPipeline()

    for pdf_path in sorted(FIXTURE_DIR.glob("*.pdf")):
        analysis = pipeline.analyze(pdf_path)
        full_account = analysis.account.account_number
        assert full_account
        masked_account = AccountExtractor.mask_account_number(full_account)

        workbook = load_workbook(
            BytesIO(build_excel_workbook_bytes(analysis))
        )
        assert workbook.sheetnames == [
            "Transactions",
            "Account Summary",
            "Category Summary",
            "Validation Report",
        ]
        assert workbook["Transactions"].max_row == len(analysis.transactions) + 1
        assert full_account not in _workbook_text(workbook)
        assert workbook["Account Summary"]["B3"].value == masked_account

        csv_text = build_csv_bytes(analysis).decode("utf-8-sig")
        assert full_account not in csv_text
        assert len(csv_text.splitlines()) == len(analysis.transactions) + 1

        secure_workbook = load_workbook(
            BytesIO(
                build_excel_workbook_bytes(
                    analysis, include_full_account_number=True
                )
            )
        )
        assert secure_workbook["Account Summary"]["B3"].value == full_account
