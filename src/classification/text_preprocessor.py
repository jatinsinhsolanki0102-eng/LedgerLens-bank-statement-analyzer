"""Text normalisation used by both rule matching and the ML pipeline."""

from __future__ import annotations

import re


class TextPreprocessor:
    """Clean transaction descriptions without discarding merchant signal."""

    _TRANSACTION_PREFIX = re.compile(
        r"^\s*(?:UPI|IMPS|NEFT|RTGS|POS|ATM|ACH|ECS|MB|IB|SI|CARD|"
        r"DEBIT|CREDIT)[/\-\s:]+",
        re.IGNORECASE,
    )
    _LONG_REFERENCE = re.compile(r"\b(?:[A-Z0-9]*\d[A-Z0-9]*){6,}\b", re.IGNORECASE)
    _CARD_NUMBER = re.compile(r"\b(?:\d[ -]?){12,19}\b")
    _DATE_TOKEN = re.compile(r"\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b")
    _MULTISPACE = re.compile(r"\s+")

    def clean(self, description: str) -> str:
        """Return a lower-case description suitable for TF-IDF features."""

        text = (description or "").strip()
        if not text:
            return ""

        text = text.replace("\u00a0", " ")
        text = self._DATE_TOKEN.sub(" ", text)
        text = self._CARD_NUMBER.sub(" ", text)
        text = re.sub(r"https?://\S+|www\.\S+", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"[\w.+-]+@[\w.-]+\.\w+", " ", text)
        text = self._TRANSACTION_PREFIX.sub("", text)
        text = re.sub(r"[/|:_*#]+", " ", text)
        text = re.sub(r"[^A-Za-z0-9&.' -]", " ", text)
        text = self._LONG_REFERENCE.sub(" ", text)
        text = re.sub(r"\b(?:ref|reference|txn|transaction|utr|rrn)\s*(?:no|id)?\b", " ", text, flags=re.I)
        text = self._MULTISPACE.sub(" ", text)
        return text.strip(" .-").lower()

    def clean_many(self, descriptions: list[str]) -> list[str]:
        return [self.clean(description) for description in descriptions]
