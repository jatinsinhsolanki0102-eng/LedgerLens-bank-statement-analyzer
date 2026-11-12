"""LedgerLens Streamlit application entry point."""

from __future__ import annotations

import html

import streamlit as st

from config.settings import APP_SUBTITLE, APP_TITLE
from src.ui import (
    analytics_page,
    dashboard_page,
    export_page,
    transactions_page,
    upload_page,
)
from src.ui.styles import inject_global_styles

PAGES = {
    "Dashboard": dashboard_page.render,
    "Upload Statement": upload_page.render,
    "Transactions": transactions_page.render,
    "Analytics": analytics_page.render,
    "Export": export_page.render,
}


def _initialise_state() -> None:
    if "navigation" not in st.session_state:
        st.session_state.navigation = "Dashboard"
    if "analysis" not in st.session_state:
        st.session_state.analysis = None
    if "model_metadata" not in st.session_state:
        st.session_state.model_metadata = None
    if "transaction_page" not in st.session_state:
        st.session_state.transaction_page = 1
    if "transaction_revision" not in st.session_state:
        st.session_state.transaction_revision = 0


def _render_sidebar() -> str:
    st.sidebar.markdown(
        f"""
        <div class="ll-brand">
            <div class="ll-brand-mark">LL</div>
            <div>
                <div class="ll-brand-name">{html.escape(APP_TITLE)}</div>
                <div class="ll-brand-sub">{html.escape(APP_SUBTITLE)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    selected_page = st.sidebar.radio(
        "Navigation",
        options=list(PAGES),
        key="navigation",
        label_visibility="collapsed",
    )
    st.sidebar.divider()

    analysis = st.session_state.get("analysis")
    if analysis:
        review_count = sum(
            transaction.needs_review for transaction in analysis.transactions
        )
        st.sidebar.markdown(
            '<div class="ll-sidebar-status">'
            "<strong>Statement loaded</strong><br>"
            f"{len(analysis.transactions):,} transactions · "
            f"{review_count:,} need review<br>"
            f"{html.escape(analysis.pdf_info.kind.value)} PDF"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.markdown(
            '<div class="ll-sidebar-status">'
            "<strong>No statement loaded</strong><br>"
            "Start with Upload Statement to process a PDF."
            "</div>",
            unsafe_allow_html=True,
        )

    st.sidebar.markdown(
        '<div class="ll-sidebar-status">'
        "<strong>Local by design</strong><br>"
        "Statements stay on this machine. No external AI or financial APIs are used."
        "</div>",
        unsafe_allow_html=True,
    )
    return selected_page


def _reset_secure_export_for_navigation(selected_page: str) -> None:
    if st.session_state.get("_last_navigation") != selected_page:
        st.session_state["secure_export_opt_in"] = False
        st.session_state["_last_navigation"] = selected_page


def main() -> None:
    st.set_page_config(
        page_title=f"{APP_TITLE} | {APP_SUBTITLE}",
        page_icon="₹",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_global_styles()
    _initialise_state()
    selected_page = _render_sidebar()
    _reset_secure_export_for_navigation(selected_page)
    PAGES[selected_page]()


if __name__ == "__main__":
    main()
