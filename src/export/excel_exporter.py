"""Excel workbook generation with formatted summary sheets."""

from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO
from typing import Any

import pandas as pd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.worksheet import Worksheet

from config.category_rules import CATEGORIES
from src.extraction.account_extractor import AccountExtractor
from src.models import StatementAnalysis

_HEADER_FILL = PatternFill("solid", fgColor="17324D")
_HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
_SUBHEADER_FILL = PatternFill("solid", fgColor="E8F0F7")
_BORDER = Border(
    left=Side(style="thin", color="D8E1E8"),
    right=Side(style="thin", color="D8E1E8"),
    top=Side(style="thin", color="D8E1E8"),
    bottom=Side(style="thin", color="D8E1E8"),
)

_TRANSACTION_COLUMNS = (
    "Date",
    "Description",
    "Debit",
    "Credit",
    "Balance",
    "Category",
    "Classification Method",
    "Confidence",
    "Needs Review",
    "Source Page",
    "Raw Text",
)


def sanitize_spreadsheet_text(value: Any) -> Any:
    """Prevent spreadsheet formula injection in user-controlled text fields."""

    if not isinstance(value, str):
        return value
    if value.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def _redact_account_number(value: Any, account_number: str | None) -> Any:
    """Replace occurrences of a full account number with its masked form."""

    if not isinstance(value, str) or not account_number:
        return value
    spaced_digits = r"[\s-]*".join(re.escape(char) for char in account_number)
    return re.sub(
        spaced_digits,
        AccountExtractor.mask_account_number(account_number),
        value,
        flags=re.IGNORECASE,
    )


def mask_frame_account_numbers(
    dataframe: pd.DataFrame, account_number: str | None
) -> pd.DataFrame:
    """Return a copy with full account-number occurrences redacted in every cell."""

    if not account_number:
        return dataframe.copy()
    masked = dataframe.copy()
    for column in masked.columns:
        masked[column] = masked[column].map(
            lambda value: _redact_account_number(value, account_number)
        )
    return masked


def build_transactions_frame(
    analysis: StatementAnalysis, include_full_account_number: bool = False
) -> pd.DataFrame:
    """Create the canonical transaction export frame."""

    rows = [transaction.to_export_dict() for transaction in analysis.transactions]
    dataframe = pd.DataFrame(rows, columns=_TRANSACTION_COLUMNS)
    if not include_full_account_number:
        for column in ("Description", "Raw Text"):
            dataframe[column] = dataframe[column].map(
                lambda value: _redact_account_number(
                    value, analysis.account.account_number
                )
            )
    for column in ("Description", "Category", "Classification Method", "Raw Text"):
        dataframe[column] = dataframe[column].map(sanitize_spreadsheet_text)
    return dataframe


def build_account_summary_frame(
    analysis: StatementAnalysis, include_full_account_number: bool = False
) -> pd.DataFrame:
    """Create a key/value account information sheet."""

    account = analysis.account
    account_number = (
        account.account_number
        if include_full_account_number
        else AccountExtractor.mask_account_number(account.account_number)
    )
    rows = [
        ("Account Holder", account.account_holder_name or "Not available"),
        ("Account Number", account_number),
        ("IFSC Code", account.ifsc_code or "Not available"),
        ("Bank Name", account.bank_name or "Not available"),
        ("Statement Period", account.statement_period_label or "Not available"),
        ("Opening Balance", account.opening_balance),
        ("Closing Balance", account.closing_balance),
        ("Currency", account.currency),
        ("Detected PDF Type", analysis.pdf_info.kind.value),
        ("Pages", analysis.pdf_info.page_count),
        ("OCR Used", "Yes" if analysis.used_ocr else "No"),
        ("Parser", analysis.parser_name),
        ("Transactions", len(analysis.transactions)),
        ("Validation Errors", analysis.validation.error_count),
        ("Validation Warnings", analysis.validation.warning_count),
        ("Source File", analysis.source_name),
        ("Generated At", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    ]
    dataframe = pd.DataFrame(rows, columns=["Field", "Value"])
    dataframe["Field"] = dataframe["Field"].map(sanitize_spreadsheet_text)
    dataframe["Value"] = dataframe["Value"].map(sanitize_spreadsheet_text)
    return dataframe


def build_category_summary_frame(analysis: StatementAnalysis) -> pd.DataFrame:
    """Aggregate transaction count, debits, credits, and net by category."""

    if not analysis.transactions:
        return pd.DataFrame(
            columns=["Category", "Transactions", "Total Debit", "Total Credit", "Net"]
        )

    rows = [
        {
            "Category": transaction.category,
            "Debit": transaction.debit or 0.0,
            "Credit": transaction.credit or 0.0,
        }
        for transaction in analysis.transactions
    ]
    dataframe = pd.DataFrame(rows)
    grouped = (
        dataframe.groupby("Category", dropna=False)
        .agg(
            Transactions=("Category", "size"),
            **{
                "Total Debit": ("Debit", "sum"),
                "Total Credit": ("Credit", "sum"),
            },
        )
        .reset_index()
    )
    grouped["Net"] = grouped["Total Credit"] - grouped["Total Debit"]
    order = {category: index for index, category in enumerate(CATEGORIES)}
    grouped["_order"] = grouped["Category"].map(order).fillna(len(CATEGORIES))
    grouped = grouped.sort_values(["_order", "Category"]).drop(columns="_order")
    return grouped


def build_validation_frame(analysis: StatementAnalysis) -> pd.DataFrame:
    """Create a validation issue table for export."""

    records = analysis.validation.to_records()
    if not records:
        records = [
            {
                "Severity": "Info",
                "Code": "NO_ISSUES",
                "Transaction #": "",
                "Field": "",
                "Message": "No validation issues detected.",
            }
        ]
    return pd.DataFrame(records)


def build_excel_workbook_bytes(
    analysis: StatementAnalysis, include_full_account_number: bool = False
) -> bytes:
    """Build a multi-sheet Excel workbook and return it as bytes."""

    output = BytesIO()
    transactions = build_transactions_frame(
        analysis, include_full_account_number=include_full_account_number
    )
    account_summary = build_account_summary_frame(
        analysis, include_full_account_number=include_full_account_number
    )
    category_summary = build_category_summary_frame(analysis)
    validation_report = build_validation_frame(analysis)

    frames = {
        "Transactions": transactions,
        "Account Summary": account_summary,
        "Category Summary": category_summary,
        "Validation Report": validation_report,
    }
    if not include_full_account_number:
        frames = {
            name: mask_frame_account_numbers(
                dataframe, analysis.account.account_number
            )
            for name, dataframe in frames.items()
        }

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frames["Transactions"].to_excel(
            writer, sheet_name="Transactions", index=False
        )
        frames["Account Summary"].to_excel(
            writer, sheet_name="Account Summary", index=False
        )
        frames["Category Summary"].to_excel(
            writer, sheet_name="Category Summary", index=False
        )
        frames["Validation Report"].to_excel(
            writer, sheet_name="Validation Report", index=False
        )

        workbook = writer.book
        _format_transaction_sheet(workbook["Transactions"])
        _format_summary_sheet(workbook["Account Summary"])
        _format_category_sheet(workbook["Category Summary"])
        _format_validation_sheet(workbook["Validation Report"])

    output.seek(0)
    return output.getvalue()


def _style_header_row(worksheet: Worksheet, row_number: int = 1) -> None:
    for cell in worksheet[row_number]:
        if cell.value is None:
            continue
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = _BORDER
    worksheet.row_dimensions[row_number].height = 24


def _format_transaction_sheet(worksheet: Worksheet) -> None:
    _style_header_row(worksheet)
    worksheet.freeze_panes = "A2"
    if worksheet.max_row > 1:
        worksheet.auto_filter.ref = worksheet.dimensions

    widths = {
        "A": 13,
        "B": 46,
        "C": 14,
        "D": 14,
        "E": 15,
        "F": 22,
        "G": 21,
        "H": 12,
        "I": 13,
        "J": 12,
        "K": 50,
    }
    for column_letter, width in widths.items():
        worksheet.column_dimensions[column_letter].width = width

    for row in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row):
        for cell in row:
            cell.border = _BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=cell.column_letter in {"B", "K"})
        row[0].number_format = "dd-mmm-yyyy"
        for cell in row[2:5]:
            cell.number_format = "#,##0.00"
        row[7].number_format = "0%"


def _format_summary_sheet(worksheet: Worksheet) -> None:
    _style_header_row(worksheet)
    worksheet.freeze_panes = "A2"
    worksheet.column_dimensions["A"].width = 26
    worksheet.column_dimensions["B"].width = 44
    for row in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row):
        row[0].font = Font(bold=True, color="17324D")
        row[0].fill = _SUBHEADER_FILL
        for cell in row:
            cell.border = _BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=True)


def _format_category_sheet(worksheet: Worksheet) -> None:
    _style_header_row(worksheet)
    worksheet.freeze_panes = "A2"
    worksheet.column_dimensions["A"].width = 28
    for column_letter in ("B", "C", "D", "E"):
        worksheet.column_dimensions[column_letter].width = 16
    for row in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row):
        for cell in row:
            cell.border = _BORDER
            cell.alignment = Alignment(vertical="top")
        for cell in row[1:]:
            cell.number_format = "#,##0.00" if cell.column_letter != "B" else "0"


def _format_validation_sheet(worksheet: Worksheet) -> None:
    _style_header_row(worksheet)
    worksheet.freeze_panes = "A2"
    widths = {"A": 12, "B": 28, "C": 14, "D": 18, "E": 80}
    for column_letter, width in widths.items():
        worksheet.column_dimensions[column_letter].width = width
    for row in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row):
        for cell in row:
            cell.border = _BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=cell.column_letter == "E")
        severity = str(row[0].value or "")
        if severity == "Error":
            row[0].font = Font(color="B42318", bold=True)
        elif severity == "Warning":
            row[0].font = Font(color="B54708", bold=True)
        elif severity == "Info":
            row[0].font = Font(color="175CD3")
