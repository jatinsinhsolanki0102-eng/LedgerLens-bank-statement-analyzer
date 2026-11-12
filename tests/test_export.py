"""Excel and CSV export tests."""

from __future__ import annotations

from datetime import date
from io import BytesIO

from openpyxl import load_workbook

from src.export import (
    build_account_summary_frame,
    build_category_summary_frame,
    build_csv_bytes,
    build_excel_workbook_bytes,
    build_transactions_frame,
    build_validation_frame,
)
from src.models import (
    AccountInfo,
    IssueSeverity,
    PDFInfo,
    PDFKind,
    StatementAnalysis,
    Transaction,
    ValidationIssue,
    ValidationReport,
)


def _analysis() -> StatementAnalysis:
    account = AccountInfo(
        account_holder_name="AARAV SHARMA",
        account_number="50100123456789",
        ifsc_code="HDFC0001234",
        bank_name="HDFC Bank",
        statement_period_start=date(2024, 4, 1),
        statement_period_end=date(2024, 4, 30),
        opening_balance=125000.0,
        closing_balance=208750.0,
    )
    transactions = [
        Transaction(
            transaction_date=date(2024, 4, 1),
            description="SALARY CREDIT ACME CORP",
            credit=85000.0,
            balance=210000.0,
            category="Income",
            classification_method="Rule-based",
            confidence_score=0.97,
            source_page=1,
            raw_text="01/04/2024 SALARY CREDIT ACME CORP 85000.00 210000.00",
        ),
        Transaction(
            transaction_date=date(2024, 4, 2),
            description="=HYPERLINK(\"https://example.invalid\")",
            debit=1250.0,
            balance=208750.0,
            category="Food & Dining",
            classification_method="Machine Learning",
            confidence_score=0.88,
            source_page=1,
            raw_text="02/04/2024 ZOMATO 1250.00 208750.00",
        ),
    ]
    validation = ValidationReport(
        issues=[
            ValidationIssue(
                code="TEST_WARNING",
                message="A test warning.",
                severity=IssueSeverity.WARNING,
                transaction_index=1,
                field_name="description",
            )
        ]
    )
    return StatementAnalysis(
        source_name="statement.pdf",
        pdf_info=PDFInfo(page_count=1, kind=PDFKind.TEXT, encrypted=False),
        account=account,
        transactions=transactions,
        validation=validation,
        parser_name="HDFC Bank layout parser",
        used_ocr=False,
    )


def test_transaction_frame_columns_and_formula_neutralisation() -> None:
    frame = build_transactions_frame(_analysis())

    assert list(frame.columns) == [
        "Date",
        "Description",
        "Debit",
        "Credit",
        "Balance",
        "Category",
        "Classification Method",
        "Confidence",
        "Needs Review",
        "Source Page",
        "Raw Text",
    ]
    assert frame.loc[1, "Description"].startswith("'=")
    assert frame.loc[0, "Needs Review"] == "No"


def test_category_summary_aggregates_and_orders() -> None:
    frame = build_category_summary_frame(_analysis())

    assert list(frame["Category"]) == ["Food & Dining", "Income"]
    salary = frame[frame["Category"] == "Income"].iloc[0]
    food = frame[frame["Category"] == "Food & Dining"].iloc[0]
    assert salary["Total Credit"] == 85000.0
    assert food["Total Debit"] == 1250.0
    assert food["Transactions"] == 1


def test_account_and_validation_summary_frames() -> None:
    analysis = _analysis()
    account_frame = build_account_summary_frame(analysis)
    secure_account_frame = build_account_summary_frame(
        analysis, include_full_account_number=True
    )
    validation_frame = build_validation_frame(analysis)

    assert {"Field", "Value"} == set(account_frame.columns)
    assert "**********6789" in set(account_frame["Value"])
    assert "50100123456789" not in set(account_frame["Value"])
    assert "50100123456789" in set(secure_account_frame["Value"])
    assert validation_frame.iloc[0]["Code"] == "TEST_WARNING"


def test_exports_mask_account_numbers_in_free_text_by_default() -> None:
    analysis = _analysis()
    analysis.transactions[1].description = (
        "TRANSFER FOR ACCOUNT 50100123456789 AND 5010-0123-4567-89"
    )
    analysis.transactions[1].raw_text = (
        "TRANSFER FOR ACCOUNT 50100123456789 AND 5010 0123 4567 89 1250.00"
    )

    default_transactions = build_transactions_frame(analysis)
    secure_transactions = build_transactions_frame(
        analysis, include_full_account_number=True
    )
    default_csv = build_csv_bytes(analysis).decode("utf-8-sig")
    secure_csv = build_csv_bytes(
        analysis, include_full_account_number=True
    ).decode("utf-8-sig")
    default_workbook = load_workbook(BytesIO(build_excel_workbook_bytes(analysis)))
    secure_workbook = load_workbook(
        BytesIO(build_excel_workbook_bytes(analysis, include_full_account_number=True))
    )

    assert "50100123456789" not in default_transactions.to_csv(index=False)
    assert "5010-0123-4567-89" not in default_transactions.to_csv(index=False)
    assert "5010 0123 4567 89" not in default_transactions.to_csv(index=False)
    assert default_transactions.loc[1, "Description"].count("**********6789") == 2
    assert "**********6789" in default_transactions.loc[1, "Raw Text"]
    assert "50100123456789" in secure_transactions.loc[1, "Description"]
    assert "5010-0123-4567-89" in secure_transactions.loc[1, "Description"]
    assert "50100123456789" not in default_csv
    assert "5010-0123-4567-89" not in default_csv
    assert "5010 0123 4567 89" not in default_csv
    assert "**********6789" in default_csv
    assert "50100123456789" in secure_csv
    assert default_workbook["Account Summary"]["B3"].value == "**********6789"
    assert secure_workbook["Account Summary"]["B3"].value == "50100123456789"


def test_empty_analysis_exports_have_stable_headers() -> None:
    analysis = _analysis()
    analysis.transactions = []
    analysis.validation = ValidationReport()

    category_frame = build_category_summary_frame(analysis)
    validation_frame = build_validation_frame(analysis)
    csv_bytes = build_csv_bytes(analysis)

    assert category_frame.empty
    assert list(category_frame.columns) == [
        "Category",
        "Transactions",
        "Total Debit",
        "Total Credit",
        "Net",
    ]
    assert validation_frame.iloc[0]["Code"] == "NO_ISSUES"
    assert len(csv_bytes) > 0


def test_masked_exports_handle_empty_and_missing_account_data() -> None:
    analysis = _analysis()
    analysis.account.account_number = None
    analysis.transactions = []
    analysis.validation = ValidationReport()

    account_frame = build_account_summary_frame(analysis)
    workbook = load_workbook(BytesIO(build_excel_workbook_bytes(analysis)))
    csv_text = build_csv_bytes(analysis).decode("utf-8-sig")

    assert "Not available" in set(account_frame["Value"])
    assert workbook["Account Summary"]["B3"].value == "Not available"
    assert workbook["Transactions"].max_row == 1
    assert "Date,Description" in csv_text
    assert len(csv_text.splitlines()) == 1


def test_excel_workbook_contains_expected_sheets() -> None:
    workbook_bytes = build_excel_workbook_bytes(_analysis())
    workbook = load_workbook(BytesIO(workbook_bytes))

    assert workbook.sheetnames == [
        "Transactions",
        "Account Summary",
        "Category Summary",
        "Validation Report",
    ]
    transactions = workbook["Transactions"]
    assert transactions.max_row == 3
    assert transactions["A1"].value == "Date"
    assert transactions["B3"].value.startswith("'=")
    assert transactions.freeze_panes == "A2"
    assert transactions.auto_filter.ref == transactions.dimensions

    summary = workbook["Account Summary"]
    assert summary["A1"].value == "Field"
    assert summary["A2"].font.bold

    validation = workbook["Validation Report"]
    assert validation["A1"].value == "Severity"
    assert validation["A2"].value == "Warning"


def test_csv_export_has_bom_and_all_rows() -> None:
    csv_bytes = build_csv_bytes(_analysis())
    decoded = csv_bytes.decode("utf-8-sig")

    assert csv_bytes.startswith(b"\xef\xbb\xbf")
    assert decoded.startswith("Date,Description,")
    assert "SALARY CREDIT ACME CORP" in decoded
    assert "'=HYPERLINK" in decoded
