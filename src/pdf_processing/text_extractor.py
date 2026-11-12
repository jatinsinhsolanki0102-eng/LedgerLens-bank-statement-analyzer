"""Extract text and optional table data from text-based PDFs."""

from __future__ import annotations

from pathlib import Path

import pdfplumber

from src.pdf_processing.pdf_detector import open_pdf
from src.utils.logging_config import get_logger

logger = get_logger("text_extractor")


def extract_text_pages(path: str | Path, password: str | None = None) -> list[str]:
    """Return text for every page using PyMuPDF's reading order."""

    document = open_pdf(path, password=password)
    pages: list[str] = []
    try:
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            pages.append(page.get_text("text", sort=True).strip())
    finally:
        document.close()
    return pages


def extract_text_with_pdfplumber(path: str | Path, password: str | None = None) -> list[str]:
    """Fallback extraction using pdfplumber, primarily for unusual text layouts."""

    pages: list[str] = []
    try:
        with pdfplumber.open(str(path), password=password or "") as document:
            for page in document.pages:
                pages.append((page.extract_text() or "").strip())
    except Exception as exc:
        logger.warning("pdfplumber fallback failed: %s", type(exc).__name__)
        return []
    return pages


def extract_table_rows(path: str | Path, password: str | None = None) -> list[list[list[str]]]:
    """Extract ruled tables from every page.

    The return value is a list of tables, each table being a list of rows, with
    cells converted to trimmed strings. Missing values remain ``None``.
    """

    tables: list[list[list[str]]] = []
    try:
        with pdfplumber.open(str(path), password=password or "") as document:
            for page in document.pages:
                page_tables = page.extract_tables(
                    table_settings={
                        "vertical_strategy": "lines",
                        "horizontal_strategy": "lines",
                        "snap_tolerance": 3,
                        "join_tolerance": 3,
                        "intersection_tolerance": 3,
                    }
                )
                for table in page_tables or []:
                    cleaned_table = [
                        [
                            (cell or "").strip() if cell is not None else ""
                            for cell in row
                        ]
                        for row in table
                    ]
                    tables.append(cleaned_table)
    except Exception as exc:
        logger.warning("Table extraction skipped: %s", type(exc).__name__)
    return tables
