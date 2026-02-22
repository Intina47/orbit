from __future__ import annotations

from typing import Any

from decision_engine.observability import JsonLogger


class EngineLogger:
    """Logger facade for the memory_engine package."""

    def __init__(self) -> None:
        self._logger = JsonLogger(name="memory_engine")

    def info(self, event: str, **kwargs: Any) -> None:
        self._logger.info(event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._logger.warning(event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._logger.error(event, **kwargs)
