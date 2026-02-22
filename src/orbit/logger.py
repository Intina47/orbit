"""Structlog configuration for Orbit SDK components."""

from __future__ import annotations

import logging
from typing import Any

import structlog
from structlog.typing import FilteringBoundLogger

_CONFIGURED = False

_LEVELS = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}


def configure_logging(log_level: str = "info") -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    level = _LEVELS.get(log_level.lower(), logging.INFO)
    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(ensure_ascii=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _CONFIGURED = True


def get_logger(name: str, **context: Any) -> FilteringBoundLogger:
    logger: FilteringBoundLogger = structlog.get_logger(name)
    if context:
        return logger.bind(**context)
    return logger
