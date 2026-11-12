"""Deeper spending, income, and trend analytics."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.ui.charts import (
    PLOTLY_CONFIG,
    balance_trend,
    category_donut,
    debit_credit_distribution,
    monthly_cashflow_bar,
    monthly_net_line,
)
from src.ui.components import (
    calculate_totals,
    category_expense_dataframe,
    format_inr,
    format_percent,
    render_empty_state,
    render_page_header,
)


def render() -> None:
    analysis = st.session_state.get("analysis")
    if not analysis:
        render_page_header(
            "Analytics",
            "Understand monthly patterns, category concentration, and balance movement.",
            eyebrow="Insights",
        )
        render_empty_state(
            "Analytics will appear after processing",
            "Upload a statement to unlock monthly cash-flow charts, category "
            "distribution, and balance trends.",
        )
        return

    render_page_header(
        "Analytics",
        "Understand monthly patterns, category concentration, and balance movement.",
        eyebrow="Insights",
        meta_label="statement",
        meta_value=analysis.account.statement_period_label or analysis.source_name,
    )

    if not analysis.transactions:
        st.info("No transactions are available to analyse.")
        return

    transactions = analysis.transactions
    totals = calculate_totals(analysis)
    category_data = category_expense_dataframe(transactions)
    monthly_data, undated_count = _build_monthly_data(transactions)

    savings_rate = (
        totals["net"] / totals["income"] if totals["income"] else None
    )
    top_category = (
        category_data.iloc[0]["Category"] if not category_data.empty else "Not available"
    )
    top_category_amount = (
        category_data.iloc[0]["Amount"] if not category_data.empty else None
    )
    average_monthly_spend = (
        monthly_data["Expenses"].mean() if not monthly_data.empty else None
    )
    largest_expense = max(
        (transaction for transaction in transactions if transaction.debit),
        key=lambda item: item.debit or 0.0,
        default=None,
    )

    savings_col, category_col, monthly_col, largest_col = st.columns(4)
    savings_col.metric(
        "Savings rate",
        format_percent(savings_rate),
        help="Net cash flow divided by total income.",
    )
    category_col.metric(
        "Top expense category",
        top_category,
        delta=format_inr(top_category_amount) if top_category_amount else None,
    )
    monthly_col.metric("Average monthly spend", format_inr(average_monthly_spend))
    largest_col.metric(
        "Largest expense",
        format_inr(largest_expense.debit if largest_expense else None),
        help=largest_expense.description[:80] if largest_expense else None,
    )

    if undated_count:
        st.info(
            f"{undated_count} transaction(s) have no usable date and are excluded "
            "from monthly charts."
        )

    st.write("")
    flow_column, net_column = st.columns(2)
    with flow_column:
        st.markdown(
            '<div class="ll-section-title">Income vs expenses</div>'
            '<div class="ll-section-subtitle">Monthly totals across the statement period.</div>',
            unsafe_allow_html=True,
        )
        if monthly_data.empty:
            st.info("Monthly flow requires at least one dated transaction.")
        else:
            st.plotly_chart(
                monthly_cashflow_bar(monthly_data),
                use_container_width=True,
                config=PLOTLY_CONFIG,
            )
    with net_column:
        st.markdown(
            '<div class="ll-section-title">Monthly net cash flow</div>'
            '<div class="ll-section-subtitle">Positive months are shown in teal; deficits in coral.</div>',
            unsafe_allow_html=True,
        )
        if monthly_data.empty:
            st.info("Monthly net cash flow requires at least one dated transaction.")
        else:
            st.plotly_chart(
                monthly_net_line(monthly_data),
                use_container_width=True,
                config=PLOTLY_CONFIG,
            )

    category_column, trend_column = st.columns([1, 1.35])
    with category_column:
        st.markdown(
            '<div class="ll-section-title">Category distribution</div>'
            '<div class="ll-section-subtitle">Share of total debit spending.</div>',
            unsafe_allow_html=True,
        )
        if category_data.empty:
            st.info("No debit transactions are available.")
        else:
            st.plotly_chart(
                category_donut(category_data),
                use_container_width=True,
                config=PLOTLY_CONFIG,
            )
    with trend_column:
        st.markdown(
            '<div class="ll-section-title">Balance trend</div>'
            '<div class="ll-section-subtitle">Observed running balance over time.</div>',
            unsafe_allow_html=True,
        )
        if not any(item.balance is not None for item in transactions):
            st.info("The statement does not include running balances.")
        else:
            st.plotly_chart(
                balance_trend(transactions),
                use_container_width=True,
                config=PLOTLY_CONFIG,
            )

    distribution_column, summary_column = st.columns([1.2, 1])
    with distribution_column:
        st.markdown(
            '<div class="ll-section-title">Transaction distribution</div>'
            '<div class="ll-section-subtitle">Count of debit and credit entries.</div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(
            debit_credit_distribution(transactions),
            use_container_width=True,
            config=PLOTLY_CONFIG,
        )
    with summary_column:
        st.markdown(
            '<div class="ll-section-title">Monthly summary</div>'
            '<div class="ll-section-subtitle">A compact view of dated cash flow.</div>',
            unsafe_allow_html=True,
        )
        if monthly_data.empty:
            st.info("No dated transactions available.")
        else:
            st.dataframe(
                monthly_data,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Income": st.column_config.NumberColumn(format="%.2f"),
                    "Expenses": st.column_config.NumberColumn(format="%.2f"),
                    "Net": st.column_config.NumberColumn(format="%.2f"),
                },
            )


def _build_monthly_data(transactions: list) -> tuple[pd.DataFrame, int]:
    rows: list[dict[str, object]] = []
    undated_count = 0
    for transaction in transactions:
        if transaction.transaction_date is None:
            undated_count += 1
            continue
        rows.append(
            {
                "Month": transaction.transaction_date.strftime("%b %Y"),
                "Sort": transaction.transaction_date.strftime("%Y-%m"),
                "Income": transaction.credit or 0.0,
                "Expenses": transaction.debit or 0.0,
            }
        )
    if not rows:
        return pd.DataFrame(columns=["Month", "Income", "Expenses", "Net"]), undated_count

    dataframe = pd.DataFrame(rows)
    grouped = (
        dataframe.groupby(["Sort", "Month"], as_index=False)[["Income", "Expenses"]]
        .sum()
        .sort_values("Sort")
        .drop(columns="Sort")
    )
    grouped["Net"] = grouped["Income"] - grouped["Expenses"]
    return grouped, undated_count
