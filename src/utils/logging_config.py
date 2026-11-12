"""Safe application logging.

Log messages intentionally avoid file contents, account numbers, transaction
descriptions, and other financial details.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

from config.settings import LOG_DIR, ensure_runtime_directories

_LOGGER_NAME = "bank_statement_analyzer"
_CONFIGURED = False


def configure_logging() -> None:
    """Configure a rotating file logger once per process."""

    global _CONFIGURED
    if _CONFIGURED:
        return

    ensure_runtime_directories()
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    logger.propagate = False

    if not logger.handlers:
        handler = RotatingFileHandler(
            LOG_DIR / "app.log",
            maxBytes=2_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)

    _CONFIGURED = True


def get_logger(module_name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(f"{_LOGGER_NAME}.{module_name}")
