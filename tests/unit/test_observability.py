from __future__ import annotations

import json

from decision_engine.observability import JsonLogger, configure_structlog


def test_structlog_configuration_is_idempotent() -> None:
    configure_structlog(log_level="INFO")
    configure_structlog(log_level="DEBUG")


def test_json_logger_emits_structured_json(capsys) -> None:
    logger = JsonLogger(name="test-logger")
    logger.info("event_processed", memory_id="m1", confidence=0.75)
    output = capsys.readouterr().out.strip()
    payload = json.loads(output.splitlines()[-1])
    assert payload["event"] == "event_processed"
    assert payload["memory_id"] == "m1"
