"""Hybrid deterministic-rule and traditional-ML classification engine."""

from __future__ import annotations

import re

from config.category_rules import OTHER_CATEGORY
from config.settings import ML_CONFIDENCE_THRESHOLD
from src.classification.ml_classifier import MLClassifier
from src.classification.rule_classifier import RuleClassifier
from src.models import Transaction
from src.utils.logging_config import get_logger

logger = get_logger("classification_engine")

_AMBIGUOUS_PAYMENT_RAIL = re.compile(r"\b(?:upi|neft|imps|rtgs)\b", flags=re.IGNORECASE)


class ClassificationEngine:
    """Apply high-confidence rules first, then ML, then a review fallback."""

    def __init__(
        self,
        rule_classifier: RuleClassifier | None = None,
        ml_classifier: MLClassifier | None = None,
        ml_confidence_threshold: float = ML_CONFIDENCE_THRESHOLD,
    ) -> None:
        self.rule_classifier = rule_classifier or RuleClassifier()
        self.ml_classifier = ml_classifier
        self.ml_confidence_threshold = ml_confidence_threshold

    @property
    def ml_available(self) -> bool:
        return bool(self.ml_classifier and self.ml_classifier.available)

    def classify_all(self, transactions: list[Transaction]) -> list[Transaction]:
        """Classify transactions in place and return the same list."""

        pending: list[tuple[int, Transaction]] = []
        for index, transaction in enumerate(transactions):
            rule_match = self.rule_classifier.classify(
                transaction.description, direction=transaction.direction
            )
            if rule_match:
                transaction.category = rule_match.category
                transaction.classification_method = "Rule-based"
                transaction.confidence_score = rule_match.confidence
                transaction.needs_review = transaction.needs_review or (
                    rule_match.category == OTHER_CATEGORY
                )
            elif _AMBIGUOUS_PAYMENT_RAIL.search(transaction.description or ""):
                transaction.category = OTHER_CATEGORY
                transaction.classification_method = "Ambiguous - Needs Review"
                transaction.confidence_score = 0.0
                transaction.needs_review = True
            else:
                pending.append((index, transaction))

        predictions = self._predict_pending(pending)
        for (_, transaction), prediction in zip(pending, predictions, strict=True):
            if prediction is None:
                transaction.category = OTHER_CATEGORY
                transaction.classification_method = "Unclassified"
                transaction.confidence_score = 0.0
                transaction.needs_review = True
                continue

            if prediction.confidence < self.ml_confidence_threshold:
                transaction.category = OTHER_CATEGORY
                transaction.classification_method = "ML - Needs Review"
                transaction.confidence_score = prediction.confidence
                transaction.needs_review = True
                continue

            transaction.category = prediction.category
            transaction.classification_method = "Machine Learning"
            transaction.confidence_score = prediction.confidence
            if prediction.category == OTHER_CATEGORY:
                transaction.needs_review = True

        rule_count = sum(
            transaction.classification_method == "Rule-based"
            for transaction in transactions
        )
        logger.info(
            "Classified %s transactions: %s by rules and %s by ML/review fallback",
            len(transactions),
            rule_count,
            len(transactions) - rule_count,
        )
        return transactions

    def _predict_pending(
        self, pending: list[tuple[int, Transaction]]
    ) -> list:
        if not pending or not self.ml_available:
            return [None for _ in pending]
        descriptions = [transaction.description for _, transaction in pending]
        return self.ml_classifier.predict_many(descriptions)
