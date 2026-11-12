"""Traditional TF-IDF machine-learning classifier and training pipeline."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import FeatureUnion, Pipeline

from config.category_rules import CATEGORIES, OTHER_CATEGORY
from config.settings import MODEL_PATH, TRAINING_DATA_PATH, ensure_runtime_directories
from src.classification.text_preprocessor import TextPreprocessor
from src.utils.logging_config import get_logger

logger = get_logger("ml_classifier")

SYNTHETIC_DATA_NOTE = (
    "The bundled training file contains synthetic demonstration descriptions. "
    "Its evaluation metrics do not establish real-world accuracy."
)


class TrainingDataError(ValueError):
    """Raised when the labelled dataset cannot support a reliable training run."""


@dataclass(frozen=True, slots=True)
class ClassificationPrediction:
    category: str
    confidence: float


@dataclass(frozen=True, slots=True)
class TrainingResult:
    model_name: str
    metrics: dict[str, Any]
    metadata: dict[str, Any]


class MLClassifier:
    """Train, persist, and use a classical text-classification pipeline."""

    def __init__(
        self,
        model_path: str | Path = MODEL_PATH,
        preprocessor: TextPreprocessor | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.preprocessor = preprocessor or TextPreprocessor()
        self._pipeline: Pipeline | None = None
        self._metadata: dict[str, Any] | None = None

    @property
    def available(self) -> bool:
        return self._pipeline is not None

    @property
    def metadata(self) -> dict[str, Any] | None:
        return self._metadata

    def load(self) -> bool:
        """Load a persisted model, returning ``False`` when it is unavailable."""

        if not self.model_path.exists():
            return False
        try:
            artifact = joblib.load(self.model_path)
            pipeline = artifact.get("pipeline")
            if not isinstance(pipeline, Pipeline):
                raise ValueError("Model artifact does not contain a sklearn Pipeline.")
            self._pipeline = pipeline
            self._metadata = artifact.get("metadata", {})
            logger.info("Loaded classifier model from local artifact")
            return True
        except Exception as exc:
            logger.warning("Classifier model load failed: %s", type(exc).__name__)
            self._pipeline = None
            self._metadata = None
            return False

    def ensure_trained(
        self,
        dataset_path: str | Path = TRAINING_DATA_PATH,
        model_path: str | Path | None = None,
    ) -> bool:
        """Load an existing model or train one from the bundled dataset."""

        if self.load():
            return True
        try:
            self.train(dataset_path=dataset_path, model_path=model_path or self.model_path)
            return True
        except (TrainingDataError, OSError, ValueError) as exc:
            logger.warning("Classifier training unavailable: %s", type(exc).__name__)
            return False

    def train(
        self,
        dataset_path: str | Path = TRAINING_DATA_PATH,
        model_path: str | Path | None = None,
        test_size: float = 0.25,
        random_state: int = 42,
    ) -> TrainingResult:
        """Train Logistic Regression and Multinomial NB, persist the better model."""

        dataset_path = Path(dataset_path)
        if not dataset_path.exists():
            raise TrainingDataError("The labelled training dataset could not be found.")

        dataframe = pd.read_csv(dataset_path)
        required_columns = {"description", "category"}
        if not required_columns.issubset(dataframe.columns):
            raise TrainingDataError(
                "Training data must contain 'description' and 'category' columns."
            )

        dataframe = dataframe.dropna(subset=["description", "category"]).copy()
        dataframe["description"] = dataframe["description"].astype(str).str.strip()
        dataframe["category"] = dataframe["category"].astype(str).str.strip()
        dataframe = dataframe[dataframe["description"] != ""]

        unknown_categories = sorted(set(dataframe["category"]) - set(CATEGORIES))
        if unknown_categories:
            raise TrainingDataError(
                "Dataset contains categories not defined in configuration: "
                + ", ".join(unknown_categories)
            )
        if len(dataframe) < 8 or dataframe["category"].nunique() < 2:
            raise TrainingDataError(
                "At least 8 labelled rows across 2 or more categories are required."
            )

        cleaned_descriptions = self.preprocessor.clean_many(
            dataframe["description"].tolist()
        )
        labels = dataframe["category"].tolist()
        warnings: list[str] = []

        conflict_check = pd.DataFrame(
            {"text": cleaned_descriptions, "category": labels}
        )
        conflicting_texts = conflict_check.groupby("text")["category"].nunique()
        if (conflicting_texts > 1).any():
            raise TrainingDataError(
                "The same cleaned description is assigned to multiple categories."
            )
        deduplicated = conflict_check.drop_duplicates(subset=["text"], keep="first")
        if len(deduplicated) < len(conflict_check):
            warnings.append(
                f"Removed {len(conflict_check) - len(deduplicated)} duplicate cleaned "
                "description(s) to reduce train/test leakage."
            )
        cleaned_descriptions = deduplicated["text"].tolist()
        labels = deduplicated["category"].tolist()
        class_counts = deduplicated["category"].value_counts()

        stratify_labels: list[str] | None = labels
        if int(class_counts.min()) < 2:
            stratify_labels = None
            warnings.append(
                "Some categories have fewer than two examples; the holdout split is not stratified."
            )

        try:
            X_train, X_test, y_train, y_test = train_test_split(
                cleaned_descriptions,
                labels,
                test_size=test_size,
                random_state=random_state,
                stratify=stratify_labels,
            )
        except ValueError as exc:
            raise TrainingDataError(
                "The dataset is too small or imbalanced for the requested holdout split."
            ) from exc

        def text_features() -> FeatureUnion:
            return FeatureUnion(
                [
                    (
                        "word",
                        TfidfVectorizer(
                            ngram_range=(1, 2),
                            min_df=1,
                            max_features=5000,
                            sublinear_tf=True,
                        ),
                    ),
                    (
                        "character",
                        TfidfVectorizer(
                            analyzer="char_wb",
                            ngram_range=(2, 5),
                            min_df=1,
                            max_features=10000,
                            sublinear_tf=True,
                        ),
                    ),
                ]
            )

        model_candidates: dict[str, Pipeline] = {
            "Logistic Regression": Pipeline(
                [
                    ("tfidf", text_features()),
                    (
                        "classifier",
                        LogisticRegression(
                            max_iter=2000,
                            class_weight="balanced",
                            random_state=random_state,
                            C=4.0,
                        ),
                    ),
                ]
            ),
            "Multinomial Naive Bayes": Pipeline(
                [
                    ("tfidf", text_features()),
                    ("classifier", MultinomialNB(alpha=0.3)),
                ]
            ),
        }

        labels_for_metrics = [label for label in CATEGORIES if label in set(labels)]
        evaluated_models: dict[str, dict[str, Any]] = {}
        trained_pipelines: dict[str, Pipeline] = {}
        for model_name, pipeline in model_candidates.items():
            pipeline.fit(X_train, y_train)
            predictions = pipeline.predict(X_test)
            precision, recall, f1, _ = precision_recall_fscore_support(
                y_test,
                predictions,
                labels=labels_for_metrics,
                average="macro",
                zero_division=0,
            )
            matrix = confusion_matrix(
                y_test, predictions, labels=labels_for_metrics
            ).tolist()
            evaluated_models[model_name] = {
                "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
                "precision_macro": round(float(precision), 4),
                "recall_macro": round(float(recall), 4),
                "f1_macro": round(float(f1), 4),
                "confusion_matrix": matrix,
            }
            trained_pipelines[model_name] = pipeline

        best_name = max(
            evaluated_models,
            key=lambda name: (
                evaluated_models[name]["f1_macro"],
                evaluated_models[name]["accuracy"],
            ),
        )
        best_pipeline = trained_pipelines[best_name]

        source_values: list[str] = []
        if "data_source" in dataframe.columns:
            source_values = sorted(
                str(value) for value in dataframe["data_source"].dropna().unique()
            )
        synthetic_only = bool(source_values) and all(
            "synthetic" in value.casefold() for value in source_values
        )
        if synthetic_only:
            warnings.append(SYNTHETIC_DATA_NOTE)
        else:
            warnings.append(
                "Metrics reflect only the supplied labelled dataset and should be "
                "validated before operational use."
            )
        if OTHER_CATEGORY not in labels_for_metrics:
            warnings.append(
                f"The training dataset has no '{OTHER_CATEGORY}' examples."
            )

        metadata = {
            "model_name": best_name,
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "training_rows": len(X_train),
            "test_rows": len(X_test),
            "total_rows": len(dataframe),
            "classes": labels_for_metrics,
            "models": evaluated_models,
            "selected_metrics": evaluated_models[best_name],
            "confusion_matrix": evaluated_models[best_name]["confusion_matrix"],
            "confusion_matrix_labels": labels_for_metrics,
            "dataset_path": str(dataset_path),
            "data_sources": source_values,
            "synthetic_data": synthetic_only,
            "warnings": warnings,
        }

        destination = Path(model_path or self.model_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"pipeline": best_pipeline, "metadata": metadata}, destination)

        self._pipeline = best_pipeline
        self._metadata = metadata
        logger.info(
            "Classifier trained with %s labelled rows; selected %s",
            len(dataframe),
            best_name,
        )
        return TrainingResult(
            model_name=best_name,
            metrics=evaluated_models[best_name],
            metadata=metadata,
        )

    def predict(self, description: str) -> ClassificationPrediction | None:
        """Predict a category and confidence for one description."""

        if self._pipeline is None:
            return None
        cleaned = self.preprocessor.clean(description)
        if not cleaned:
            return None
        probabilities = self._pipeline.predict_proba([cleaned])[0]
        classes = self._pipeline.classes_
        best_index = int(probabilities.argmax())
        return ClassificationPrediction(
            category=str(classes[best_index]),
            confidence=round(float(probabilities[best_index]), 4),
        )

    def predict_many(self, descriptions: list[str]) -> list[ClassificationPrediction | None]:
        """Predict descriptions in one batch to keep large statements responsive."""

        if self._pipeline is None or not descriptions:
            return [None for _ in descriptions]
        cleaned_descriptions = self.preprocessor.clean_many(descriptions)
        valid_indices = [index for index, text in enumerate(cleaned_descriptions) if text]
        results: list[ClassificationPrediction | None] = [None for _ in descriptions]
        if not valid_indices:
            return results

        probabilities = self._pipeline.predict_proba(
            [cleaned_descriptions[index] for index in valid_indices]
        )
        classes = self._pipeline.classes_
        for row_index, probability_row in enumerate(probabilities):
            best_index = int(probability_row.argmax())
            target_index = valid_indices[row_index]
            results[target_index] = ClassificationPrediction(
                category=str(classes[best_index]),
                confidence=round(float(probability_row[best_index]), 4),
            )
        return results


def main() -> None:
    """Command-line entry point for training the bundled model."""

    parser = argparse.ArgumentParser(description="Train the transaction classifier.")
    parser.add_argument("--dataset", type=Path, default=TRAINING_DATA_PATH)
    parser.add_argument("--model", type=Path, default=MODEL_PATH)
    arguments = parser.parse_args()

    ensure_runtime_directories()
    classifier = MLClassifier(model_path=arguments.model)
    result = classifier.train(dataset_path=arguments.dataset)
    metrics = result.metrics
    print(f"Selected model: {result.model_name}")
    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print(f"Macro precision: {metrics['precision_macro']:.4f}")
    print(f"Macro recall: {metrics['recall_macro']:.4f}")
    print(f"Macro F1: {metrics['f1_macro']:.4f}")
    for warning in result.metadata.get("warnings", []):
        print(f"Note: {warning}")


if __name__ == "__main__":
    main()
