"""Field-level and duplicate validation for extracted transactions."""

from __future__ import annotations

import re
from datetime import date, timedelta

from config.settings import MAX_VALIDATION_ISSUES
from src.models import IssueSeverity, Transaction, ValidationIssue, ValidationReport


class TransactionValidator:
    """Flag suspicious extraction results without removing source rows."""

    def validate(self, transactions: list[Transaction]) -> ValidationReport:
        report = ValidationReport()
        duplicate_groups: dict[tuple[object, ...], list[int]] = {}

        for index, transaction in enumerate(transactions):
            self._validate_required_fields(index, transaction, report)
            self._validate_amounts(index, transaction, report)
            self._validate_description(index, transaction, report)

            key = self._duplicate_key(transaction)
            duplicate_groups.setdefault(key, []).append(index)

        for indices in duplicate_groups.values():
            if len(indices) < 2:
                continue
            first_index = indices[0]
            for duplicate_index in indices[1:]:
                self._add_issue(
                    report,
                    ValidationIssue(
                        code="POSSIBLE_DUPLICATE",
                        message=(
                            "This transaction has the same date, amount, and description "
                            f"as transaction #{first_index + 1}."
                        ),
                        severity=IssueSeverity.WARNING,
                        transaction_index=duplicate_index,
                    ),
                )
                transactions[duplicate_index].needs_review = True

        if report.error_count:
            report.issues.append(
                ValidationIssue(
                    code="VALIDATION_ERRORS_PRESENT",
                    message=(
                        f"{report.error_count} error(s) were found. Review the affected "
                        "transactions before relying on the totals."
                    ),
                    severity=IssueSeverity.ERROR,
                )
            )
        return report

    def _validate_required_fields(
        self, index: int, transaction: Transaction, report: ValidationReport
    ) -> None:
        if transaction.transaction_date is None:
            self._add_issue(
                report,
                ValidationIssue(
                    code="MISSING_DATE",
                    message="Transaction date could not be parsed.",
                    severity=IssueSeverity.WARNING,
                    transaction_index=index,
                    field_name="date",
                ),
                transaction,
            )
        elif transaction.transaction_date > date.today() + timedelta(days=1):
            self._add_issue(
                report,
                ValidationIssue(
                    code="FUTURE_DATE",
                    message="Transaction date is in the future.",
                    severity=IssueSeverity.WARNING,
                    transaction_index=index,
                    field_name="date",
                ),
                transaction,
            )

        if not transaction.description.strip():
            self._add_issue(
                report,
                ValidationIssue(
                    code="MISSING_DESCRIPTION",
                    message="Transaction description is empty.",
                    severity=IssueSeverity.WARNING,
                    transaction_index=index,
                    field_name="description",
                ),
                transaction,
            )

    def _validate_amounts(
        self, index: int, transaction: Transaction, report: ValidationReport
    ) -> None:
        if transaction.debit is not None and transaction.credit is not None:
            self._add_issue(
                report,
                ValidationIssue(
                    code="DEBIT_AND_CREDIT",
                    message="Both debit and credit amounts are populated.",
                    severity=IssueSeverity.ERROR,
                    transaction_index=index,
                    field_name="amount",
                ),
                transaction,
            )
        elif transaction.debit is None and transaction.credit is None:
            self._add_issue(
                report,
                ValidationIssue(
                    code="MISSING_AMOUNT",
                    message="Neither debit nor credit amount could be extracted.",
                    severity=IssueSeverity.WARNING,
                    transaction_index=index,
                    field_name="amount",
                ),
                transaction,
            )

        for field_name, value in (("debit", transaction.debit), ("credit", transaction.credit)):
            if value is None:
                continue
            if not isinstance(value, (int, float)):
                self._add_issue(
                    report,
                    ValidationIssue(
                        code="INVALID_AMOUNT",
                        message=f"The {field_name} value is not numeric.",
                        severity=IssueSeverity.ERROR,
                        transaction_index=index,
                        field_name=field_name,
                    ),
                    transaction,
                )
            elif value < 0:
                self._add_issue(
                    report,
                    ValidationIssue(
                        code="NEGATIVE_AMOUNT",
                        message=f"The {field_name} value is negative.",
                        severity=IssueSeverity.WARNING,
                        transaction_index=index,
                        field_name=field_name,
                    ),
                    transaction,
                )

    def _validate_description(
        self, index: int, transaction: Transaction, report: ValidationReport
    ) -> None:
        description = transaction.description.strip()
        if not description:
            return
        if re.fullmatch(r"[\d\s./*#-]+", description):
            self._add_issue(
                report,
                ValidationIssue(
                    code="SUSPICIOUS_DESCRIPTION",
                    message="Description contains only numbers or symbols.",
                    severity=IssueSeverity.WARNING,
                    transaction_index=index,
                    field_name="description",
                ),
                transaction,
            )

    def _add_issue(
        self,
        report: ValidationReport,
        issue: ValidationIssue,
        transaction: Transaction | None = None,
    ) -> None:
        if len(report.issues) >= MAX_VALIDATION_ISSUES:
            return
        report.issues.append(issue)
        if transaction is not None:
            transaction.needs_review = True

    @staticmethod
    def _duplicate_key(transaction: Transaction) -> tuple[object, ...]:
        description = re.sub(r"[^a-z0-9]+", "", transaction.description.lower())
        return (
            transaction.transaction_date,
            description,
            round(transaction.debit or 0.0, 2),
            round(transaction.credit or 0.0, 2),
            round(transaction.balance or 0.0, 2),
        )
