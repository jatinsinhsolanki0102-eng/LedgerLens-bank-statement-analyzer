"""CSV export for processed transactions."""

from __future__ import annotations

from src.export.excel_exporter import build_transactions_frame, mask_frame_account_numbers
from src.models import StatementAnalysis


def build_csv_bytes(
    analysis: StatementAnalysis, include_full_account_number: bool = False
) -> bytes:
    """Return a UTF-8 (with BOM) CSV suitable for spreadsheet applications."""

    dataframe = build_transactions_frame(
        analysis, include_full_account_number=include_full_account_number
    )
    if not include_full_account_number:
        dataframe = mask_frame_account_numbers(
            dataframe, analysis.account.account_number
        )
    return dataframe.to_csv(index=False, lineterminator="\n").encode("utf-8-sig")
