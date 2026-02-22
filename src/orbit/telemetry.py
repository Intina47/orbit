"""Anonymous telemetry hooks for SDK usage events."""

from __future__ import annotations

from typing import Any

from orbit.logger import get_logger


class TelemetryClient:
    """Fire-and-forget telemetry client."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._log = get_logger("orbit.telemetry")

    def track(self, event_name: str, properties: dict[str, Any] | None = None) -> None:
        if not self._enabled:
            return
        self._log.debug(
            "telemetry_event",
            tracked_event=event_name,
            properties=properties or {},
        )
