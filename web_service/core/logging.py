from __future__ import annotations

import logging

from web_service.core.config import ERROR_LOG_PATH, LOG_DIR


LOGGER_NAME = "auto_fix_error_logger"


def get_error_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.ERROR)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.FileHandler(ERROR_LOG_PATH, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)

    return logger

