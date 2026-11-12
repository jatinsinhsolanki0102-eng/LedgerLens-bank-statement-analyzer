"""Financial overview dashboard."""

from __future__ import annotations

import streamlit as st

from src.ui.charts import PLOTLY_CONFIG, category_expense_bar
from src.ui.components import (
    build_transaction_dataframe,
    calculate_totals,
    category_expense_dataframe,
    format_inr,
    render_account_strip,
    render_empty_state,
    render_page_header,
    render_status_badges,
)


def render() -> None:
    analysis = st.session_state.get("analysis")
    if not analysis:
        render_page_header(
            "Dashboard",
            "A concise view of cash flow, balances, and spending categories.",
            eyebrow="Overview",
        )
        render_empty_state(
            "No statement loaded",
            "Upload a bank statement PDF to see income, expenses, balances, and "
            "category-level spending insights.",
        )
        return

    transactions = analysis.transactions
    totals = calculate_totals(analysis)
    render_page_header(
        "Dashboard",
        "A concise view of cash flow, balances, and spending categories.",
        eyebrow="Overview",
        meta_label="transactions",
        meta_value=f"{len(transactions):,}",
    )
    render_status_badges(analysis)
    st.write("")
    render_account_strip(analysis.account)

    income_col, expense_col, net_col, balance_col, count_col = st.columns(5)
    income_col.metric("Total income", format_inr(totals["income"]))
    expense_col.metric("Total expenses", format_inr(totals["expenses"]))
    net_col.metric("Net cash flow", format_inr(totals["net"]))
    balance_col.metric("Latest balance", format_inr(totals["latest_balance"]))
    count_col.metric("Transactions", f"{totals['transaction_count']:,}")

    if totals["review_count"]:
        st.warning(
            f"{totals['review_count']} transaction(s) are marked for review. "
            "Open Transactions to inspect or correct their categories."
        )

    st.write("")
    left_column, right_column = st.columns([1.5, 1])
    with left_column:
        st.markdown(
            '<div class="ll-section-title">Expense breakdown by category</div>'
            '<div class="ll-section-subtitle">Debit transactions grouped by assigned category.</div>',
            unsafe_allow_html=True,
        )
        category_data = category_expense_dataframe(transactions)
        if category_data.empty:
            st.info("No debit transactions are available for a category breakdown.")
        else:
            st.plotly_chart(
                category_expense_bar(category_data, height=380),
                use_container_width=True,
                config=PLOTLY_CONFIG,
            )

    with right_column:
        st.markdown(
            '<div class="ll-section-title">Financial snapshot</div>'
            '<div class="ll-section-subtitle">Key figures from the extracted statement.</div>',
            unsafe_allow_html=True,
        )
        st.metric("Average expense", format_inr(totals["average_expense"]))
        st.metric(
            "Inflows / outflows",
            f"{sum((item.credit or 0) > 0 for item in transactions):,} / "
            f"{sum((item.debit or 0) > 0 for item in transactions):,}",
            help="Number of credit and debit transactions.",
        )
        st.metric(
            "Opening balance",
            format_inr(analysis.account.opening_balance),
        )
        st.metric(
            "Closing balance",
            format_inr(analysis.account.closing_balance),
        )

    st.write("")
    st.markdown(
        '<div class="ll-section-title">Recent transactions</div>'
        '<div class="ll-section-subtitle">The latest rows in statement order.</div>',
        unsafe_allow_html=True,
    )
    if not transactions:
        st.info("No transactions were extracted from this statement.")
        return

    recent = build_transaction_dataframe(transactions[-8:])
    display_columns = [
        "Date",
        "Description",
        "Debit",
        "Credit",
        "Balance",
        "Category",
        "Method",
        "Confidence",
    ]
    st.dataframe(
        recent[display_columns],
        hide_index=True,
        use_container_width=True,
        column_config={
            "Debit": st.column_config.NumberColumn(format="%.2f"),
            "Credit": st.column_config.NumberColumn(format="%.2f"),
            "Balance": st.column_config.NumberColumn(format="%.2f"),
            "Confidence": st.column_config.NumberColumn("Confidence %", format="%.1f"),
            "Date": st.column_config.DateColumn(format="DD-MMM-YYYY"),
        },
        height=min(360, 40 + 35 * len(recent)),
    )
    st.markdown(
        '<div class="ll-note">Totals include all extracted debits and credits, '
        "including transfers between accounts.</div>",
        unsafe_allow_html=True,
    )
