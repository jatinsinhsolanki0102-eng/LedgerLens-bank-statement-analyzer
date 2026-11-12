"""Reusable Streamlit presentation helpers."""

from __future__ import annotations

import html
import re
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from config.category_rules import CATEGORIES
from config.settings import APP_TITLE, CURRENCY_SYMBOL, PRIVACY_NOTICE
from src.extraction.account_extractor import AccountExtractor
from src.models import AccountInfo, StatementAnalysis, Transaction
from src.utils.amount_utils import format_currency


def render_page_header(
    title: str,
    subtitle: str,
    eyebrow: str | None = None,
    meta_label: str | None = None,
    meta_value: str | None = None,
) -> None:
    eyebrow_html = (
        f'<div class="ll-eyebrow">{html.escape(eyebrow)}</div>' if eyebrow else ""
    )
    meta_html = ""
    if meta_label and meta_value:
        meta_html = (
            '<div class="ll-header-meta">'
            f"<strong>{html.escape(meta_value)}</strong>"
            f"{html.escape(meta_label)}</div>"
        )
    st.markdown(
        f"""
        <div class="ll-page-header">
            <div>
                {eyebrow_html}
                <h1 class="ll-page-title">{html.escape(title)}</h1>
                <div class="ll-page-subtitle">{html.escape(subtitle)}</div>
            </div>
            {meta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state(
    title: str,
    message: str,
    destination: str = "Upload Statement",
    button_label: str = "Upload a statement",
) -> None:
    def _navigate() -> None:
        st.session_state.navigation = destination

    st.markdown(
        f"""
        <div class="ll-empty">
            <div class="ll-empty-mark">LL</div>
            <h2>{html.escape(title)}</h2>
            <p>{html.escape(message)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    left, center, right = st.columns([1, 1, 1])
    with center:
        st.button(button_label, on_click=_navigate, use_container_width=True, type="primary")


def render_privacy_notice() -> None:
    st.markdown(
        f'<div class="ll-privacy"><strong>Privacy:</strong> {html.escape(PRIVACY_NOTICE)}</div>',
        unsafe_allow_html=True,
    )


def build_account_strip_html(account: AccountInfo) -> str:
    values = (
        ("Account holder", account.account_holder_name or "Not available"),
        (
            "Account number",
            AccountExtractor.mask_account_number(account.account_number),
        ),
        ("Bank", account.bank_name or "Not available"),
        ("IFSC", account.ifsc_code or "Not available"),
        ("Statement period", account.statement_period_label or "Not available"),
    )
    cards = "".join(
        '<div class="ll-account-item">'
        f'<div class="ll-account-label">{html.escape(label)}</div>'
        f'<div class="ll-account-value">{html.escape(str(value))}</div>'
        "</div>"
        for label, value in values
    )
    return f'<div class="ll-account-strip">{cards}</div>'


def render_account_strip(account: AccountInfo) -> None:
    st.markdown(build_account_strip_html(account), unsafe_allow_html=True)


def badge(label: str, tone: str = "neutral") -> str:
    return f'<span class="ll-badge ll-badge-{tone}">{html.escape(label)}</span>'


def format_inr(value: float | None) -> str:
    return format_currency(value, include_symbol=True)


def format_percent(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.{decimals}f}%"


def calculate_totals(analysis: StatementAnalysis) -> dict[str, float | int | None]:
    total_income = sum(
        transaction.credit or 0.0 for transaction in analysis.transactions
    )
    total_expenses = sum(
        transaction.debit or 0.0 for transaction in analysis.transactions
    )
    latest_balance = next(
        (
            transaction.balance
            for transaction in reversed(analysis.transactions)
            if transaction.balance is not None
        ),
        analysis.account.closing_balance,
    )
    review_count = sum(
        transaction.needs_review for transaction in analysis.transactions
    )
    return {
        "income": round(total_income, 2),
        "expenses": round(total_expenses, 2),
        "net": round(total_income - total_expenses, 2),
        "latest_balance": latest_balance,
        "transaction_count": len(analysis.transactions),
        "review_count": review_count,
        "average_expense": round(
            total_expenses / max(sum(1 for item in analysis.transactions if item.debit), 1),
            2,
        ),
    }


def build_transaction_dataframe(transactions: list[Transaction]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for index, transaction in enumerate(transactions, start=1):
        rows.append(
            {
                "ID": index,
                "Date": transaction.transaction_date,
                "Description": transaction.description,
                "Debit": transaction.debit,
                "Credit": transaction.credit,
                "Balance": transaction.balance,
                "Category": transaction.category,
                "Method": transaction.classification_method,
                "Confidence": round((transaction.confidence_score or 0.0) * 100, 1),
                "Review": "Needs review" if transaction.needs_review else "",
            }
        )
    return pd.DataFrame(rows)


def category_expense_dataframe(transactions: list[Transaction]) -> pd.DataFrame:
    rows = [
        {"Category": transaction.category, "Amount": transaction.debit or 0.0}
        for transaction in transactions
        if (transaction.debit or 0.0) > 0
    ]
    if not rows:
        return pd.DataFrame(columns=["Category", "Amount"])
    dataframe = pd.DataFrame(rows)
    grouped = (
        dataframe.groupby("Category", as_index=False)["Amount"]
        .sum()
        .sort_values("Amount", ascending=False)
    )
    return grouped


def latest_transaction_source_label(analysis: StatementAnalysis) -> str:
    if not analysis.source_name:
        return "Statement loaded"
    return analysis.source_name


def sanitize_filename(value: str, fallback: str = "bank_statement") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "").strip("._")
    return cleaned or fallback


def render_status_badges(analysis: StatementAnalysis) -> None:
    kind = analysis.pdf_info.kind.value
    badges = [badge(kind, "info")]
    if analysis.used_ocr:
        badges.append(badge("OCR used", "warning"))
    if analysis.validation.error_count:
        badges.append(badge(f"{analysis.validation.error_count} errors", "danger"))
    if analysis.validation.warning_count:
        badges.append(
            badge(f"{analysis.validation.warning_count} warnings", "warning")
        )
    if not analysis.validation.error_count and not analysis.validation.warning_count:
        badges.append(badge("Validation clear", "success"))
    st.markdown(" ".join(badges), unsafe_allow_html=True)


def render_note(message: str) -> None:
    st.markdown(f'<div class="ll-note">{html.escape(message)}</div>', unsafe_allow_html=True)


def apply_manual_category(transaction: Transaction, category: str) -> None:
    """Apply a user correction and mark the classification as manual."""

    if category not in CATEGORIES:
        raise ValueError("Unknown category.")
    transaction.category = category
    transaction.classification_method = "Manual"
    transaction.confidence_score = 1.0
    transaction.needs_review = False


def transaction_date_range(transactions: list[Transaction]) -> tuple[date | None, date | None]:
    dates = [
        transaction.transaction_date
        for transaction in transactions
        if transaction.transaction_date is not None
    ]
    if not dates:
        return None, None
    return min(dates), max(dates)


def app_identity() -> str:
    return APP_TITLE


def currency_symbol() -> str:
    return CURRENCY_SYMBOL


def make_data_editor_config() -> dict[str, Any]:
    return {
        "ID": st.column_config.NumberColumn("ID", width="small"),
        "Date": st.column_config.DateColumn("Date", format="DD-MMM-YYYY"),
        "Description": st.column_config.TextColumn("Description", width="large"),
        "Debit": st.column_config.NumberColumn("Debit", format="%.2f"),
        "Credit": st.column_config.NumberColumn("Credit", format="%.2f"),
        "Balance": st.column_config.NumberColumn("Balance", format="%.2f"),
        "Category": st.column_config.SelectboxColumn(
            "Category", options=list(CATEGORIES), required=True, width="medium"
        ),
        "Method": st.column_config.TextColumn("Method"),
        "Confidence": st.column_config.NumberColumn(
            "Confidence %", format="%.1f"
        ),
        "Review": st.column_config.TextColumn("Review"),
    }
