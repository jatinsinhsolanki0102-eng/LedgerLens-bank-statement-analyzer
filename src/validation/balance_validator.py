"""Running-balance consistency checks with order-aware expectations."""

from __future__ import annotations

from config.settings import BALANCE_TOLERANCE, MAX_VALIDATION_ISSUES
from src.models import (
    AccountInfo,
    IssueSeverity,
    Transaction,
    ValidationIssue,
    ValidationReport,
)
from src.utils.amount_utils import amounts_equal
from src.utils.date_utils import detect_statement_order


class BalanceValidator:
    """Check transaction amounts against observed balance movement."""

    def validate(
        self, transactions: list[Transaction], account: AccountInfo | None = None
    ) -> ValidationReport:
        report = ValidationReport()
        if not transactions:
            return report

        order = detect_statement_order(
            [transaction.transaction_date for transaction in transactions]
        )
        indexed_transactions = list(enumerate(transactions))
        if order == "descending":
            indexed_transactions.reverse()

        compared_pairs = 0
        mismatches = 0
        previous_balance = account.opening_balance if account else None

        for original_index, transaction in indexed_transactions:
            has_single_amount = (transaction.debit is not None) != (
                transaction.credit is not None
            )
            if transaction.balance is None or not has_single_amount:
                if transaction.balance is not None:
                    previous_balance = transaction.balance
                continue

            net_change = (transaction.credit or 0.0) - (transaction.debit or 0.0)
            if previous_balance is not None:
                expected = previous_balance + net_change
                compared_pairs += 1
                if not amounts_equal(expected, transaction.balance, BALANCE_TOLERANCE):
                    mismatches += 1
                    if len(report.issues) < MAX_VALIDATION_ISSUES:
                        report.issues.append(
                            ValidationIssue(
                                code="BALANCE_MISMATCH",
                                message=(
                                    f"Expected balance {expected:,.2f} but found "
                                    f"{transaction.balance:,.2f}. A row may be missing "
                                    "or the bank may use a different balance convention."
                                ),
                                severity=IssueSeverity.WARNING,
                                transaction_index=original_index,
                                field_name="balance",
                            )
                        )
                    transaction.needs_review = True

            previous_balance = transaction.balance

        if (
            account
            and account.closing_balance is not None
            and previous_balance is not None
            and not amounts_equal(
                account.closing_balance, previous_balance, BALANCE_TOLERANCE
            )
        ):
            report.issues.append(
                ValidationIssue(
                    code="CLOSING_BALANCE_MISMATCH",
                    message=(
                        "Statement closing balance does not match the newest extracted "
                        "transaction balance."
                    ),
                    severity=IssueSeverity.WARNING,
                    field_name="closing_balance",
                )
            )

        if compared_pairs and not mismatches:
            report.issues.append(
                ValidationIssue(
                    code="BALANCE_SEQUENCE_OK",
                    message=(
                        f"Running balance was consistent across {compared_pairs} "
                        "checked transaction pair(s)."
                    ),
                    severity=IssueSeverity.INFO,
                )
            )
        elif not any(transaction.balance is not None for transaction in transactions):
            report.issues.append(
                ValidationIssue(
                    code="NO_BALANCE_DATA",
                    message="No running balance values were available for validation.",
                    severity=IssueSeverity.INFO,
                )
            )
        return report


