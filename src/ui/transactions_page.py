"""Interactive transaction explorer with manual category correction."""

from __future__ import annotations

import math
from datetime import date

import pandas as pd
import streamlit as st

from config.category_rules import CATEGORIES
from src.models import StatementAnalysis
from src.ui.components import (
    apply_manual_category,
    build_transaction_dataframe,
    make_data_editor_config,
    render_empty_state,
    render_page_header,
    transaction_date_range,
)


def render() -> None:
    analysis = st.session_state.get("analysis")
    if not analysis:
        render_page_header(
            "Transactions",
            "Search, filter, review, and correct transaction categories.",
            eyebrow="Transaction explorer",
        )
        render_empty_state(
            "No transactions to display",
            "Upload a statement first. Extracted transactions will appear here with "
            "their category, classification method, and confidence score.",
        )
        return

    render_page_header(
        "Transactions",
        "Search, filter, review, and correct transaction categories.",
        eyebrow="Transaction explorer",
        meta_label="rows extracted",
        meta_value=f"{len(analysis.transactions):,}",
    )

    flash_message = st.session_state.pop("transaction_flash", None)
    if flash_message:
        st.success(flash_message)

    if not analysis.transactions:
        st.info("No transaction rows were extracted from this statement.")
        return

    dataframe = build_transaction_dataframe(analysis.transactions)
    filtered = _apply_filters(dataframe, analysis)
    if filtered.empty:
        st.info("No transactions match the current filters.")
        return

    filtered = _apply_sorting(filtered)

    result_col, review_col, method_col = st.columns(3)
    result_col.metric("Matching rows", f"{len(filtered):,}")
    review_col.metric(
        "Needs review",
        f"{sum(filtered['Review'] == 'Needs review'):,}",
    )
    method_col.metric(
        "Manual corrections",
        f"{sum(filtered['Method'] == 'Manual'):,}",
    )

    rows_per_page = st.selectbox(
        "Rows per page",
        options=(25, 50, 100, 250),
        index=1,
        key="transaction_page_size",
    )
    page_count = max(1, math.ceil(len(filtered) / rows_per_page))
    current_page = int(st.session_state.get("transaction_page", 1))
    current_page = min(max(current_page, 1), page_count)
    st.session_state.transaction_page = current_page
    start = (current_page - 1) * rows_per_page
    end = min(start + rows_per_page, len(filtered))
    page_data = filtered.iloc[start:end].copy()

    st.caption(f"Showing rows {start + 1:,}–{end:,} of {len(filtered):,}.")
    _render_pagination(current_page, page_count)

    revision = int(st.session_state.get("transaction_revision", 0))
    editor_key = f"transaction_editor_{current_page}_{revision}_{'-'.join(map(str, page_data['ID'].tolist()))}"
    edited = st.data_editor(
        page_data,
        column_config=make_data_editor_config(),
        disabled=[
            "ID",
            "Date",
            "Description",
            "Debit",
            "Credit",
            "Balance",
            "Method",
            "Confidence",
            "Review",
        ],
        hide_index=True,
        use_container_width=True,
        height=min(680, 42 + 35 * len(page_data)),
        key=editor_key,
    )
    st.markdown(
        '<div class="ll-note">Edit the Category column directly, then choose '
        "Apply category corrections. Manual changes are marked as reviewed.</div>",
        unsafe_allow_html=True,
    )

    if st.button("Apply category corrections", type="primary"):
        corrections = _apply_category_edits(analysis, page_data, edited)
        if corrections:
            st.session_state.transaction_flash = (
                f"Applied {corrections} manual category correction(s)."
            )
            st.session_state.transaction_revision = revision + 1
            st.rerun()
        else:
            st.info("No category changes were found.")


def _apply_filters(dataframe: pd.DataFrame, analysis: StatementAnalysis) -> pd.DataFrame:
    st.markdown(
        '<div class="ll-section-title">Filter transactions</div>',
        unsafe_allow_html=True,
    )
    search_column, category_column, method_column = st.columns([2, 1.4, 1.2])
    search_text = search_column.text_input(
        "Search",
        placeholder="Merchant, description, or category",
        key="transaction_search",
    )
    present_categories = [
        category for category in CATEGORIES if category in set(dataframe["Category"])
    ]
    selected_categories = category_column.multiselect(
        "Categories",
        options=present_categories,
        key="transaction_categories",
    )
    present_methods = sorted(dataframe["Method"].dropna().unique().tolist())
    selected_methods = method_column.multiselect(
        "Classification method",
        options=present_methods,
        key="transaction_methods",
    )

    minimum_date, maximum_date = transaction_date_range(analysis.transactions)
    if minimum_date and maximum_date:
        date_column, undated_column = st.columns([2, 1])
        date_range = date_column.date_input(
            "Date range",
            value=(minimum_date, maximum_date),
            min_value=minimum_date,
            max_value=maximum_date,
            key="transaction_date_range",
        )
        include_undated = undated_column.checkbox(
            "Include rows without a date",
            value=True,
            key="transaction_include_undated",
        )
    else:
        date_range = ()
        include_undated = True

    mask = pd.Series(True, index=dataframe.index)
    if search_text:
        searchable = (
            dataframe["Description"].fillna("")
            + " "
            + dataframe["Category"].fillna("")
            + " "
            + dataframe["Method"].fillna("")
        )
        mask &= searchable.str.contains(search_text, case=False, na=False)
    if selected_categories:
        mask &= dataframe["Category"].isin(selected_categories)
    if selected_methods:
        mask &= dataframe["Method"].isin(selected_methods)

    start_date: date | None = None
    end_date: date | None = None
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    elif isinstance(date_range, date):
        start_date = end_date = date_range

    if start_date and end_date:
        dated_mask = dataframe["Date"].apply(
            lambda value: (
                value is not None
                and not pd.isna(value)
                and start_date <= value <= end_date
            )
        )
        if include_undated:
            dated_mask |= dataframe["Date"].isna()
        mask &= dated_mask

    return dataframe[mask].copy()


def _apply_sorting(dataframe: pd.DataFrame) -> pd.DataFrame:
    sort_column, direction_column = st.columns([1, 1])
    sort_option = sort_column.selectbox(
        "Sort by",
        options=(
            "Source order",
            "Date",
            "Debit",
            "Credit",
            "Balance",
            "Category",
            "Confidence",
        ),
        key="transaction_sort_column",
    )
    direction = direction_column.selectbox(
        "Direction",
        options=("Ascending", "Descending"),
        key="transaction_sort_direction",
    )
    if sort_option == "Source order":
        return dataframe
    return dataframe.sort_values(
        sort_option,
        ascending=direction == "Ascending",
        na_position="last",
        kind="stable",
    )


def _render_pagination(current_page: int, page_count: int) -> None:
    previous_column, status_column, next_column = st.columns([1, 2, 1])
    previous_column.button(
        "Previous page",
        disabled=current_page <= 1,
        on_click=_change_page,
        args=(-1, page_count),
        use_container_width=True,
    )
    status_column.markdown(
        f'<div style="text-align:center;color:#627D98;padding-top:0.55rem;">'
        f"Page {current_page} of {page_count}</div>",
        unsafe_allow_html=True,
    )
    next_column.button(
        "Next page",
        disabled=current_page >= page_count,
        on_click=_change_page,
        args=(1, page_count),
        use_container_width=True,
    )


def _change_page(delta: int, page_count: int) -> None:
    current_page = int(st.session_state.get("transaction_page", 1))
    st.session_state.transaction_page = min(max(current_page + delta, 1), page_count)


def _apply_category_edits(
    analysis: StatementAnalysis,
    original_page: pd.DataFrame,
    edited_page: pd.DataFrame,
) -> int:
    original_categories = dict(zip(original_page["ID"], original_page["Category"]))
    corrections = 0
    for row in edited_page.itertuples(index=False):
        transaction_id = int(row.ID)
        new_category = row.Category
        if new_category not in CATEGORIES:
            continue
        if original_categories.get(transaction_id) == new_category:
            continue
        transaction = analysis.transactions[transaction_id - 1]
        apply_manual_category(transaction, new_category)
        corrections += 1
    return corrections
