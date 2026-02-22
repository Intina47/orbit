from __future__ import annotations

from decision_engine.models import RawEvent, SemanticUnderstanding
from decision_engine.semantic_encoding import SemanticProvider
from memory_engine.providers.registry import (
    build_semantic_provider as _build_from_registry,
)


def build_semantic_provider(
    use_openai: bool = False,
    provider_name: str | None = None,
) -> SemanticProvider:
    """Build semantic provider from explicit provider name or environment."""

    return _build_from_registry(
        provider_name=provider_name,
        force_openai=use_openai,
    )


class SemanticExtractor:
    """Semantic extraction adapter used by Stage 1 processing."""

    def __init__(self, provider: SemanticProvider) -> None:
        self._provider = provider

    def extract(self, raw_event: RawEvent) -> SemanticUnderstanding:
        return self._provider.understand(raw_event)
