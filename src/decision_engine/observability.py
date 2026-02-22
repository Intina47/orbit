from __future__ import annotations

import logging
import os
from typing import Any

import structlog


class _StructlogState:
    def __init__(self) -> None:
        self.configured = False


_STATE = _StructlogState()


def configure_structlog(log_level: str | None = None) -> None:
    """Configure structlog once with strict JSON output."""

    if _STATE.configured:
        return

    resolved_text = (
        log_level if log_level is not None else os.getenv("LOG_LEVEL", "INFO")
    )
    resolved_level = resolved_text.upper()
    level_value = getattr(logging, resolved_level, logging.INFO)
    logging.basicConfig(format="%(message)s", level=level_value)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(ensure_ascii=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level_value),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _STATE.configured = True


class JsonLogger:
    """Compatibility logger wrapper backed by strict structlog JSON output."""

    def __init__(self, name: str = "decision_engine") -> None:
        configure_structlog()
        self._logger = structlog.get_logger(name)

    def info(self, event: str, **kwargs: Any) -> None:
        self._logger.info(event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._logger.warning(event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._logger.error(event, **kwargs)
