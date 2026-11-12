"""Amount, date, account, transaction, and bank-parser extraction tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.extraction.account_extractor import (
    AccountExtractor,
    detect_bank_name,
)
from src.extraction.bank_parser import get_bank_parser
from src.extraction.transaction_extractor import TransactionExtractor
from src.models import AccountInfo
from src.utils.amount_utils import (
    amounts_equal,
    extract_trailing_amounts,
    find_amount_tokens,
    format_currency,
    parse_amount,
)
from src.utils.date_utils import (
    detect_statement_order,
    find_date_at_start,
    parse_date,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1,234.56", 1234.56),
        ("₹ 1,23,456.78", 123456.78),
        ("INR 500", 500.0),
        ("Rs. 250.00", 250.0),
        ("(500.00)", -500.0),
        ("1,000.00 CR", 1000.0),
        ("-42.50", -42.5),
        (123.45, 123.45),
        ("", None),
        ("not an amount", None),
    ],
)
def test_parse_amount(raw: object, expected: float | None) -> None:
    assert parse_amount(raw) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "₹ 0.00"),
        (999, "₹ 999.00"),
        (1234.5, "₹ 1,234.50"),
        (123456.78, "₹ 1,23,456.78"),
        (12345678.9, "₹ 1,23,45,678.90"),
        (-123456.78, "-₹ 1,23,456.78"),
        (None, "—"),
    ],
)
def test_format_currency_uses_indian_grouping(value: float | None, expected: str) -> None:
    assert format_currency(value) == expected


def test_format_currency_can_omit_symbol() -> None:
    assert format_currency(123456.78, include_symbol=False) == "1,23,456.78"


def test_amounts_equal_respects_tolerance() -> None:
    assert amounts_equal(100.0, 100.005, tolerance=0.01)
    assert not amounts_equal(100.0, 100.02, tolerance=0.01)
    assert not amounts_equal(None, 100.0)


def test_find_amount_tokens_ignores_long_references() -> None:
    tokens = find_amount_tokens("UPI 123456789012 1,250.00 208,750.00")

    assert [token.value for token in tokens] == [1250.0, 208750.0]


def test_extract_trailing_amounts_separates_description() -> None:
    tokens, description = extract_trailing_amounts(
        "UPI/ZOMATO/ORDER 445566 UPI445566 1,250.00 208,750.00"
    )

    assert [token.value for token in tokens] == [1250.0, 208750.0]
    assert description == "UPI/ZOMATO/ORDER 445566 UPI445566"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("01/04/2024", date(2024, 4, 1)),
        ("01-04-2024", date(2024, 4, 1)),
        ("2024-04-01", date(2024, 4, 1)),
        ("01-Apr-2024", date(2024, 4, 1)),
        ("1 April 2024", date(2024, 4, 1)),
        ("garbage", None),
    ],
)
def test_parse_date_formats(raw: str, expected: date | None) -> None:
    assert parse_date(raw) == expected


def test_parse_date_uses_default_year() -> None:
    assert parse_date("01/04", default_year=2024) == date(2024, 4, 1)


def test_find_date_at_start_returns_remainder() -> None:
    parsed, remainder = find_date_at_start("02/04/2024 UPI/ZOMATO ORDER 1,250.00")

    assert parsed == date(2024, 4, 2)
    assert remainder == "UPI/ZOMATO ORDER 1,250.00"


def test_detect_statement_order() -> None:
    ascending = [date(2024, 4, 1), date(2024, 4, 2), date(2024, 4, 3)]
    descending = list(reversed(ascending))

    assert detect_statement_order(ascending) == "ascending"
    assert detect_statement_order(descending) == "descending"
    assert detect_statement_order([None, date(2024, 4, 1)]) == "ascending"


def test_account_extraction(statement_lines: list[str]) -> None:
    text = "\n".join(statement_lines)
    account = AccountExtractor().extract(text)

    assert account.account_holder_name == "AARAV SHARMA"
    assert account.account_number == "50100123456789"
    assert account.ifsc_code == "HDFC0001234"
    assert account.bank_name == "HDFC Bank"
    assert account.statement_period_start == date(2024, 4, 1)
    assert account.statement_period_end == date(2024, 4, 30)
    assert account.opening_balance == 125000.0
    assert account.closing_balance == 117287.0
    assert "01 Apr 2024" in (account.statement_period_label or "")


def test_account_number_masking() -> None:
    assert AccountExtractor.mask_account_number("50100123456789") == "**********6789"
    assert AccountExtractor.mask_account_number("1234") == "****"
    assert AccountExtractor.mask_account_number(None) == "Not available"


def test_bank_detection_from_name_and_ifsc() -> None:
    assert detect_bank_name("HDFC BANK LIMITED") == "HDFC Bank"
    assert detect_bank_name("IFSC: ICIC0001234") == "ICICI Bank"
    assert detect_bank_name("an unknown institution") is None


def test_line_transaction_extraction(statement_lines: list[str], tmp_path: Path) -> None:
    account = AccountInfo(opening_balance=125000.0)
    result = TransactionExtractor().extract(["\n".join(statement_lines)], account)

    assert len(result.transactions) == 18
    assert result.warnings == []

    salary = result.transactions[0]
    assert salary.transaction_date == date(2024, 4, 1)
    assert salary.credit == 85000.0
    assert salary.debit is None
    assert salary.balance == 210000.0
    assert "SALARY CREDIT" in salary.description

    zomato = result.transactions[1]
    assert zomato.debit == 1250.0
    assert zomato.credit is None
    assert zomato.balance == 208750.0

    transfer = result.transactions[10]
    assert transfer.credit == 5000.0
    assert transfer.debit is None

    interest = result.transactions[-1]
    assert interest.credit == 1000.0
    assert interest.balance == 117287.0


def test_multiline_description_is_joined() -> None:
    lines = [
        "01/04/2024 SALARY CREDIT ACME CORP 0.00 85,000.00 210,000.00",
        "APRIL PAYROLL NEFT REF 998877",
    ]
    result = TransactionExtractor().extract(lines, AccountInfo(opening_balance=125000.0))

    assert len(result.transactions) == 1
    assert "APRIL PAYROLL NEFT REF 998877" in result.transactions[0].description


def test_duplicate_transactions_are_removed() -> None:
    lines = [
        "01/04/2024 SALARY CREDIT ACME CORP 0.00 85,000.00 210,000.00",
        "01/04/2024 SALARY CREDIT ACME CORP 0.00 85,000.00 210,000.00",
        "02/04/2024 UPI/ZOMATO ORDER 1,250.00 208,750.00",
    ]
    result = TransactionExtractor().extract(lines, AccountInfo(opening_balance=125000.0))

    assert len(result.transactions) == 2
    assert any("duplicate" in warning.lower() for warning in result.warnings)


def test_extraction_flags_balance_mismatch() -> None:
    lines = [
        "01/04/2024 SALARY CREDIT ACME CORP 0.00 85,000.00 210,000.00",
        "02/04/2024 UPI/ZOMATO ORDER 1,250.00 205,000.00",
    ]
    result = TransactionExtractor().extract(lines, AccountInfo(opening_balance=125000.0))

    assert result.transactions[1].needs_review
    assert any("Balance movement" in warning for warning in result.warnings)


def test_table_transaction_extraction() -> None:
    tables = [
        [
            ["Date", "Narration", "Chq/Ref", "Withdrawal Amt", "Deposit Amt", "Closing Balance"],
            ["01/04/2024", "SALARY CREDIT", "NEFT123", "", "50000.00", "150000.00"],
            ["02/04/2024", "UPI/ZOMATO ORDER", "445566", "1000.00", "", "149000.00"],
            ["03/04/2024", "NEFT SELF TRANSFER", "NEFT552", "5000.00", "", "144000.00"],
        ]
    ]
    result = TransactionExtractor().extract(
        pages=[""], account=AccountInfo(opening_balance=100000.0), tables=tables
    )

    assert len(result.transactions) == 3
    assert result.transactions[0].credit == 50000.0
    assert result.transactions[1].debit == 1000.0
    assert result.transactions[1].balance == 149000.0
    assert not result.warnings


def test_bank_parser_selection(statement_lines: list[str]) -> None:
    text = "\n".join(statement_lines)

    hdfc_parser = get_bank_parser(text, bank_name="HDFC Bank")
    generic_parser = get_bank_parser("A statement with no bank name", bank_name=None)

    assert hdfc_parser.name == "HDFC Bank layout parser"
    assert generic_parser.name == "Generic layout parser"
