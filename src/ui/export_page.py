"""Download centre for Excel and CSV deliverables."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from src.export import (
    build_account_summary_frame,
    build_category_summary_frame,
    build_csv_bytes,
    build_excel_workbook_bytes,
    build_transactions_frame,
    build_validation_frame,
)
from src.ui.components import (
    format_inr,
    render_empty_state,
    render_page_header,
    sanitize_filename,
)

_SECURE_EXPORT_KEY = "secure_export_opt_in"
_SECURE_EXPORT_ANALYSIS_KEY = "_secure_export_analysis_id"


def _reset_secure_export() -> None:
    st.session_state[_SECURE_EXPORT_KEY] = False


def _reset_secure_export_for_new_analysis(analysis: object) -> None:
    analysis_id = id(analysis)
    if st.session_state.get(_SECURE_EXPORT_ANALYSIS_KEY) != analysis_id:
        st.session_state[_SECURE_EXPORT_KEY] = False
        st.session_state[_SECURE_EXPORT_ANALYSIS_KEY] = analysis_id


def render() -> None:
    analysis = st.session_state.get("analysis")
    if not analysis:
        render_page_header(
            "Export",
            "Download a formatted workbook or a portable CSV of the processed results.",
            eyebrow="Deliverables",
        )
        render_empty_state(
            "Nothing to export yet",
            "Process a statement first. Excel and CSV downloads will include "
            "transactions, account details, category summaries, and validation notes.",
        )
        return

    render_page_header(
        "Export",
        "Download a formatted workbook or a portable CSV of the processed results.",
        eyebrow="Deliverables",
        meta_label="transactions",
        meta_value=f"{len(analysis.transactions):,}",
    )
    _reset_secure_export_for_new_analysis(analysis)
    st.warning(
        "Exported files contain sensitive financial information. Account numbers "
        "are masked by default. Store and share files only through approved channels."
    )
    include_full_account_number = st.checkbox(
        "Enable sensitive full-account-number export",
        key=_SECURE_EXPORT_KEY,
        help=(
            "Normal downloads always remain masked. Enable this only to reveal an "
            "additional secure download button for the current statement."
        ),
    )
    if include_full_account_number:
        st.error(
            "Sensitive export enabled. The additional buttons below will include the "
            "full account number. This permission clears after any download or when "
            "you switch statements or pages."
        )

    transactions_frame = build_transactions_frame(analysis)
    category_frame = build_category_summary_frame(analysis)
    validation_frame = build_validation_frame(analysis)
    account_frame = build_account_summary_frame(analysis)

    gross_debits = sum(transaction.debit or 0.0 for transaction in analysis.transactions)
    gross_credits = sum(transaction.credit or 0.0 for transaction in analysis.transactions)
    row_count, category_count, issue_count, credit_total = st.columns(4)
    row_count.metric("Transactions", f"{len(transactions_frame):,}")
    category_count.metric("Categories", f"{len(category_frame):,}")
    issue_count.metric(
        "Validation issues",
        analysis.validation.error_count + analysis.validation.warning_count,
    )
    credit_total.metric("Gross credits", format_inr(gross_credits))

    st.write("")
    base_name = sanitize_filename(Path(analysis.source_name).stem or "bank_statement")
    excel_bytes = build_excel_workbook_bytes(analysis)
    csv_bytes = build_csv_bytes(analysis)

    excel_column, csv_column = st.columns(2)
    with excel_column:
        st.markdown(
            '<div class="ll-card">'
            '<div class="ll-section-title">Excel workbook</div>'
            '<div class="ll-section-subtitle">Transactions, Account Summary, '
            "Category Summary, and Validation Report sheets.</div>"
            f'<div class="ll-formula">Gross debits: {format_inr(gross_debits)} • '
            f"File size: {len(excel_bytes) / 1024:.1f} KB</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.write("")
        st.download_button(
            "Download Excel (.xlsx)",
            data=excel_bytes,
            file_name=f"{base_name}_analysis.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
            on_click=_reset_secure_export,
        )
    with csv_column:
        st.markdown(
            '<div class="ll-card">'
            '<div class="ll-section-title">CSV transactions</div>'
            '<div class="ll-section-subtitle">UTF-8 CSV with all transaction fields '
            "and classification metadata.</div>"
            f'<div class="ll-formula">Rows: {len(transactions_frame):,} • '
            f"File size: {len(csv_bytes) / 1024:.1f} KB</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.write("")
        st.download_button(
            "Download CSV (.csv)",
            data=csv_bytes,
            file_name=f"{base_name}_transactions.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True,
            on_click=_reset_secure_export,
        )

    if include_full_account_number:
        st.divider()
        secure_excel_bytes = build_excel_workbook_bytes(
            analysis, include_full_account_number=True
        )
        secure_csv_bytes = build_csv_bytes(
            analysis, include_full_account_number=True
        )
        st.error(
            "These files contain the full account number. They are generated only "
            "for this explicit opt-in and are never used by the normal downloads."
        )
        secure_excel_column, secure_csv_column = st.columns(2)
        with secure_excel_column:
            st.download_button(
                "Download Excel with full account number",
                data=secure_excel_bytes,
                file_name=f"{base_name}_analysis_full_account.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                on_click=_reset_secure_export,
            )
        with secure_csv_column:
            st.download_button(
                "Download CSV with full account number",
                data=secure_csv_bytes,
                file_name=f"{base_name}_transactions_full_account.csv",
                mime="text/csv",
                use_container_width=True,
                on_click=_reset_secure_export,
            )
        st.caption(
            "This permission is cleared after any download and when the statement "
            "or page changes."
        )

    st.write("")
    preview_tabs = st.tabs(
        ["Category summary", "Account summary", "Validation report", "Transaction preview"]
    )
    with preview_tabs[0]:
        st.dataframe(
            category_frame,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Total Debit": st.column_config.NumberColumn(format="%.2f"),
                "Total Credit": st.column_config.NumberColumn(format="%.2f"),
                "Net": st.column_config.NumberColumn(format="%.2f"),
            },
        )
    with preview_tabs[1]:
        account_preview = account_frame.copy()
        account_preview["Value"] = account_preview["Value"].astype(str)
        st.dataframe(account_preview, hide_index=True, use_container_width=True)
    with preview_tabs[2]:
        validation_preview = validation_frame.copy()
        if "Transaction #" in validation_preview.columns:
            validation_preview["Transaction #"] = validation_preview[
                "Transaction #"
            ].astype(str)
        st.dataframe(validation_preview, hide_index=True, use_container_width=True)
    with preview_tabs[3]:
        st.dataframe(
            transactions_frame.head(50),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Debit": st.column_config.NumberColumn(format="%.2f"),
                "Credit": st.column_config.NumberColumn(format="%.2f"),
                "Balance": st.column_config.NumberColumn(format="%.2f"),
                "Confidence": st.column_config.NumberColumn(format="%.2f"),
            },
        )
        if len(transactions_frame) > 50:
            st.caption("Preview shows the first 50 rows. The download contains all rows.")
