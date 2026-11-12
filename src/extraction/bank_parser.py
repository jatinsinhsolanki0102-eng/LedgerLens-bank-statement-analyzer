"""Bank layout detection and parser facade.

The extraction engine accepts a broad set of column headers and line layouts.
Bank-specific additions therefore usually only require registering detection
metadata and any new header aliases used by that bank.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.extraction.account_extractor import detect_bank_name
from src.extraction.transaction_extractor import TransactionExtractionResult, TransactionExtractor
from src.models import AccountInfo


@dataclass(frozen=True, slots=True)
class BankLayout:
    name: str
    detection_patterns: tuple[str, ...]
    notes: str = ""


BANK_LAYOUTS: tuple[BankLayout, ...] = (
    BankLayout("HDFC Bank", (r"\bhdfc\s+bank\b",), "HDFC-style narration and amount columns."),
    BankLayout("ICICI Bank", (r"\bicici\s+bank\b",), "ICICI value-date and remarks layouts."),
    BankLayout(
        "State Bank of India",
        (r"\bstate\s+bank\s+of\s+india\b", r"\bsbi\b"),
        "SBI description, debit, credit, and balance columns.",
    ),
    BankLayout("Axis Bank", (r"\baxis\s+bank\b",), "Axis-style transaction tables."),
    BankLayout(
        "Kotak Mahindra Bank",
        (r"\bkotak\s+(?:mahindra\s+)?bank\b",),
        "Kotak-style transaction tables.",
    ),
    BankLayout(
        "Punjab National Bank",
        (r"\bpunjab\s+national\s+bank\b", r"\bpNB\b"),
        "PNB-style transaction tables.",
    ),
    BankLayout("Bank of Baroda", (r"\bbank\s+of\s+baroda\b",), "Bank of Baroda tables."),
    BankLayout("Canara Bank", (r"\bcanara\s+bank\b",), "Canara Bank tables."),
    BankLayout("Union Bank of India", (r"\bunion\s+bank\s+of\s+india\b",), "Union Bank tables."),
    BankLayout("IndusInd Bank", (r"\bindusind\s+bank\b",), "IndusInd Bank tables."),
    BankLayout("Yes Bank", (r"\byes\s+bank\b",), "Yes Bank tables."),
    BankLayout("IDFC FIRST Bank", (r"\bidfc\s+first\s+bank\b",), "IDFC FIRST tables."),
    BankLayout("Federal Bank", (r"\bfederal\s+bank\b",), "Federal Bank tables."),
)

GENERIC_LAYOUT = BankLayout(
    "Generic",
    (),
    "Fallback parser for uncatalogued layouts using common statement headers.",
)


class BankParser:
    """Facade around the generic transaction extraction engine for one layout."""

    def __init__(
        self,
        layout: BankLayout = GENERIC_LAYOUT,
        extractor: TransactionExtractor | None = None,
    ) -> None:
        self.layout = layout
        self._extractor = extractor or TransactionExtractor()

    @property
    def name(self) -> str:
        if self.layout == GENERIC_LAYOUT:
            return "Generic layout parser"
        return f"{self.layout.name} layout parser"

    def parse(
        self,
        pages: list[str],
        account: AccountInfo | None = None,
        tables: list[list[list[str]]] | None = None,
    ) -> TransactionExtractionResult:
        return self._extractor.extract(pages=pages, account=account, tables=tables)


def get_bank_parser(text: str, bank_name: str | None = None) -> BankParser:
    """Select a layout parser using detected bank metadata, then statement text."""

    if bank_name:
        for layout in BANK_LAYOUTS:
            if layout.name.casefold() == bank_name.casefold():
                return BankParser(layout)

    detected_name = detect_bank_name(text)
    if detected_name:
        for layout in BANK_LAYOUTS:
            if layout.name.casefold() == detected_name.casefold():
                return BankParser(layout)

    for layout in BANK_LAYOUTS:
        if any(re.search(pattern, text or "", flags=re.IGNORECASE) for pattern in layout.detection_patterns):
            return BankParser(layout)

    return BankParser(GENERIC_LAYOUT)
