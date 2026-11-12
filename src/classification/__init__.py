"""Rule-based and traditional machine-learning classification."""

from src.classification.classification_engine import ClassificationEngine
from src.classification.ml_classifier import (
    ClassificationPrediction,
    MLClassifier,
    TrainingDataError,
    TrainingResult,
)
from src.classification.rule_classifier import RuleClassifier, RuleMatch
from src.classification.text_preprocessor import TextPreprocessor

__all__ = [
    "ClassificationEngine",
    "ClassificationPrediction",
    "MLClassifier",
    "RuleClassifier",
    "RuleMatch",
    "TextPreprocessor",
    "TrainingDataError",
    "TrainingResult",
]
