"""Regression tests for analytics aggregation and monthly cash-flow charts."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.models import (
    AccountInfo,
    PDFInfo,
    PDFKind,
    StatementAnalysis,
    Transaction,
    ValidationReport,
)
from src.ui.analytics_page import _build_monthly_data
from src.ui.charts import CORAL, TEAL, monthly_net_line


def _transaction(
    transaction_date: date | None,
    description: str,
    *,
    debit: float | None = None,
    credit: float | None = None,
) -> Transaction:
    return Transaction(
        transaction_date=transaction_date,
        description=description,
        debit=debit,
        credit=credit,
    )


def _analysis(transactions: list[Transaction]) -> StatementAnalysis:
    return StatementAnalysis(
        source_name="01_standard_statement.pdf",
        pdf_info=PDFInfo(page_count=1, kind=PDFKind.TEXT, encrypted=False),
        account=AccountInfo(),
        transactions=transactions,
        validation=ValidationReport(),
        parser_name="Generic layout parser",
    )


def test_monthly_net_for_single_month() -> None:
    monthly_data, undated_count = _build_monthly_data(
        [
            _transaction(date(2024, 4, 1), "SALARY", credit=1_000.0),
            _transaction(date(2024, 4, 2), "SHOP", debit=600.0),
        ]
    )

    assert undated_count == 0
    assert list(monthly_data.columns) == ["Month", "Income", "Expenses", "Net"]
    assert monthly_data.to_dict("records") == [
        {
            "Month": "Apr 2024",
            "Income": 1_000.0,
            "Expenses": 600.0,
            "Net": 400.0,
        }
    ]


def test_monthly_net_for_multiple_months_and_chart_colors() -> None:
    monthly_data, undated_count = _build_monthly_data(
        [
            _transaction(date(2024, 1, 5), "SALARY", credit=1_000.0),
            _transaction(date(2024, 1, 9), "RENT", debit=250.0),
            _transaction(date(2024, 2, 4), "REFUND", credit=100.0),
            _transaction(date(2024, 2, 12), "SHOP", debit=300.0),
        ]
    )

    assert undated_count == 0
    assert monthly_data["Month"].tolist() == ["Jan 2024", "Feb 2024"]
    assert monthly_data["Net"].tolist() == [750.0, -200.0]

    figure = monthly_net_line(monthly_data)
    assert list(figure.data[0].x) == ["Jan 2024", "Feb 2024"]
    assert list(figure.data[0].y) == [750.0, -200.0]
    assert list(figure.data[0].marker.color) == [TEAL, CORAL]


def test_monthly_net_columns_exist_for_empty_transactions() -> None:
    monthly_data, undated_count = _build_monthly_data([])

    assert monthly_data.empty
    assert list(monthly_data.columns) == ["Month", "Income", "Expenses", "Net"]
    assert undated_count == 0


def test_monthly_net_columns_exist_for_undated_transactions() -> None:
    monthly_data, undated_count = _build_monthly_data(
        [
            _transaction(None, "UNKNOWN DATE", debit=50.0),
            _transaction(None, "ALSO UNDATED", credit=75.0),
        ]
    )

    assert monthly_data.empty
    assert list(monthly_data.columns) == ["Month", "Income", "Expenses", "Net"]
    assert undated_count == 2


def test_analytics_page_renders_multiple_month_cash_flow() -> None:
    analysis = _analysis(
        [
            _transaction(date(2024, 1, 5), "SALARY", credit=1_000.0),
            _transaction(date(2024, 1, 9), "RENT", debit=250.0),
            _transaction(date(2024, 2, 4), "REFUND", credit=100.0),
            _transaction(date(2024, 2, 12), "SHOP", debit=300.0),
        ]
    )
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=30)
    app.session_state["analysis"] = analysis
    app.session_state["navigation"] = "Analytics"

    app.run()

    assert not app.exception
    assert len(app.dataframe) == 1
    summary = app.dataframe[0].value
    assert list(summary.columns) == ["Month", "Income", "Expenses", "Net"]
    assert summary["Net"].tolist() == [750.0, -200.0]
