"""Rule, machine-learning, and hybrid classification tests."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from config.category_rules import OTHER_CATEGORY
from config.settings import TRAINING_DATA_PATH
from src.classification.classification_engine import ClassificationEngine
from src.classification.ml_classifier import (
    ClassificationPrediction,
    MLClassifier,
    TrainingDataError,
)
from src.classification.rule_classifier import RuleClassifier
from src.classification.text_preprocessor import TextPreprocessor
from src.models import Transaction


@pytest.fixture(scope="module")
def trained_classifier(tmp_path_factory: pytest.TempPathFactory) -> tuple[MLClassifier, Path]:
    model_path = tmp_path_factory.mktemp("classifier") / "model.joblib"
    classifier = MLClassifier(model_path=model_path)
    classifier.train(dataset_path=TRAINING_DATA_PATH)
    return classifier, model_path


def test_preprocessor_removes_references_and_prefixes() -> None:
    cleaned = TextPreprocessor().clean(
        "UPI/ZOMATO/ORDER 445566 4111111111111111 01/04/2024"
    )

    assert cleaned == "zomato order"


def test_preprocessor_handles_empty_text() -> None:
    assert TextPreprocessor().clean("") == ""
    assert TextPreprocessor().clean_many(["", "  "]) == ["", ""]


def test_rule_classification_merchant_match() -> None:
    match = RuleClassifier().classify("UPI/ZOMATO/ORDER 445566")

    assert match is not None
    assert match.category == "Food & Dining"
    assert match.confidence >= 0.9


def test_rule_classification_respects_direction() -> None:
    classifier = RuleClassifier()

    assert classifier.classify("SALARY CREDIT APRIL", direction="credit") is not None
    assert classifier.classify("SALARY CREDIT APRIL", direction="debit") is None
    assert classifier.classify("ATM WITHDRAWAL", direction="debit") is not None
    assert classifier.classify("ATM WITHDRAWAL", direction="credit") is None


def test_generic_transfer_rule_is_above_default_threshold() -> None:
    match = RuleClassifier().classify("NEFT RECEIVED FROM SELF")

    assert match is not None
    assert match.category == "Transfer"


def test_rule_classification_returns_none_for_unknown_text() -> None:
    assert RuleClassifier().classify("mystery merchant settlement") is None


def test_model_training_and_metadata(trained_classifier: tuple[MLClassifier, Path]) -> None:
    classifier, model_path = trained_classifier
    metadata = classifier.metadata

    assert model_path.exists()
    assert classifier.available
    assert metadata is not None
    assert metadata["model_name"] in {"Logistic Regression", "Multinomial Naive Bayes"}
    assert metadata["training_rows"] > 0
    assert metadata["test_rows"] > 0
    assert metadata["selected_metrics"]["accuracy"] > 0.5
    assert metadata["synthetic_data"] is True
    assert any("synthetic" in warning.casefold() for warning in metadata["warnings"])
    assert len(metadata["confusion_matrix"]) == len(metadata["confusion_matrix_labels"])


def test_model_predicts_known_merchant(trained_classifier: tuple[MLClassifier, Path]) -> None:
    classifier, _ = trained_classifier
    prediction = classifier.predict("zomato food order")

    assert prediction is not None
    assert 0.0 <= prediction.confidence <= 1.0


def test_model_batch_prediction(trained_classifier: tuple[MLClassifier, Path]) -> None:
    classifier, _ = trained_classifier
    predictions = classifier.predict_many(["zomato order", "", "netflix subscription"])

    assert len(predictions) == 3
    assert predictions[0] is not None
    assert predictions[1] is None
    assert predictions[2] is not None


def test_model_artifact_can_be_reloaded(trained_classifier: tuple[MLClassifier, Path]) -> None:
    _, model_path = trained_classifier
    reloaded = MLClassifier(model_path=model_path)

    assert reloaded.load()
    assert reloaded.predict("swiggy restaurant order") is not None


def test_training_rejects_conflicting_labels(tmp_path: Path) -> None:
    dataset = tmp_path / "conflicting.csv"
    rows = [
        {"description": "same merchant description", "category": "Shopping"},
        {"description": "same merchant description", "category": "Food & Dining"},
    ]
    rows.extend(
        [
            {"description": f"unique example {index}", "category": "Shopping"}
            for index in range(6)
        ]
    )
    pd.DataFrame(rows).to_csv(dataset, index=False)

    with pytest.raises(TrainingDataError, match="multiple categories"):
        MLClassifier(model_path=tmp_path / "model.joblib").train(dataset)


def test_training_rejects_unknown_category(tmp_path: Path) -> None:
    dataset = tmp_path / "unknown.csv"
    rows = [
        {"description": f"unique example {index}", "category": "Not A Real Category"}
        for index in range(8)
    ]
    pd.DataFrame(rows).to_csv(dataset, index=False)

    with pytest.raises(TrainingDataError, match="not defined"):
        MLClassifier(model_path=tmp_path / "model.joblib").train(dataset)


class _StubMLClassifier:
    available = True

    def __init__(self, prediction: ClassificationPrediction | None) -> None:
        self._prediction = prediction

    def predict_many(self, descriptions: list[str]) -> list[ClassificationPrediction | None]:
        return [self._prediction for _ in descriptions]


def test_hybrid_engine_prefers_rules() -> None:
    engine = ClassificationEngine(
        rule_classifier=RuleClassifier(),
        ml_classifier=_StubMLClassifier(ClassificationPrediction("Shopping", 0.99)),
    )
    transactions = [
        Transaction(transaction_date=None, description="UPI/ZOMATO ORDER", debit=500.0)
    ]

    engine.classify_all(transactions)

    assert transactions[0].category == "Food & Dining"
    assert transactions[0].classification_method == "Rule-based"


def test_hybrid_engine_uses_confident_ml_prediction() -> None:
    engine = ClassificationEngine(
        rule_classifier=RuleClassifier(),
        ml_classifier=_StubMLClassifier(ClassificationPrediction("Shopping", 0.90)),
        ml_confidence_threshold=0.55,
    )
    transactions = [
        Transaction(transaction_date=None, description="mystery merchant", debit=500.0)
    ]

    engine.classify_all(transactions)

    assert transactions[0].category == "Shopping"
    assert transactions[0].classification_method == "Machine Learning"
    assert not transactions[0].needs_review


def test_hybrid_engine_sends_low_confidence_to_review() -> None:
    engine = ClassificationEngine(
        rule_classifier=RuleClassifier(),
        ml_classifier=_StubMLClassifier(ClassificationPrediction("Shopping", 0.20)),
        ml_confidence_threshold=0.55,
    )
    transactions = [
        Transaction(transaction_date=None, description="mystery merchant", debit=500.0)
    ]

    engine.classify_all(transactions)

    assert transactions[0].category == OTHER_CATEGORY
    assert transactions[0].classification_method == "ML - Needs Review"
    assert transactions[0].needs_review


def test_hybrid_engine_without_ml_marks_unclassified() -> None:
    engine = ClassificationEngine(rule_classifier=RuleClassifier(), ml_classifier=None)
    transactions = [
        Transaction(transaction_date=None, description="mystery merchant", debit=500.0)
    ]

    engine.classify_all(transactions)

    assert transactions[0].category == OTHER_CATEGORY
    assert transactions[0].classification_method == "Unclassified"
    assert transactions[0].needs_review
