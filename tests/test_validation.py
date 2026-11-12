"""Transaction field, duplicate, and running-balance validation tests."""

from __future__ import annotations

from datetime import date, timedelta

from src.models import AccountInfo, IssueSeverity, Transaction
from src.validation.balance_validator import BalanceValidator
from src.validation.transaction_validator import TransactionValidator


def _codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


def test_valid_transaction_has_no_issues() -> None:
    transaction = Transaction(
        transaction_date=date(2024, 4, 1),
        description="SALARY CREDIT ACME CORP",
        credit=85000.0,
        balance=210000.0,
    )

    report = TransactionValidator().validate([transaction])

    assert report.error_count == 0
    assert report.warning_count == 0
    assert transaction.needs_review is False


def test_missing_date_and_amount_are_flagged() -> None:
    transaction = Transaction(transaction_date=None, description="UNKNOWN")
    report = TransactionValidator().validate([transaction])

    assert {"MISSING_DATE", "MISSING_AMOUNT"} <= _codes(report)
    assert transaction.needs_review


def test_debit_and_credit_is_an_error() -> None:
    transaction = Transaction(
        transaction_date=date(2024, 4, 1),
        description="AMBIGUOUS AMOUNT",
        debit=100.0,
        credit=100.0,
    )
    report = TransactionValidator().validate([transaction])

    assert "DEBIT_AND_CREDIT" in _codes(report)
    assert report.error_count == 2
    assert "VALIDATION_ERRORS_PRESENT" in _codes(report)


def test_negative_amount_and_suspicious_description_are_warnings() -> None:
    transaction = Transaction(
        transaction_date=date(2024, 4, 1),
        description="12345 ////",
        debit=-10.0,
    )
    report = TransactionValidator().validate([transaction])

    assert "NEGATIVE_AMOUNT" in _codes(report)
    assert "SUSPICIOUS_DESCRIPTION" in _codes(report)
    assert report.warning_count >= 2


def test_future_date_is_flagged() -> None:
    transaction = Transaction(
        transaction_date=date.today() + timedelta(days=3),
        description="FUTURE MERCHANT",
        debit=10.0,
    )
    report = TransactionValidator().validate([transaction])

    assert "FUTURE_DATE" in _codes(report)


def test_duplicate_transactions_are_flagged() -> None:
    first = Transaction(
        transaction_date=date(2024, 4, 1),
        description="SALARY CREDIT ACME",
        credit=85000.0,
        balance=210000.0,
    )
    second = Transaction(
        transaction_date=date(2024, 4, 1),
        description="SALARY CREDIT ACME",
        credit=85000.0,
        balance=210000.0,
    )

    report = TransactionValidator().validate([first, second])

    assert "POSSIBLE_DUPLICATE" in _codes(report)
    assert second.needs_review


def test_balance_sequence_success_adds_info() -> None:
    account = AccountInfo(opening_balance=125000.0, closing_balance=208750.0)
    transactions = [
        Transaction(
            transaction_date=date(2024, 4, 1),
            description="SALARY",
            credit=85000.0,
            balance=210000.0,
        ),
        Transaction(
            transaction_date=date(2024, 4, 2),
            description="ZOMATO",
            debit=1250.0,
            balance=208750.0,
        ),
    ]

    report = BalanceValidator().validate(transactions, account)

    assert "BALANCE_MISMATCH" not in _codes(report)
    success = [issue for issue in report.issues if issue.code == "BALANCE_SEQUENCE_OK"]
    assert success and success[0].severity == IssueSeverity.INFO


def test_balance_mismatch_marks_transaction_for_review() -> None:
    account = AccountInfo(opening_balance=125000.0)
    transactions = [
        Transaction(
            transaction_date=date(2024, 4, 1),
            description="SALARY",
            credit=85000.0,
            balance=200000.0,
        )
    ]

    report = BalanceValidator().validate(transactions, account)

    assert "BALANCE_MISMATCH" in _codes(report)
    assert transactions[0].needs_review


def test_descending_statement_is_validated_chronologically() -> None:
    account = AccountInfo(opening_balance=1000.0, closing_balance=1300.0)
    transactions = [
        Transaction(
            transaction_date=date(2024, 4, 3),
            description="THIRD",
            debit=200.0,
            balance=1300.0,
        ),
        Transaction(
            transaction_date=date(2024, 4, 2),
            description="SECOND",
            credit=1000.0,
            balance=1500.0,
        ),
        Transaction(
            transaction_date=date(2024, 4, 1),
            description="FIRST",
            debit=500.0,
            balance=500.0,
        ),
    ]

    report = BalanceValidator().validate(transactions, account)

    assert "BALANCE_MISMATCH" not in _codes(report)
    assert "CLOSING_BALANCE_MISMATCH" not in _codes(report)
    assert "BALANCE_SEQUENCE_OK" in _codes(report)


def test_closing_balance_mismatch_is_flagged() -> None:
    account = AccountInfo(opening_balance=1000.0, closing_balance=9999.0)
    transactions = [
        Transaction(
            transaction_date=date(2024, 4, 1),
            description="DEPOSIT",
            credit=500.0,
            balance=1500.0,
        )
    ]

    report = BalanceValidator().validate(transactions, account)

    assert "CLOSING_BALANCE_MISMATCH" in _codes(report)


def test_empty_transactions_return_empty_report() -> None:
    assert not BalanceValidator().validate([], AccountInfo()).issues
