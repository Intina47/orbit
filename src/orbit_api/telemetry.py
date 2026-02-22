"""OpenTelemetry bootstrap for Orbit API."""

# pylint: disable=import-outside-toplevel

from __future__ import annotations

from fastapi import FastAPI

from orbit.logger import get_logger
from orbit_api.config import ApiConfig


def configure_telemetry(app: FastAPI, config: ApiConfig) -> None:
    """Attach OpenTelemetry instrumentation when exporter endpoint is configured."""

    endpoint = config.otel_exporter_endpoint
    if endpoint is None:
        return

    log = get_logger("orbit.api.telemetry")
    try:  # pragma: no cover - optional runtime dependency
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        log.warning(
            "otel_disabled_missing_dependency",
            endpoint=endpoint,
        )
        return

    resource = Resource.create({"service.name": config.otel_service_name})
    provider = TracerProvider(resource=resource)
    span_exporter = OTLPSpanExporter(endpoint=endpoint)
    provider.add_span_processor(BatchSpanProcessor(span_exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    HTTPXClientInstrumentor().instrument(tracer_provider=provider)
    log.info("otel_enabled", endpoint=endpoint, service_name=config.otel_service_name)
