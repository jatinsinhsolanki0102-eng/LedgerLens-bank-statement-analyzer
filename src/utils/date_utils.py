"""Date parsing helpers for the range of formats found in bank statements."""

from __future__ import annotations

import re
from datetime import date, datetime

MONTH_NAMES = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

DATE_TOKEN_PATTERN = re.compile(
    r"(?<!\d)(?:"
    r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}"
    r"|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}"
    r"|\d{1,2}[\s-](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|"
    r"January|February|March|April|May|June|July|August|September|October|"
    r"November|December)[\s-]\d{2,4}"
    r"|\d{1,2}[\s-](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r")(?!\d)",
    re.IGNORECASE,
)

DATE_AT_START_PATTERN = re.compile(
    r"^\s*(?:\d{1,4}\s+)?"
    r"("
    r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}"
    r"|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}"
    r"|\d{1,2}[\s-](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|"
    r"January|February|March|April|May|June|July|August|September|October|"
    r"November|December)[\s-]\d{2,4}"
    r"|\d{1,2}[\s-](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r")",
    re.IGNORECASE,
)

_DEFAULT_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%d/%m/%y",
    "%d-%m-%y",
    "%d.%m.%y",
    "%d %b %Y",
    "%d-%b-%Y",
    "%d/%b/%Y",
    "%d %B %Y",
    "%d-%B-%Y",
    "%d %b %y",
    "%d-%b-%y",
    "%d%b%y",
    "%d%b%Y",
)


def parse_date(value: str | None, default_year: int | None = None) -> date | None:
    """Parse a date string, preferring day-first interpretation.

    Returns ``None`` rather than raising for malformed values so extraction can
    retain a transaction while flagging its date for review.
    """

    if not value:
        return None

    cleaned = " ".join(str(value).strip().replace(",", " ").split())
    cleaned = re.sub(r"\b(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\b", "", cleaned, flags=re.I)
    cleaned = cleaned.strip()
    if not cleaned:
        return None

    for date_format in _DEFAULT_FORMATS:
        try:
            parsed = datetime.strptime(cleaned, date_format).date()
            return _normalise_two_digit_year(parsed, default_year)
        except ValueError:
            continue

    match = DATE_TOKEN_PATTERN.search(cleaned)
    if match and match.group(0) != cleaned:
        return parse_date(match.group(0), default_year=default_year)

    if default_year:
        for date_format in ("%d/%m", "%d-%m", "%d %b", "%d-%b"):
            try:
                parsed = datetime.strptime(f"{cleaned} {default_year}", f"{date_format} %Y")
                return parsed.date()
            except ValueError:
                continue

    return None


def _normalise_two_digit_year(parsed: date, default_year: int | None) -> date:
    if default_year is None or parsed.year >= 100:
        return parsed
    century = (default_year // 100) * 100
    candidate = parsed.replace(year=century + parsed.year)
    if candidate.year - default_year > 50:
        candidate = candidate.replace(year=candidate.year - 100)
    return candidate


def extract_dates(text: str, default_year: int | None = None) -> list[date]:
    """Extract all valid dates from a piece of text in source order."""

    dates: list[date] = []
    for match in DATE_TOKEN_PATTERN.finditer(text or ""):
        parsed = parse_date(match.group(0), default_year=default_year)
        if parsed:
            dates.append(parsed)
    return dates


def find_date_at_start(line: str, default_year: int | None = None) -> tuple[date | None, str]:
    """Return the leading date and the remainder of a transaction line."""

    match = DATE_AT_START_PATTERN.match(line or "")
    if not match:
        return None, (line or "").strip()
    parsed = parse_date(match.group(1), default_year=default_year)
    return parsed, line[match.end() :].strip()


def detect_statement_order(dates: list[date | None]) -> str:
    """Infer whether dated rows are in ascending or descending order."""

    valid_dates = [item for item in dates if item is not None]
    if len(valid_dates) < 2:
        return "ascending"
    increases = sum(
        current >= previous
        for previous, current in zip(valid_dates, valid_dates[1:], strict=False)
    )
    return "ascending" if increases >= (len(valid_dates) - 1) / 2 else "descending"
