"""Deterministic keyword and regex transaction classifier."""

from __future__ import annotations

import re
from dataclasses import dataclass

from config.category_rules import CATEGORY_RULES, CategoryRule
from config.settings import RULE_CONFIDENCE_THRESHOLD


@dataclass(frozen=True, slots=True)
class RuleMatch:
    category: str
    confidence: float
    rule: CategoryRule
    matched_pattern: str


class RuleClassifier:
    """Match configured merchant and transaction keywords against descriptions."""

    def __init__(
        self,
        rules: tuple[CategoryRule, ...] = CATEGORY_RULES,
        confidence_threshold: float = RULE_CONFIDENCE_THRESHOLD,
    ) -> None:
        self._rules = rules
        self.confidence_threshold = confidence_threshold
        self._compiled_rules = [
            (
                rule,
                tuple(
                    (pattern, re.compile(pattern, flags=re.IGNORECASE))
                    for pattern in rule.patterns
                ),
            )
            for rule in rules
        ]

    def match(self, description: str, direction: str | None = None) -> RuleMatch | None:
        """Return the strongest deterministic match above the confidence threshold."""

        if not description or not description.strip():
            return None

        best_match: RuleMatch | None = None
        for rule, compiled_patterns in self._compiled_rules:
            if rule.direction and direction and rule.direction != direction:
                continue
            for pattern, compiled in compiled_patterns:
                if not compiled.search(description):
                    continue
                if best_match is None or rule.confidence > best_match.confidence:
                    best_match = RuleMatch(
                        category=rule.category,
                        confidence=rule.confidence,
                        rule=rule,
                        matched_pattern=pattern,
                    )
                break

        if best_match is None or best_match.confidence < self.confidence_threshold:
            return None
        return best_match

    def classify(self, description: str, direction: str | None = None) -> RuleMatch | None:
        """Public alias used by the hybrid classification engine."""

        return self.match(description, direction=direction)
