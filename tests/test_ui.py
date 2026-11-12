"""Streamlit helper and application smoke tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.models import AccountInfo, PDFInfo, PDFKind, StatementAnalysis, Transaction, ValidationReport
from src.ui.components import (
    apply_manual_category,
    build_account_strip_html,
    build_transaction_dataframe,
    calculate_totals,
    sanitize_filename,
    transaction_date_range,
)


def _analysis() -> StatementAnalysis:
    return StatementAnalysis(
        source_name="statement.pdf",
        pdf_info=PDFInfo(page_count=1, kind=PDFKind.TEXT, encrypted=False),
        account=AccountInfo(
            account_holder_name="AARAV SHARMA",
            account_number="50100123456789",
            ifsc_code="HDFC0001234",
            bank_name="HDFC Bank",
            statement_period_start=date(2024, 4, 1),
            statement_period_end=date(2024, 4, 30),
            opening_balance=1000.0,
            closing_balance=1400.0,
        ),
        transactions=[
            Transaction(
                transaction_date=date(2024, 4, 1),
                description="SALARY",
                credit=1000.0,
                balance=2000.0,
                category="Salary",
                classification_method="Rule-based",
                confidence_score=0.97,
            ),
            Transaction(
                transaction_date=date(2024, 4, 2),
                description="SHOP",
                debit=600.0,
                balance=1400.0,
                category="Shopping",
                classification_method="Machine Learning",
                confidence_score=0.70,
                needs_review=True,
            ),
        ],
        validation=ValidationReport(),
        parser_name="Generic layout parser",
    )


def test_calculate_totals() -> None:
    totals = calculate_totals(_analysis())

    assert totals["income"] == 1000.0
    assert totals["expenses"] == 600.0
    assert totals["net"] == 400.0
    assert totals["latest_balance"] == 1400.0
    assert totals["transaction_count"] == 2
    assert totals["review_count"] == 1
    assert totals["average_expense"] == 600.0


def test_manual_category_correction() -> None:
    transaction = _analysis().transactions[1]

    apply_manual_category(transaction, "Shopping")

    assert transaction.category == "Shopping"
    assert transaction.classification_method == "Manual"
    assert transaction.confidence_score == 1.0
    assert not transaction.needs_review


def test_transaction_dataframe_and_date_range() -> None:
    analysis = _analysis()
    frame = build_transaction_dataframe(analysis.transactions)
    start, end = transaction_date_range(analysis.transactions)

    assert list(frame.columns) == [
        "ID",
        "Date",
        "Description",
        "Debit",
        "Credit",
        "Balance",
        "Category",
        "Method",
        "Confidence",
        "Review",
    ]
    assert frame.loc[1, "Review"] == "Needs review"
    assert (start, end) == (date(2024, 4, 1), date(2024, 4, 2))


def test_filename_sanitisation() -> None:
    assert sanitize_filename("my statement (final).pdf") == "my_statement_final_.pdf"
    assert sanitize_filename("", fallback="fallback") == "fallback"


def test_account_strip_html_masks_number_and_has_no_indentation() -> None:
    markup = build_account_strip_html(_analysis().account)

    assert markup.startswith('<div class="ll-account-strip"><div class="ll-account-item">')
    assert markup.count('class="ll-account-item"') == 5
    assert "AARAV SHARMA" in markup
    assert "HDFC Bank" in markup
    assert "HDFC0001234" in markup
    assert "01 Apr 2024" in markup
    assert "50100123456789" not in markup
    assert "**********6789" in markup
    assert "\n" not in markup


def test_upload_page_renders_account_details_markup() -> None:
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=30)
    app.session_state["analysis"] = _analysis()
    app.session_state["navigation"] = "Upload Statement"

    app.run()

    assert not app.exception
    account_markup = next(
        block.value
        for block in app.markdown
        if block.value.startswith('<div class="ll-account-strip">')
    )
    assert "50100123456789" not in account_markup
    assert "**********6789" in account_markup
    assert "HDFC Bank" in account_markup
    assert "HDFC0001234" in account_markup
    assert "\n" not in account_markup


def test_secure_export_permission_resets_when_leaving_export_page() -> None:
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=30)
    app.session_state["secure_export_opt_in"] = True
    app.session_state["_last_navigation"] = "Export"
    app.session_state["navigation"] = "Dashboard"

    app.run()

    assert not app.exception
    assert app.session_state["secure_export_opt_in"] is False


def test_streamlit_app_renders_every_page_without_analysis() -> None:
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=30)
    app.run()

    assert not app.exception
    assert app.radio[0].value == "Dashboard"

    for page in ("Upload Statement", "Transactions", "Analytics", "Export", "Dashboard"):
        app.radio[0].set_value(page).run()
        assert not app.exception, page

    app.radio[0].set_value("Upload Statement").run()
    assert len(app.get("file_uploader")) == 1
