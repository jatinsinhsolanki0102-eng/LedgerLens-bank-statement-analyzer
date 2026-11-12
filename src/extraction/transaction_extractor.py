"""Layout-tolerant extraction of transaction rows from statement text and tables."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from config.settings import BALANCE_TOLERANCE
from src.models import AccountInfo, Transaction
from src.utils.amount_utils import AmountToken, amounts_equal, extract_trailing_amounts, parse_amount
from src.utils.date_utils import find_date_at_start, parse_date
from src.utils.logging_config import get_logger

logger = get_logger("transaction_extractor")


@dataclass(slots=True)
class _RawRow:
    transaction_date: date | None
    description: str
    page_number: int | None = None
    raw_text: str = ""
    amount_tokens: list[AmountToken] = field(default_factory=list)
    raw_amount: float | None = None
    debit: float | None = None
    credit: float | None = None
    balance: float | None = None
    explicit_direction: str | None = None
    type_text: str = ""
    from_table: bool = False


@dataclass(slots=True)
class TransactionExtractionResult:
    transactions: list[Transaction]
    warnings: list[str]


class TransactionExtractor:
    """Extract transactions while preserving source descriptions and ordering."""

    _SUMMARY_PATTERN = re.compile(
        r"^\s*(?:opening\s*balance|closing\s*balance|balance\s*[bc]/?f|"
        r"brought\s*forward|carried\s*forward|statement\s*summary|"
        r"grand\s*total|total\s+transactions?)\b",
        re.IGNORECASE,
    )
    _NOISE_CONTINUATION_PATTERN = re.compile(
        r"\b(?:statement|summary|page\s+\d+|generated\s+on|customer\s+id|"
        r"account\s*(?:no|number|holder)|ifsc|branch|address|email|phone|"
        r"mobile|nominee|registered\s+office|transaction\s*(?:date|details)|"
        r"narration|withdrawal|deposit|balance)\b",
        re.IGNORECASE,
    )
    _CREDIT_HINT = re.compile(
        r"\b(?:salary|stipend|payroll|refund|reversal|cashback|received|"
        r"credit|deposit|interest\s+credit)\b",
        re.IGNORECASE,
    )
    _DEBIT_HINT = re.compile(
        r"\b(?:withdrawal|atm|purchase|payment|paid|charges?|fee|bill|"
        r"debit|sent|spent)\b",
        re.IGNORECASE,
    )

    def extract(
        self,
        pages: list[str],
        account: AccountInfo | None = None,
        tables: list[list[list[str]]] | None = None,
    ) -> TransactionExtractionResult:
        default_year = self._default_year(account, pages)
        opening_balance = account.opening_balance if account else None

        line_rows = self._extract_rows_from_pages(pages, default_year)
        table_rows = self._extract_rows_from_tables(tables or [], default_year)

        line_transactions, line_warnings = self._resolve_transactions(
            line_rows, opening_balance
        )
        table_transactions, table_warnings = self._resolve_transactions(
            table_rows, opening_balance
        )

        warnings: list[str] = []
        if table_transactions and line_transactions:
            if len(line_transactions) >= len(table_transactions):
                selected = line_transactions
                warnings.extend(line_warnings)
            else:
                selected = table_transactions
                warnings.extend(table_warnings)
        elif table_transactions:
            selected = table_transactions
            warnings.extend(table_warnings)
        else:
            selected = line_transactions
            warnings.extend(line_warnings)

        transactions, duplicate_count = self._deduplicate(selected)
        if duplicate_count:
            warnings.append(
                f"Removed {duplicate_count} exact duplicate transaction row(s)."
            )
        if not transactions:
            warnings.append("No transaction rows could be identified in this statement.")

        return TransactionExtractionResult(transactions=transactions, warnings=warnings)

    def _extract_rows_from_pages(self, pages: list[str], default_year: int | None) -> list[_RawRow]:
        rows: list[_RawRow] = []
        previous_row: _RawRow | None = None
        skipped_dated_lines = 0

        for page_index, page_text in enumerate(pages, start=1):
            for raw_line in (page_text or "").splitlines():
                line = self._normalise_line(raw_line)
                if not line:
                    continue

                if self._SUMMARY_PATTERN.search(line):
                    previous_row = None
                    continue

                transaction_date, remainder = find_date_at_start(
                    line, default_year=default_year
                )
                if transaction_date is None:
                    if self._is_continuation(line, previous_row):
                        previous_row.description = (
                            f"{previous_row.description} {line}".strip()
                        )
                    continue

                amount_tokens, description = extract_trailing_amounts(remainder)
                if not amount_tokens:
                    skipped_dated_lines += 1
                    previous_row = None
                    continue
                if self._SUMMARY_PATTERN.search(description):
                    previous_row = None
                    continue

                row = _RawRow(
                    transaction_date=transaction_date,
                    description=self._normalise_line(description),
                    page_number=page_index,
                    raw_text=raw_line.strip(),
                    amount_tokens=amount_tokens,
                )
                rows.append(row)
                previous_row = row

        if skipped_dated_lines:
            logger.info("Skipped %s dated lines without amounts", skipped_dated_lines)
        return rows

    def _extract_rows_from_tables(
        self, tables: list[list[list[str]]], default_year: int | None
    ) -> list[_RawRow]:
        rows: list[_RawRow] = []
        active_mapping: dict[str, int] | None = None
        previous_row: _RawRow | None = None

        for table in tables:
            table_mapping: dict[str, int] | None = None
            for raw_row in table:
                row = [self._normalise_line(cell) for cell in raw_row]
                if not any(row):
                    continue

                header_mapping = self._detect_table_header(row)
                if header_mapping:
                    table_mapping = header_mapping
                    active_mapping = header_mapping
                    previous_row = None
                    continue
                mapping = table_mapping or active_mapping
                if not mapping:
                    continue

                date_cell = self._cell(row, mapping.get("date"))
                description_cell = self._cell(row, mapping.get("description"))
                debit_value = parse_amount(self._cell(row, mapping.get("debit")))
                credit_value = parse_amount(self._cell(row, mapping.get("credit")))
                balance_value = parse_amount(self._cell(row, mapping.get("balance")))
                amount_value = parse_amount(self._cell(row, mapping.get("amount")))
                type_text = self._cell(row, mapping.get("type")) or ""

                transaction_date = parse_date(date_cell, default_year=default_year)
                if transaction_date is None:
                    if (
                        previous_row
                        and description_cell
                        and debit_value is None
                        and credit_value is None
                        and balance_value is None
                        and amount_value is None
                    ):
                        previous_row.description = (
                            f"{previous_row.description} {description_cell}".strip()
                        )
                    continue

                if self._SUMMARY_PATTERN.search(description_cell):
                    previous_row = None
                    continue

                if not any(
                    value is not None
                    for value in (debit_value, credit_value, balance_value, amount_value)
                ):
                    continue

                explicit_direction = self._direction_from_text(type_text)
                row_object = _RawRow(
                    transaction_date=transaction_date,
                    description=description_cell,
                    raw_text=" | ".join(cell for cell in row if cell),
                    debit=debit_value,
                    credit=credit_value,
                    balance=balance_value,
                    raw_amount=amount_value,
                    explicit_direction=explicit_direction,
                    type_text=type_text,
                    from_table=True,
                )
                rows.append(row_object)
                previous_row = row_object

        return rows

    def _resolve_transactions(
        self, rows: list[_RawRow], opening_balance: float | None
    ) -> tuple[list[Transaction], list[str]]:
        transactions: list[Transaction] = []
        warnings: list[str] = []
        previous_balance = opening_balance
        mismatch_count = 0

        for row_index, row in enumerate(rows, start=1):
            debit = self._positive_or_none(row.debit)
            credit = self._positive_or_none(row.credit)
            balance = row.balance
            amount: float | None = None
            marker_direction: str | None = None
            needs_review = False

            if debit is not None or credit is not None:
                amount = debit if debit is not None else credit
            elif row.amount_tokens:
                amount, balance, marker_direction, ambiguous = self._interpret_line_amounts(
                    row.amount_tokens
                )
                needs_review = needs_review or ambiguous
            elif row.raw_amount is not None:
                amount = abs(row.raw_amount)
                marker_direction = row.explicit_direction

            if debit is None and credit is None and amount is not None:
                direction = self._resolve_direction(
                    row=row,
                    marker_direction=marker_direction,
                    previous_balance=previous_balance,
                    balance=balance,
                )
                if row.amount_tokens and len(row.amount_tokens) > 2:
                    inferred_delta = self._balance_delta(previous_balance, balance)
                    if inferred_delta is not None:
                        target_amount = abs(inferred_delta)
                        if any(
                            amounts_equal(abs(token.value), target_amount)
                            for token in row.amount_tokens[:-1]
                        ):
                            amount = target_amount
                if direction == "debit":
                    debit = amount
                elif direction == "credit":
                    credit = amount
                else:
                    needs_review = True

            balance_delta = self._balance_delta(previous_balance, balance)
            if balance_delta is not None and amount is not None:
                delta_direction = "credit" if balance_delta > 0 else "debit"
                if abs(abs(balance_delta) - amount) > BALANCE_TOLERANCE:
                    needs_review = True
                    mismatch_count += 1
                    if mismatch_count <= 10:
                        warnings.append(
                            "Balance movement does not match the extracted amount "
                            f"near transaction row {row_index}."
                        )
                elif (debit is not None and delta_direction != "debit") or (
                    credit is not None and delta_direction != "credit"
                ):
                    needs_review = True
                    if mismatch_count <= 10:
                        warnings.append(
                            "Transaction direction conflicts with the balance movement "
                            f"near transaction row {row_index}."
                        )
                    mismatch_count += 1

            if debit is not None and credit is not None:
                needs_review = True
                warnings.append(
                    f"Both debit and credit were populated for transaction row {row_index}."
                )

            if amount is None and balance is not None:
                needs_review = True

            description = row.description.strip()
            if not description:
                needs_review = True

            transaction = Transaction(
                transaction_date=row.transaction_date,
                description=description,
                debit=debit,
                credit=credit,
                balance=balance,
                source_page=row.page_number,
                raw_text=row.raw_text,
                needs_review=needs_review,
            )
            transactions.append(transaction)

            if balance is not None:
                previous_balance = balance

        return transactions, warnings

    def _interpret_line_amounts(
        self, tokens: list[AmountToken]
    ) -> tuple[float | None, float | None, str | None, bool]:
        if len(tokens) == 1:
            token = tokens[0]
            marker_direction = self._direction_from_text(token.marker or "")
            return abs(token.value), None, marker_direction, True

        balance = tokens[-1].value
        leading_tokens = tokens[:-1]
        amount = abs(leading_tokens[-1].value)
        marker_direction = None
        for token in reversed(leading_tokens):
            token_direction = self._direction_from_text(token.marker or "")
            if token_direction:
                marker_direction = token_direction
                amount = abs(token.value)
                break
        return amount, balance, marker_direction, False

    def _resolve_direction(
        self,
        row: _RawRow,
        marker_direction: str | None,
        previous_balance: float | None,
        balance: float | None,
    ) -> str | None:
        delta = self._balance_delta(previous_balance, balance)
        if marker_direction:
            return marker_direction
        if delta is not None:
            return "credit" if delta > 0 else "debit"
        if row.explicit_direction:
            return row.explicit_direction

        if self._CREDIT_HINT.search(row.description) and not self._DEBIT_HINT.search(
            row.description
        ):
            return "credit"
        if self._DEBIT_HINT.search(row.description) and not self._CREDIT_HINT.search(
            row.description
        ):
            return "debit"
        return None

    @staticmethod
    def _balance_delta(
        previous_balance: float | None, balance: float | None
    ) -> float | None:
        if previous_balance is None or balance is None:
            return None
        delta = round(balance - previous_balance, 2)
        return delta if abs(delta) > BALANCE_TOLERANCE else None

    @staticmethod
    def _positive_or_none(value: float | None) -> float | None:
        if value is None:
            return None
        value = abs(value)
        return value if value > 0 else None

    @staticmethod
    def _direction_from_text(value: str) -> str | None:
        normalized = re.sub(r"[^A-Za-z/]", " ", value or "").upper()
        if re.search(r"\bCR\b|\bCREDIT\b|\bDEPOSIT\b", normalized):
            return "credit"
        if re.search(r"\bDR\b|\bDEBIT\b|\bWITHDRAWAL\b", normalized):
            return "debit"
        return None

    def _detect_table_header(self, row: list[str]) -> dict[str, int] | None:
        normalized = [self._normalise_header(cell) for cell in row]
        mapping: dict[str, int] = {}

        column_groups = {
            "date": (
                "transactiondate",
                "txndate",
                "valuedate",
                "postingdate",
                "date",
            ),
            "description": (
                "transactionremarks",
                "description",
                "narration",
                "particulars",
                "remarks",
                "details",
            ),
            "debit": ("withdrawal", "debit", "dr"),
            "credit": ("deposit", "credit", "cr"),
            "balance": ("closingbalance", "runningbalance", "balance"),
            "amount": ("transactionamount", "amount"),
            "type": ("drcr", "transactiontype", "type"),
        }
        for key, aliases in column_groups.items():
            index = self._find_column(normalized, aliases)
            if index is not None:
                mapping[key] = index

        has_date = "date" in mapping
        has_amount_column = any(
            key in mapping for key in ("debit", "credit", "balance", "amount")
        )
        if has_date and has_amount_column:
            return mapping
        return None

    @staticmethod
    def _find_column(headers: list[str], aliases: tuple[str, ...]) -> int | None:
        for alias in aliases:
            for index, header in enumerate(headers):
                if not header:
                    continue
                if len(alias) <= 2:
                    if header == alias:
                        return index
                elif header == alias or alias in header:
                    return index
        return None

    @staticmethod
    def _normalise_header(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", (value or "").lower())

    @staticmethod
    def _cell(row: list[str], index: int | None) -> str:
        if index is None or index >= len(row):
            return ""
        return row[index]

    @staticmethod
    def _normalise_line(line: str) -> str:
        return " ".join((line or "").replace("\u00a0", " ").split())

    def _is_continuation(self, line: str, previous_row: _RawRow | None) -> bool:
        if previous_row is None:
            return False
        if len(line) > 220 or not re.search(r"[A-Za-z]", line):
            return False
        if self._NOISE_CONTINUATION_PATTERN.search(line):
            return False
        if re.search(r"\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}", line):
            return False
        return True

    @staticmethod
    def _default_year(account: AccountInfo | None, pages: list[str]) -> int | None:
        if account:
            if account.statement_period_end:
                return account.statement_period_end.year
            if account.statement_period_start:
                return account.statement_period_start.year
        combined_text = "\n".join(pages)
        years = [int(year) for year in re.findall(r"\b(?:19|20)\d{2}\b", combined_text)]
        return max(set(years), key=years.count) if years else None

    @staticmethod
    def _deduplicate(transactions: list[Transaction]) -> tuple[list[Transaction], int]:
        unique: list[Transaction] = []
        seen: set[tuple[object, ...]] = set()
        duplicate_count = 0

        for transaction in transactions:
            if transaction.balance is not None:
                key = (
                    transaction.transaction_date,
                    round(transaction.debit or 0.0, 2),
                    round(transaction.credit or 0.0, 2),
                    round(transaction.balance, 2),
                )
            else:
                description_key = re.sub(
                    r"[^a-z0-9]+", "", transaction.description.lower()
                )
                key = (
                    transaction.transaction_date,
                    round(transaction.debit or 0.0, 2),
                    round(transaction.credit or 0.0, 2),
                    description_key,
                )
            if key in seen:
                duplicate_count += 1
                continue
            seen.add(key)
            unique.append(transaction)
        return unique, duplicate_count
