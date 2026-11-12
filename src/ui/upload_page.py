"""Upload and statement processing page."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from config.settings import MAX_UPLOAD_BYTES
from src.models import StatementAnalysis
from src.pdf_processing.errors import StatementProcessingError
from src.pipeline import StatementProcessingPipeline
from src.ui.components import (
    render_account_strip,
    render_page_header,
    render_privacy_notice,
    render_status_badges,
)
from src.utils.logging_config import get_logger

logger = get_logger("upload_page")


@st.cache_resource(show_spinner=False)
def get_processing_pipeline() -> StatementProcessingPipeline:
    return StatementProcessingPipeline()


def render() -> None:
    render_page_header(
        "Upload statement",
        "Process a text-based or scanned bank statement entirely on this machine.",
        eyebrow="Statement intake",
    )
    render_privacy_notice()

    uploaded_file = st.file_uploader(
        "Choose a PDF bank statement",
        type=["pdf"],
        accept_multiple_files=False,
        help=f"PDF files up to {MAX_UPLOAD_BYTES // (1024 * 1024)} MB are supported.",
    )
    password = st.text_input(
        "PDF password (optional)",
        type="password",
        help="Only required for password-protected statements.",
    )

    upload_valid = uploaded_file is not None
    if uploaded_file is not None and uploaded_file.size > MAX_UPLOAD_BYTES:
        st.error(
            f"This file is {uploaded_file.size / (1024 * 1024):.1f} MB. The maximum "
            f"allowed size is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )
        upload_valid = False

    process_clicked = st.button(
        "Process statement",
        type="primary",
        disabled=not upload_valid,
        use_container_width=False,
    )

    if process_clicked and uploaded_file is not None:
        _process_uploaded_file(uploaded_file, password)

    analysis = st.session_state.get("analysis")
    if analysis:
        st.divider()
        _render_analysis_summary(analysis)
        _render_model_details()


def _process_uploaded_file(uploaded_file, password: str) -> None:
    if not uploaded_file.name.lower().endswith(".pdf"):
        st.error("Please upload a PDF file.")
        return

    temporary_path: str | None = None
    try:
        file_descriptor, temporary_path = tempfile.mkstemp(suffix=".pdf")
        with os.fdopen(file_descriptor, "wb") as temporary_file:
            temporary_file.write(uploaded_file.getbuffer())

        pipeline = get_processing_pipeline()
        with st.status("Processing statement locally...", expanded=True) as status:
            st.write("Detecting the PDF type and extracting text...")
            analysis = pipeline.analyze(
                temporary_path, password=password.strip() or None
            )
            status.update(
                label="Statement processed successfully",
                state="complete",
                expanded=False,
            )

        analysis.source_name = uploaded_file.name
        st.session_state.analysis = analysis
        st.session_state.processing_error = None
        model = pipeline.classification_engine.ml_classifier
        st.session_state.model_metadata = model.metadata if model else None
        st.success("Statement processed. Review the extraction summary below.")
    except StatementProcessingError as exc:
        st.session_state.processing_error = str(exc)
        st.error(str(exc))
    except Exception as exc:
        logger.error("Unexpected upload processing failure: %s", type(exc).__name__)
        st.session_state.processing_error = (
            "An unexpected error occurred while processing the statement."
        )
        st.error(st.session_state.processing_error)
    finally:
        if temporary_path:
            Path(temporary_path).unlink(missing_ok=True)


def _render_analysis_summary(analysis: StatementAnalysis) -> None:
    st.markdown(
        '<div class="ll-section-title">Latest processed statement</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="ll-section-subtitle">{analysis.source_name}</div>',
        unsafe_allow_html=True,
    )
    render_status_badges(analysis)
    st.write("")
    render_account_strip(analysis.account)

    page_col, transaction_col, parser_col, validation_col = st.columns(4)
    page_col.metric("Pages", analysis.pdf_info.page_count)
    transaction_col.metric("Transactions", len(analysis.transactions))
    parser_col.metric("Parser", analysis.parser_name.replace(" layout parser", ""))
    validation_col.metric(
        "Validation issues",
        analysis.validation.error_count + analysis.validation.warning_count,
    )

    st.write("")
    detail_rows = [
        ("PDF type", analysis.pdf_info.kind.value),
        ("Encrypted PDF", "Yes" if analysis.pdf_info.encrypted else "No"),
        ("OCR applied", "Yes" if analysis.used_ocr else "No"),
        ("Parser", analysis.parser_name),
        (
            "Transaction rows",
            f"{len(analysis.transactions):,}",
        ),
        (
            "Rule-classified",
            f"{sum(item.classification_method == 'Rule-based' for item in analysis.transactions):,}",
        ),
        (
            "ML-classified",
            f"{sum(item.classification_method == 'Machine Learning' for item in analysis.transactions):,}",
        ),
        (
            "Needs review",
            f"{sum(item.needs_review for item in analysis.transactions):,}",
        ),
    ]
    with st.expander("Extraction details", expanded=False):
        st.dataframe(
            pd.DataFrame(detail_rows, columns=["Field", "Value"]),
            hide_index=True,
            use_container_width=True,
        )

    if analysis.warnings:
        with st.expander("Processing notes and warnings", expanded=False):
            for warning in analysis.warnings:
                st.markdown(f"- {warning}")

    if analysis.validation.issues:
        with st.expander("Validation report", expanded=analysis.validation.has_errors):
            records = analysis.validation.to_records()
            st.dataframe(
                pd.DataFrame(records),
                hide_index=True,
                use_container_width=True,
            )
    elif not analysis.transactions:
        st.info(
            "No transactions were found. Check that the statement contains a supported "
            "transaction table or verify OCR quality for scanned files."
        )

    if analysis.transactions:
        st.button(
            "Open dashboard",
            on_click=_navigate_to,
            args=("Dashboard",),
            type="primary",
        )


def _render_model_details() -> None:
    metadata = st.session_state.get("model_metadata")
    with st.expander("Classification model information", expanded=False):
        if not metadata:
            st.warning(
                "No trained model metadata is available. Rule-based classification "
                "remains active, but ML predictions may be unavailable."
            )
            return

        st.markdown(
            f"**Selected model:** {metadata.get('model_name', 'Unknown')}  \n"
            f"**Training rows:** {metadata.get('training_rows', 0):,}  \n"
            f"**Holdout rows:** {metadata.get('test_rows', 0):,}  \n"
            f"**Trained at:** {metadata.get('trained_at', 'Unknown')}"
        )
        model_rows = []
        for name, metrics in metadata.get("models", {}).items():
            model_rows.append(
                {
                    "Model": name,
                    "Accuracy": metrics.get("accuracy"),
                    "Precision (macro)": metrics.get("precision_macro"),
                    "Recall (macro)": metrics.get("recall_macro"),
                    "F1 (macro)": metrics.get("f1_macro"),
                }
            )
        if model_rows:
            st.dataframe(
                pd.DataFrame(model_rows),
                hide_index=True,
                use_container_width=True,
            )
        for warning in metadata.get("warnings", []):
            st.warning(warning)
        st.markdown(
            '<div class="ll-note">The model uses TF-IDF features with a traditional '
            "scikit-learn classifier. No external LLM or API is used. Low-confidence "
            "predictions are routed to review instead of being forced into a category.</div>",
            unsafe_allow_html=True,
        )


def _navigate_to(page: str) -> None:
    st.session_state.navigation = page
