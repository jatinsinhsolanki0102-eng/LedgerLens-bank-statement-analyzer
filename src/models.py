"""Shared domain models used by extraction, classification, validation, and UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any

from config.category_rules import OTHER_CATEGORY


class PDFKind(str, Enum):
    TEXT = "Text-based"
    SCANNED = "Scanned"
    MIXED = "Mixed"
    EMPTY = "Empty"


@dataclass(slots=True)
class PDFInfo:
    page_count: int
    kind: PDFKind
    encrypted: bool
    text_page_numbers: list[int] = field(default_factory=list)
    image_page_numbers: list[int] = field(default_factory=list)
    file_size_bytes: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AccountInfo:
    account_holder_name: str | None = None
    account_number: str | None = None
    ifsc_code: str | None = None
    bank_name: str | None = None
    statement_period_start: date | None = None
    statement_period_end: date | None = None
    opening_balance: float | None = None
    closing_balance: float | None = None
    currency: str = "INR"

    @property
    def statement_period_label(self) -> str | None:
        if self.statement_period_start and self.statement_period_end:
            return (
                f"{self.statement_period_start:%d %b %Y} – "
                f"{self.statement_period_end:%d %b %Y}"
            )
        if self.statement_period_start:
            return f"From {self.statement_period_start:%d %b %Y}"
        if self.statement_period_end:
            return f"Until {self.statement_period_end:%d %b %Y}"
        return None


@dataclass(slots=True)
class Transaction:
    transaction_date: date | None
    description: str
    debit: float | None = None
    credit: float | None = None
    balance: float | None = None
    category: str = OTHER_CATEGORY
    classification_method: str = "unclassified"
    confidence_score: float | None = None
    source_page: int | None = None
    raw_text: str = ""
    needs_review: bool = False

    @property
    def amount(self) -> float | None:
        if self.debit is not None and self.debit > 0:
            return self.debit
        if self.credit is not None and self.credit > 0:
            return self.credit
        return None

    @property
    def direction(self) -> str | None:
        if self.debit is not None and self.debit > 0:
            return "debit"
        if self.credit is not None and self.credit > 0:
            return "credit"
        return None

    def to_export_dict(self) -> dict[str, Any]:
        return {
            "Date": self.transaction_date.isoformat() if self.transaction_date else "",
            "Description": self.description,
            "Debit": self.debit,
            "Credit": self.credit,
            "Balance": self.balance,
            "Category": self.category,
            "Classification Method": self.classification_method,
            "Confidence": self.confidence_score,
            "Needs Review": "Yes" if self.needs_review else "No",
            "Source Page": self.source_page,
            "Raw Text": self.raw_text,
        }


class IssueSeverity(str, Enum):
    ERROR = "Error"
    WARNING = "Warning"
    INFO = "Info"


@dataclass(slots=True)
class ValidationIssue:
    code: str
    message: str
    severity: IssueSeverity = IssueSeverity.WARNING
    transaction_index: int | None = None
    field_name: str | None = None


@dataclass(slots=True)
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(issue.severity == IssueSeverity.ERROR for issue in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(issue.severity == IssueSeverity.WARNING for issue in self.issues)

    @property
    def info_count(self) -> int:
        return sum(issue.severity == IssueSeverity.INFO for issue in self.issues)

    @property
    def has_errors(self) -> bool:
        return self.error_count > 0

    def to_records(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for issue in self.issues:
            rows.append(
                {
                    "Severity": issue.severity.value,
                    "Code": issue.code,
                    "Transaction #": (
                        issue.transaction_index + 1
                        if issue.transaction_index is not None
                        else ""
                    ),
                    "Field": issue.field_name or "",
                    "Message": issue.message,
                }
            )
        return rows

    def extend(self, other: "ValidationReport") -> None:
        self.issues.extend(other.issues)


@dataclass(slots=True)
class StatementAnalysis:
    source_name: str
    pdf_info: PDFInfo
    account: AccountInfo
    transactions: list[Transaction]
    validation: ValidationReport
    parser_name: str
    warnings: list[str] = field(default_factory=list)
    used_ocr: bool = False
