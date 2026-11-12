"""Extract account metadata using flexible, label-driven heuristics."""

from __future__ import annotations

import re
from datetime import date

from src.models import AccountInfo
from src.utils.amount_utils import parse_amount
from src.utils.date_utils import DATE_TOKEN_PATTERN, extract_dates, parse_date

KNOWN_BANKS: tuple[tuple[str, str], ...] = (
    (r"\bstate bank of india\b|\bsbi\b", "State Bank of India"),
    (r"\bhdfc bank\b", "HDFC Bank"),
    (r"\bicici bank\b", "ICICI Bank"),
    (r"\baxis bank\b", "Axis Bank"),
    (r"\bkotak mahindra bank\b|\bkotak bank\b", "Kotak Mahindra Bank"),
    (r"\bpunjab national bank\b|\bpNB\b", "Punjab National Bank"),
    (r"\bbank of baroda\b", "Bank of Baroda"),
    (r"\bcanara bank\b", "Canara Bank"),
    (r"\bunion bank of india\b", "Union Bank of India"),
    (r"\bindusind bank\b", "IndusInd Bank"),
    (r"\byes bank\b", "Yes Bank"),
    (r"\bidfc first bank\b", "IDFC FIRST Bank"),
    (r"\bfederal bank\b", "Federal Bank"),
)

IFSC_BANK_MAP = {
    "SBIN": "State Bank of India",
    "HDFC": "HDFC Bank",
    "ICIC": "ICICI Bank",
    "UTIB": "Axis Bank",
    "KKBK": "Kotak Mahindra Bank",
    "PUNB": "Punjab National Bank",
    "BARB": "Bank of Baroda",
    "CNRB": "Canara Bank",
    "UBIN": "Union Bank of India",
    "INDB": "IndusInd Bank",
    "YESB": "Yes Bank",
    "IDFB": "IDFC FIRST Bank",
    "FDRL": "Federal Bank",
}

_HOLDER_LABEL = re.compile(
    r"(?:account\s*holder(?:\s*name)?|customer\s*name|name\s*of\s*(?:the\s*)?account\s*holder)"
    r"\s*[:\-]?\s*(?P<value>.+)$",
    re.IGNORECASE,
)
_ACCOUNT_NUMBER_LABEL = re.compile(
    r"(?:account\s*(?:no\.?|number|#)?|a/c\s*(?:no\.?|number)?)"
    r"\s*[:\-]?\s*(?P<value>[Xx*\d][Xx*\d\s\-]{5,23})",
    re.IGNORECASE,
)
_IFSC_PATTERN = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
_IFSC_LABEL = re.compile(r"\bIFSC(?:\s*code)?\s*[:\-]?\s*([A-Z]{4}0[A-Z0-9]{6})\b", re.I)

_BALANCE_VALUE = re.compile(
    r"(?:INR|Rs\.?|₹)?\s*"
    r"(\(?-?\d{1,3}(?:,\d{2,3})*(?:\.\d{1,2})?\)?|\(?-?\d+\.\d{1,2}\)?)",
    re.IGNORECASE,
)
_OPENING_LABEL = re.compile(
    r"(?:opening\s*balance|balance\s*b/?f|brought\s*forward|beginning\s*balance)",
    re.IGNORECASE,
)
_CLOSING_LABEL = re.compile(
    r"(?:closing\s*balance|balance\s*c/?f|carried\s*forward|ending\s*balance)",
    re.IGNORECASE,
)
_NOISE_VALUE = re.compile(r"\b(?:ifsc|branch|account\s*no|a/c\s*no)\b", re.IGNORECASE)


def detect_bank_name(text: str) -> str | None:
    """Identify a bank from a known name or IFSC prefix."""

    if not text:
        return None
    for pattern, canonical_name in KNOWN_BANKS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return canonical_name

    ifsc_match = _IFSC_PATTERN.search(text.upper())
    if ifsc_match:
        return IFSC_BANK_MAP.get(ifsc_match.group(0)[:4])
    return None


class AccountExtractor:
    """Extract account details without assuming a single bank layout."""

    def extract(self, text: str) -> AccountInfo:
        lines = [self._clean_line(line) for line in (text or "").splitlines()]
        lines = [line for line in lines if line]
        default_year = self._infer_default_year(text)

        period_start, period_end = self._extract_statement_period(text, default_year)
        ifsc = self._extract_ifsc(text)
        bank_name = self._extract_bank_name(text, ifsc) or detect_bank_name(text)

        return AccountInfo(
            account_holder_name=self._extract_holder_name(lines),
            account_number=self._extract_account_number(lines),
            ifsc_code=ifsc,
            bank_name=bank_name,
            statement_period_start=period_start,
            statement_period_end=period_end,
            opening_balance=self._extract_balance(text, _OPENING_LABEL),
            closing_balance=self._extract_balance(text, _CLOSING_LABEL),
        )

    @staticmethod
    def mask_account_number(account_number: str | None, visible_digits: int = 4) -> str:
        """Mask an account number for display outside the export file."""

        if not account_number:
            return "Not available"
        if len(account_number) <= visible_digits:
            return "*" * len(account_number)
        return f"{'*' * (len(account_number) - visible_digits)}{account_number[-visible_digits:]}"

    def _extract_holder_name(self, lines: list[str]) -> str | None:
        for line in lines:
            match = _HOLDER_LABEL.search(line)
            if match:
                value = self._trim_labeled_value(match.group("value"))
                if value and not _NOISE_VALUE.search(value):
                    return value[:100]
        return None

    def _extract_account_number(self, lines: list[str]) -> str | None:
        for line in lines:
            match = _ACCOUNT_NUMBER_LABEL.search(line)
            if not match:
                continue
            value = re.sub(r"[\s\-]", "", match.group("value")).upper()
            if 6 <= len(value) <= 24 and sum(char.isdigit() for char in value) >= 4:
                return value
        return None

    def _extract_ifsc(self, text: str) -> str | None:
        labeled_match = _IFSC_LABEL.search(text)
        if labeled_match:
            return labeled_match.group(1).upper()
        match = _IFSC_PATTERN.search((text or "").upper())
        return match.group(0) if match else None

    def _extract_bank_name(self, text: str, ifsc: str | None) -> str | None:
        for line in text.splitlines():
            if re.search(r"\bbank\s*name\b", line, flags=re.IGNORECASE):
                value = re.split(r":", line, maxsplit=1)
                if len(value) == 2 and value[1].strip():
                    candidate = value[1].strip(" :-")
                    for pattern, canonical_name in KNOWN_BANKS:
                        if re.search(pattern, candidate, flags=re.IGNORECASE):
                            return canonical_name
                    return candidate[:80]

        detected = detect_bank_name(text)
        if detected:
            return detected
        if ifsc:
            return IFSC_BANK_MAP.get(ifsc[:4])
        return None

    def _extract_statement_period(
        self, text: str, default_year: int | None
    ) -> tuple[date | None, date | None]:
        period_match = re.search(
            r"(?:statement\s*(?:period|for\s*the\s*period)|period)\s*[:\-]?\s*"
            r"(?P<period>[^\n]{8,120})",
            text or "",
            flags=re.IGNORECASE,
        )
        if period_match:
            dates = extract_dates(period_match.group("period"), default_year=default_year)
            if len(dates) >= 2:
                return dates[0], dates[-1]
            if len(dates) == 1:
                return dates[0], None

        from_to_match = re.search(
            r"(?:statement\s*)?from\s*(?P<start>[^\n]{6,40}?)\s*(?:to|until|through)\s*"
            r"(?P<end>[^\n]{6,40})",
            text or "",
            flags=re.IGNORECASE,
        )
        if from_to_match:
            start = parse_date(from_to_match.group("start"), default_year=default_year)
            end = parse_date(from_to_match.group("end"), default_year=default_year)
            if start or end:
                return start, end

        start_match = re.search(
            r"(?:statement\s*from|start(?:ing)?\s*date)\s*[:\-]?\s*"
            r"(?P<date>" + DATE_TOKEN_PATTERN.pattern + ")",
            text or "",
            flags=re.IGNORECASE,
        )
        end_match = re.search(
            r"(?:statement\s*(?:to|until)|end(?:ing)?\s*date)\s*[:\-]?\s*"
            r"(?P<date>" + DATE_TOKEN_PATTERN.pattern + ")",
            text or "",
            flags=re.IGNORECASE,
        )
        start = parse_date(start_match.group("date"), default_year=default_year) if start_match else None
        end = parse_date(end_match.group("date"), default_year=default_year) if end_match else None
        return start, end

    def _extract_balance(self, text: str, label_pattern: re.Pattern[str]) -> float | None:
        for line in (text or "").splitlines():
            label_match = label_pattern.search(line)
            if not label_match:
                continue
            candidate_text = line[label_match.end() :]
            candidates = _BALANCE_VALUE.findall(candidate_text)
            if not candidates:
                continue
            for candidate in reversed(candidates):
                parsed = parse_amount(candidate)
                if parsed is not None:
                    return parsed
        return None

    @staticmethod
    def _infer_default_year(text: str) -> int | None:
        years = [int(year) for year in re.findall(r"\b(?:19|20)\d{2}\b", text or "")]
        if not years:
            return None
        return max(set(years), key=years.count)

    @staticmethod
    def _clean_line(line: str) -> str:
        return " ".join((line or "").replace("\u00a0", " ").split())

    @staticmethod
    def _trim_labeled_value(value: str) -> str:
        value = value.strip(" :-")
        value = re.split(r"\s{2,}|\s+(?:account|a/c|ifsc|branch)\b", value, maxsplit=1, flags=re.I)[0]
        return value.strip(" :-")
