"""Application-wide configuration values.

Environment variables are read once at import time. This keeps configuration in
one place while still allowing deployments to override operational limits.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
TRAINING_DATA_PATH = DATA_DIR / "training" / "transactions_training.csv"
SAMPLE_DATA_DIR = DATA_DIR / "sample"
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_PATH = MODEL_DIR / "transaction_classifier.joblib"
LOG_DIR = PROJECT_ROOT / "logs"

MAX_UPLOAD_BYTES = int(os.getenv("BANK_STATEMENT_MAX_UPLOAD_MB", "15")) * 1024 * 1024
SUPPORTED_FILE_EXTENSIONS = {".pdf"}
MIN_TEXT_CHARS_PER_PAGE = int(os.getenv("BANK_STATEMENT_MIN_TEXT_CHARS", "40"))
OCR_DPI = int(os.getenv("BANK_STATEMENT_OCR_DPI", "300"))
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "")

RULE_CONFIDENCE_THRESHOLD = float(os.getenv("BANK_STATEMENT_RULE_THRESHOLD", "0.80"))
ML_CONFIDENCE_THRESHOLD = float(os.getenv("BANK_STATEMENT_ML_THRESHOLD", "0.55"))
BALANCE_TOLERANCE = float(os.getenv("BANK_STATEMENT_BALANCE_TOLERANCE", "0.01"))
MAX_VALIDATION_ISSUES = 200
STATEMENT_CURRENCY = "INR"
CURRENCY_SYMBOL = "₹"

APP_TITLE = "LedgerLens"
APP_SUBTITLE = "Bank Statement Intelligence"
PRIVACY_NOTICE = (
    "Files are processed locally and are not sent to any external AI, OCR, or "
    "financial service. Temporary files are removed after processing."
)


def ensure_runtime_directories() -> None:
    """Create directories required by logging and model persistence."""

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
