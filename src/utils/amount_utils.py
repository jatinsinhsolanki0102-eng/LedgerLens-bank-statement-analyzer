"""Currency parsing helpers supporting Indian number formatting."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from config.settings import CURRENCY_SYMBOL

_AMOUNT_TOKEN_PATTERN = re.compile(
    r"(?<![\w.])"
    r"(?P<prefix>INR|Rs\.?|₹)?\s*"
    r"(?P<number>\(?-?\d[\d,]*(?:\.\d{1,2})?\)?)"
    r"(?P<marker>\s*(?:CR|DR))?"
    r"(?![\w.])",
    re.IGNORECASE,
)

_ACCOUNT_REFERENCE_PATTERN = re.compile(r"\b\d{9,}\b")


@dataclass(frozen=True, slots=True)
class AmountToken:
    raw: str
    value: float
    start: int
    end: int
    has_decimal: bool
    has_comma: bool
    marker: str | None = None


def parse_amount(value: str | float | int | None) -> float | None:
    """Parse a statement amount into a float.

    Handles currency symbols, Indian grouping commas, parentheses for negative
    values, and trailing CR/DR markers. Invalid values return ``None``.
    """

    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    cleaned = str(value).strip()
    if not cleaned:
        return None

    cleaned = cleaned.replace(CURRENCY_SYMBOL, " ")
    cleaned = re.sub(r"(?<![A-Za-z])(?:INR|Rs\.?)(?![A-Za-z])", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:CR|DR)\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("\u2212", "-").replace("\u2013", "-")
    cleaned = cleaned.strip()

    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()").replace(",", "").replace(" ", "")

    if not re.fullmatch(r"[-+]?\d+(?:\.\d{1,2})?", cleaned):
        return None

    try:
        parsed = Decimal(cleaned)
    except InvalidOperation:
        return None
    if negative:
        parsed = -parsed
    return float(parsed)


def _group_indian_digits(digits: str) -> str:
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups + [tail])


def format_currency(value: float | None, include_symbol: bool = True) -> str:
    """Format a numeric value using Indian digit grouping."""

    if value is None:
        return "—"
    whole, fraction = f"{abs(value):.2f}".split(".")
    formatted = f"{_group_indian_digits(whole)}.{fraction}"
    sign = "-" if value < 0 else ""
    prefix = f"{CURRENCY_SYMBOL} " if include_symbol else ""
    return f"{sign}{prefix}{formatted}"


def find_amount_tokens(text: str) -> list[AmountToken]:
    """Find currency-like numeric tokens while ignoring long reference numbers."""

    tokens: list[AmountToken] = []
    for match in _AMOUNT_TOKEN_PATTERN.finditer(text or ""):
        raw_number = match.group("number")
        raw = match.group(0).strip()
        compact = raw_number.replace(",", "").replace("(", "").replace(")", "")
        digits_only = re.sub(r"\D", "", compact)
        has_decimal = "." in raw_number
        has_comma = "," in raw_number

        if not has_decimal and not has_comma and len(digits_only) > 8:
            continue
        if _ACCOUNT_REFERENCE_PATTERN.fullmatch(digits_only):
            continue

        value = parse_amount(raw)
        if value is None:
            continue
        marker_match = match.group("marker")
        tokens.append(
            AmountToken(
                raw=raw,
                value=value,
                start=match.start(),
                end=match.end(),
                has_decimal=has_decimal,
                has_comma=has_comma,
                marker=marker_match.strip().upper() if marker_match else None,
            )
        )
    return tokens


def extract_trailing_amounts(
    text: str, max_tokens: int = 3
) -> tuple[list[AmountToken], str]:
    """Separate trailing monetary columns from a transaction description.

    Statements frequently collapse blank debit/credit columns, so the parser
    works with the trailing numeric group and later uses balance movement to
    establish direction.
    """

    tokens = find_amount_tokens(text)
    if not tokens:
        return [], (text or "").strip()

    trailing: list[AmountToken] = [tokens[-1]]
    for token in reversed(tokens[:-1]):
        previous = trailing[0]
        gap = text[token.end : previous.start]
        if len(gap) > 12 or re.search(r"[A-Za-z]{2,}", gap):
            break
        trailing.insert(0, token)
        if len(trailing) >= max_tokens:
            break

    first_token = trailing[0]
    description = text[: first_token.start].strip(" -|")
    return trailing, description


def amounts_equal(left: float | None, right: float | None, tolerance: float = 0.01) -> bool:
    """Compare optional monetary values using a small rounding tolerance."""

    if left is None or right is None:
        return False
    return abs(left - right) <= tolerance
